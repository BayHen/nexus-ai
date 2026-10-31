"""Transactional event append, leased dispatch, idempotent consume, and reconciliation."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.orders.models import Order
from nexus.modules.payments.models import PaymentIntent
from nexus.platform.reliability.models import (
    BusinessAuditEvent,
    InboxReceipt,
    OutboxEvent,
    ReconciliationFinding,
)

logger = logging.getLogger(__name__)


class OutboxWriter:
    """Append an event and immutable audit record in the caller transaction."""

    def __init__(self, session: AsyncSession, correlation_id: str | None) -> None:
        self._session = session
        self._correlation_id = correlation_id

    def append(
        self,
        *,
        organization_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
        max_attempts: int = 5,
    ) -> OutboxEvent:
        event = OutboxEvent(
            organization_id=organization_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            correlation_id=self._correlation_id,
            max_attempts=max_attempts,
        )
        self._session.add(event)
        self._session.add(
            BusinessAuditEvent(
                organization_id=organization_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                correlation_id=self._correlation_id,
                details=payload,
            )
        )
        return event


class OutboxProcessor:
    """Lease events and complete an idempotent local consumer transaction."""

    def __init__(self, session: AsyncSession, *, base_retry_seconds: int = 2) -> None:
        self._session = session
        self._base_retry_seconds = base_retry_seconds

    async def claim(
        self,
        worker_id: str,
        *,
        organization_id: UUID | None = None,
        limit: int = 20,
        lease_seconds: int = 60,
    ) -> list[OutboxEvent]:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=lease_seconds)
        claim_filter = or_(
            and_(OutboxEvent.status == "pending", OutboxEvent.available_at <= now),
            and_(
                OutboxEvent.status == "processing",
                OutboxEvent.locked_at < stale_before,
            ),
        )
        if organization_id is not None:
            claim_filter = and_(
                OutboxEvent.organization_id == organization_id, claim_filter
            )
        rows = list(
            await self._session.scalars(
                select(OutboxEvent)
                .where(claim_filter)
                .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for event in rows:
            event.status = "processing"
            event.locked_at = now
            event.locked_by = worker_id
        await self._session.flush()
        logger.info(
            "Outbox events claimed",
            extra={"event": "outbox_claimed", "worker_id": worker_id, "event_count": len(rows)},
        )
        return rows

    async def consume(
        self,
        event_id: UUID,
        *,
        worker_id: str,
        consumer_name: str = "business-events-v1",
        simulate_failure: bool = False,
    ) -> bool:
        event = await self._session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if event is None:
            raise LookupError("outbox event not found")
        receipt = await self._session.scalar(
            select(InboxReceipt).where(
                InboxReceipt.consumer_name == consumer_name,
                InboxReceipt.event_id == event.id,
            )
        )
        if receipt is not None:
            self._mark_published(event)
            return True
        if event.status != "processing" or event.locked_by != worker_id:
            raise RuntimeError("outbox lease is not owned by this worker")
        if simulate_failure:
            self._mark_failed(event, "simulated_consumer_failure")
            await self._session.flush()
            logger.warning(
                "Outbox consumer failed",
                extra={
                    "event": "outbox_consumer_failed",
                    "outbox_event_id": str(event.id),
                    "event_type": event.event_type,
                    "attempt_count": event.attempt_count,
                    "correlation_id": event.correlation_id,
                },
            )
            return False
        self._session.add(
            InboxReceipt(
                organization_id=event.organization_id,
                consumer_name=consumer_name,
                event_id=event.id,
                correlation_id=event.correlation_id,
            )
        )
        self._mark_published(event)
        await self._session.flush()
        logger.info(
            "Outbox event published",
            extra={
                "event": "outbox_published",
                "outbox_event_id": str(event.id),
                "event_type": event.event_type,
                "attempt_count": event.attempt_count,
                "correlation_id": event.correlation_id,
            },
        )
        return True

    @staticmethod
    def _mark_published(event: OutboxEvent) -> None:
        event.status = "published"
        event.published_at = datetime.now(UTC)
        event.locked_at = None
        event.locked_by = None
        event.last_error_code = None

    def _mark_failed(self, event: OutboxEvent, error_code: str) -> None:
        event.attempt_count += 1
        event.last_error_code = error_code
        event.locked_at = None
        event.locked_by = None
        if event.attempt_count >= event.max_attempts:
            event.status = "dead"
            return
        event.status = "pending"
        delay = min(self._base_retry_seconds * (2 ** (event.attempt_count - 1)), 300)
        event.available_at = datetime.now(UTC) + timedelta(seconds=delay)


class ReconciliationService:
    """Detect durable Order/Payment inconsistencies without mutating financial state."""

    def __init__(self, session: AsyncSession, correlation_id: str | None) -> None:
        self._session = session
        self._correlation_id = correlation_id

    async def run(self, organization_id: UUID) -> int:
        candidates = (
            await self._session.execute(
                select(PaymentIntent, Order)
                .join(
                    Order,
                    and_(
                        Order.organization_id == PaymentIntent.organization_id,
                        Order.id == PaymentIntent.order_id,
                    ),
                )
                .where(PaymentIntent.organization_id == organization_id)
            )
        ).all()
        findings: list[tuple[str, UUID, dict[str, object]]] = []
        for payment, order in candidates:
            if payment.status in {"succeeded", "refunded"} and order.status != "completed":
                findings.append(
                    (
                        "paid_order_not_completed",
                        payment.id,
                        {"payment_status": payment.status, "order_status": order.status},
                    )
                )
            if payment.amount != order.total_amount:
                findings.append(
                    (
                        "payment_order_amount_mismatch",
                        payment.id,
                        {
                            "payment_amount": str(payment.amount),
                            "order_total": str(order.total_amount),
                        },
                    )
                )
        completed_without_payment = list(
            await self._session.scalars(
                select(Order.id).where(
                    Order.organization_id == organization_id,
                    Order.status == "completed",
                    ~select(PaymentIntent.id)
                    .where(
                        PaymentIntent.organization_id == Order.organization_id,
                        PaymentIntent.order_id == Order.id,
                        PaymentIntent.status.in_(("succeeded", "refunded")),
                    )
                    .exists(),
                )
            )
        )
        findings.extend(
            ("completed_order_without_payment", order_id, {})
            for order_id in completed_without_payment
        )
        for code, aggregate_id, details in findings:
            await self._session.execute(
                insert(ReconciliationFinding)
                .values(
                    organization_id=organization_id,
                    finding_code=code,
                    aggregate_type="payment"
                    if code != "completed_order_without_payment"
                    else "order",
                    aggregate_id=aggregate_id,
                    status="open",
                    details=details,
                    correlation_id=self._correlation_id,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ReconciliationFinding.organization_id,
                        ReconciliationFinding.finding_code,
                        ReconciliationFinding.aggregate_id,
                    ]
                )
            )
        logger.info(
            "Payment reconciliation completed",
            extra={
                "event": "payment_reconciliation_completed",
                "finding_count": len(findings),
                "correlation_id": self._correlation_id,
            },
        )
        return len(findings)

    async def list_findings(self, organization_id: UUID) -> list[ReconciliationFinding]:
        return list(
            await self._session.scalars(
                select(ReconciliationFinding)
                .where(ReconciliationFinding.organization_id == organization_id)
                .order_by(ReconciliationFinding.detected_at.desc(), ReconciliationFinding.id)
            )
        )

    async def pending_outbox_count(self, organization_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.organization_id == organization_id,
                OutboxEvent.status.in_(("pending", "processing", "dead")),
            )
        )
        return int(value or 0)
