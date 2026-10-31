"""Durable, tenant-validated and idempotent background job execution."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import StockLevel
from nexus.modules.orders.models import Order
from nexus.modules.organizations.models import Organization
from nexus.platform.background.models import (
    BackgroundJob,
    BusinessReport,
    LowStockAlert,
    NotificationDelivery,
)
from nexus.platform.reliability.service import OutboxProcessor

logger = logging.getLogger(__name__)

REPORT_JOB: Final = "generate_business_report"
NOTIFICATION_JOB: Final = "send_notification_email"
LOW_STOCK_JOB: Final = "process_low_stock_alerts"
OUTBOX_JOB: Final = "process_transactional_outbox"
SUPPORTED_JOBS: Final = frozenset(
    {REPORT_JOB, NOTIFICATION_JOB, LOW_STOCK_JOB, OUTBOX_JOB}
)


class JobNotFoundError(LookupError):
    """Raised when a task references an unknown job identifier."""


class JobTenantInvalidError(RuntimeError):
    """Raised when the durable tenant no longer exists."""


class RetryableJobError(RuntimeError):
    """Signals infrastructure failure that Celery should retry."""


class PermanentJobError(RuntimeError):
    """Signals invalid job input that should not be retried."""


class JobScheduler:
    """Create a job once per tenant, type, and caller idempotency key."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def schedule(
        self,
        *,
        organization_id: UUID,
        task_name: str,
        idempotency_key: str,
        payload: dict[str, object],
        correlation_id: str | None,
        max_attempts: int = 5,
    ) -> tuple[BackgroundJob, bool]:
        if task_name not in SUPPORTED_JOBS:
            raise PermanentJobError("unsupported_job_type")
        if not await self._session.scalar(
            select(Organization.id).where(Organization.id == organization_id)
        ):
            raise JobTenantInvalidError("organization_not_found")
        statement = (
            insert(BackgroundJob)
            .values(
                organization_id=organization_id,
                task_name=task_name,
                idempotency_key=idempotency_key,
                payload=payload,
                correlation_id=correlation_id,
                max_attempts=max_attempts,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    BackgroundJob.organization_id,
                    BackgroundJob.task_name,
                    BackgroundJob.idempotency_key,
                ]
            )
            .returning(BackgroundJob.id)
        )
        created_id = await self._session.scalar(statement)
        job = await self._session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.organization_id == organization_id,
                BackgroundJob.task_name == task_name,
                BackgroundJob.idempotency_key == idempotency_key,
            )
        )
        if job is None:
            raise RuntimeError("background job insert did not return a durable row")
        return job, created_id is not None


JobHandler = Callable[[BackgroundJob], Awaitable[dict[str, object]]]


class NotificationProvider(Protocol):
    async def send(self, job_id: UUID, recipient: str, subject: str) -> str: ...


class TestNotificationProvider:
    """Deterministic provider that never contacts an external email service."""

    async def send(self, job_id: UUID, recipient: str, subject: str) -> str:
        del subject
        return str(uuid5(job_id, recipient))


class JobExecutor:
    """Lock and execute one job while making duplicate deliveries harmless."""

    def __init__(
        self,
        session: AsyncSession,
        notification_provider: NotificationProvider | None = None,
    ) -> None:
        self._session = session
        self._notification_provider = notification_provider or TestNotificationProvider()
        self._handlers: dict[str, JobHandler] = {
            REPORT_JOB: self._generate_report,
            NOTIFICATION_JOB: self._send_notification,
            LOW_STOCK_JOB: self._process_low_stock,
            OUTBOX_JOB: self._process_outbox,
        }

    async def execute(self, job_id: UUID) -> BackgroundJob:
        job = await self._session.scalar(
            select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update()
        )
        if job is None:
            raise JobNotFoundError(str(job_id))
        if job.status == "succeeded":
            logger.info(
                "Duplicate background job delivery ignored",
                extra=self._log_context(job, "background_job_duplicate"),
            )
            return job
        if job.status == "dead":
            return job
        if not await self._session.scalar(
            select(Organization.id).where(Organization.id == job.organization_id)
        ):
            self._fail(job, "tenant_context_invalid", permanent=True)
            raise JobTenantInvalidError("organization_not_found")

        job.status = "running"
        job.attempt_count += 1
        await self._session.flush()
        logger.info(
            "Background job started",
            extra=self._log_context(job, "background_job_started"),
        )
        try:
            result = await self._handlers[job.task_name](job)
        except PermanentJobError as exc:
            self._fail(job, str(exc), permanent=True)
            await self._session.flush()
            logger.error(
                "Background job permanently failed",
                extra=self._log_context(job, "background_job_dead"),
            )
            return job
        except Exception as exc:
            self._fail(job, type(exc).__name__, permanent=False)
            await self._session.flush()
            logger.warning(
                "Background job attempt failed",
                extra=self._log_context(job, "background_job_failed"),
            )
            return job

        job.status = "succeeded"
        job.result = result
        job.error_code = None
        job.completed_at = datetime.now(UTC)
        await self._session.flush()
        logger.info(
            "Background job completed",
            extra=self._log_context(job, "background_job_succeeded"),
        )
        return job

    def _fail(self, job: BackgroundJob, error_code: str, *, permanent: bool) -> None:
        exhausted = job.attempt_count >= job.max_attempts
        job.status = "dead" if permanent or exhausted else "retrying"
        job.error_code = error_code[:64]
        if job.status == "dead":
            job.completed_at = datetime.now(UTC)

    async def _generate_report(self, job: BackgroundJob) -> dict[str, object]:
        report_type = str(job.payload.get("report_type", "business_summary"))
        product_count = int(
            await self._session.scalar(
                select(func.count()).select_from(Product).where(
                    Product.organization_id == job.organization_id,
                    Product.deleted_at.is_(None),
                )
            )
            or 0
        )
        order_count = int(
            await self._session.scalar(
                select(func.count()).select_from(Order).where(
                    Order.organization_id == job.organization_id
                )
            )
            or 0
        )
        content: dict[str, object] = {
            "report_type": report_type,
            "product_count": product_count,
            "order_count": order_count,
        }
        self._session.add(
            BusinessReport(
                organization_id=job.organization_id,
                job_id=job.id,
                report_type=report_type,
                content=content,
            )
        )
        return content

    async def _send_notification(self, job: BackgroundJob) -> dict[str, object]:
        recipient = job.payload.get("recipient")
        subject = job.payload.get("subject")
        if not isinstance(recipient, str) or "@" not in recipient:
            raise PermanentJobError("invalid_notification_recipient")
        if not isinstance(subject, str) or not subject.strip():
            raise PermanentJobError("invalid_notification_subject")
        message_id = await self._notification_provider.send(job.id, recipient, subject)
        self._session.add(
            NotificationDelivery(
                organization_id=job.organization_id,
                job_id=job.id,
                recipient=recipient,
                subject=subject,
                provider_message_id=message_id,
            )
        )
        return {"provider": "test", "message_id": message_id}

    async def _process_low_stock(self, job: BackgroundJob) -> dict[str, object]:
        rows = list(
            await self._session.scalars(
                select(StockLevel).where(
                    StockLevel.organization_id == job.organization_id,
                    StockLevel.quantity <= StockLevel.low_stock_threshold,
                )
            )
        )
        for stock in rows:
            self._session.add(
                LowStockAlert(
                    organization_id=job.organization_id,
                    job_id=job.id,
                    branch_id=stock.branch_id,
                    product_id=stock.product_id,
                    quantity=str(stock.quantity),
                    threshold=str(stock.low_stock_threshold),
                )
            )
        return {"alert_count": len(rows)}

    async def _process_outbox(self, job: BackgroundJob) -> dict[str, object]:
        worker_id = f"celery:{job.id}"
        processor = OutboxProcessor(self._session)
        events = await processor.claim(
            worker_id, organization_id=job.organization_id, limit=20
        )
        processed = 0
        for event in events:
            if await processor.consume(event.id, worker_id=worker_id):
                processed += 1
        return {"claimed": len(events), "processed": processed}

    @staticmethod
    def _log_context(job: BackgroundJob, event: str) -> dict[str, object]:
        return {
            "event": event,
            "job_id": str(job.id),
            "task_name": job.task_name,
            "organization_id": str(job.organization_id),
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "correlation_id": job.correlation_id,
        }
