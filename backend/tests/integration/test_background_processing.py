"""Durable background processing success, retry, duplicate, and failure tests."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from nexus.modules.inventory.models import StockLevel
from nexus.platform.background.models import (
    BackgroundJob,
    BusinessReport,
    LowStockAlert,
    NotificationDelivery,
)
from nexus.platform.background.service import (
    LOW_STOCK_JOB,
    NOTIFICATION_JOB,
    OUTBOX_JOB,
    REPORT_JOB,
    JobExecutor,
    JobScheduler,
    JobTenantInvalidError,
    NotificationProvider,
)
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_payments_api import auth, register, setup_confirmed_order

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
pytest_plugins = ("tests.integration.test_payments_api",)


class FailingProvider(NotificationProvider):
    async def send(self, job_id: UUID, recipient: str, subject: str) -> str:
        del job_id, recipient, subject
        raise OSError("test provider unavailable")


async def schedule(
    manager: DatabaseManager,
    organization_id: UUID,
    task_name: str,
    key: str,
    payload: dict[str, object],
    *,
    max_attempts: int = 3,
) -> tuple[UUID, bool]:
    async with manager.transaction() as session:
        job, created = await JobScheduler(session).schedule(
            organization_id=organization_id,
            task_name=task_name,
            idempotency_key=key,
            payload=payload,
            correlation_id=f"corr-{key}",
            max_attempts=max_attempts,
        )
        await session.flush()
        return job.id, created


async def test_required_jobs_succeed_and_are_tenant_scoped(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    token = await register(payment_client, "background-success@example.com")
    setup = await setup_confirmed_order(payment_client, token, "bg-ok")
    organization_id = UUID(setup["organization_id"])
    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        await session.execute(
            update(StockLevel)
            .where(StockLevel.organization_id == organization_id)
            .values(low_stock_threshold=100)
        )

    jobs = [
        await schedule(
            manager, organization_id, REPORT_JOB, "report-1", {"report_type": "summary"}
        ),
        await schedule(
            manager,
            organization_id,
            NOTIFICATION_JOB,
            "email-1",
            {"recipient": "recipient@example.com", "subject": "Low stock"},
        ),
        await schedule(manager, organization_id, LOW_STOCK_JOB, "stock-1", {}),
        await schedule(manager, organization_id, OUTBOX_JOB, "outbox-1", {}),
    ]
    for job_id, created in jobs:
        assert created is True
        async with manager.transaction() as session:
            result = await JobExecutor(session).execute(job_id)
            assert result.status == "succeeded"
            assert result.correlation_id is not None

    async with manager.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(BusinessReport)) == 1
        assert await session.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
        assert (await session.scalar(select(func.count()).select_from(LowStockAlert)) or 0) >= 1
        completed = await session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(
                BackgroundJob.organization_id == organization_id,
                BackgroundJob.status == "succeeded",
            )
        )
        assert completed == 4
    jobs_response = await payment_client.get(
        "/api/v1/background/jobs", headers=auth(token)
    )
    metrics_response = await payment_client.get(
        "/api/v1/background/metrics", headers=auth(token)
    )
    assert jobs_response.status_code == metrics_response.status_code == 200
    assert len(jobs_response.json()) == 4
    assert metrics_response.json()["succeeded"] == 4
    await manager.dispose()


async def test_retry_then_success_and_duplicate_delivery_is_idempotent(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    token = await register(payment_client, "background-retry@example.com")
    setup = await setup_confirmed_order(payment_client, token, "bg-retry")
    organization_id = UUID(setup["organization_id"])
    manager = DatabaseManager(payment_database_url, 2)
    job_id, created = await schedule(
        manager,
        organization_id,
        NOTIFICATION_JOB,
        "retry-email",
        {"recipient": "retry@example.com", "subject": "Retry test"},
    )
    duplicate_id, duplicate_created = await schedule(
        manager,
        organization_id,
        NOTIFICATION_JOB,
        "retry-email",
        {"recipient": "changed@example.com", "subject": "Ignored duplicate"},
    )
    assert created is True
    assert duplicate_created is False
    assert duplicate_id == job_id

    async with manager.transaction() as session:
        first = await JobExecutor(session, FailingProvider()).execute(job_id)
        assert first.status == "retrying"
        assert first.attempt_count == 1
    async with manager.transaction() as session:
        second = await JobExecutor(session).execute(job_id)
        assert second.status == "succeeded"
        assert second.attempt_count == 2
    async with manager.transaction() as session:
        duplicate = await JobExecutor(session).execute(job_id)
        assert duplicate.status == "succeeded"
        deliveries = await session.scalar(
            select(func.count()).select_from(NotificationDelivery).where(
                NotificationDelivery.job_id == job_id
            )
        )
        assert deliveries == 1
    await manager.dispose()


async def test_permanent_failure_moves_job_to_dead_without_delivery(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    token = await register(payment_client, "background-dead@example.com")
    setup = await setup_confirmed_order(payment_client, token, "bg-dead")
    manager = DatabaseManager(payment_database_url, 2)
    with pytest.raises(JobTenantInvalidError):
        await schedule(manager, uuid4(), REPORT_JOB, "wrong-tenant", {})
    job_id, _ = await schedule(
        manager,
        UUID(setup["organization_id"]),
        NOTIFICATION_JOB,
        "invalid-email",
        {"recipient": "invalid", "subject": "Invalid"},
        max_attempts=1,
    )
    async with manager.transaction() as session:
        job = await JobExecutor(session).execute(job_id)
        assert job.status == "dead"
        assert job.error_code == "invalid_notification_recipient"
    async with manager.transaction() as session:
        deliveries = await session.scalar(
            select(func.count()).select_from(NotificationDelivery).where(
                NotificationDelivery.job_id == job_id
            )
        )
        assert deliveries == 0
    await manager.dispose()
