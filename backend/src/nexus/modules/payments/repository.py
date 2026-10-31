"""Tenant-scoped payment persistence operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.orders.models import Order
from nexus.modules.payments.models import (
    PaymentAuditLog,
    PaymentIntent,
    PaymentRefund,
    PaymentWebhookEvent,
)


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, instance: object) -> None:
        self._session.add(instance)

    async def order_for_update(self, organization_id: UUID, order_id: UUID) -> Order | None:
        return await self._session.scalar(
            select(Order)
            .where(Order.organization_id == organization_id, Order.id == order_id)
            .with_for_update()
        )

    async def intent_by_key(
        self, organization_id: UUID, idempotency_key: str
    ) -> PaymentIntent | None:
        return await self._session.scalar(
            select(PaymentIntent).where(
                PaymentIntent.organization_id == organization_id,
                PaymentIntent.idempotency_key == idempotency_key,
            )
        )

    async def intent_for_order(self, organization_id: UUID, order_id: UUID) -> PaymentIntent | None:
        return await self._session.scalar(
            select(PaymentIntent).where(
                PaymentIntent.organization_id == organization_id,
                PaymentIntent.order_id == order_id,
            )
        )

    async def intent(
        self, organization_id: UUID, payment_id: UUID, *, lock: bool = False
    ) -> PaymentIntent | None:
        statement = select(PaymentIntent).where(
            PaymentIntent.organization_id == organization_id, PaymentIntent.id == payment_id
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def intent_by_provider_id(
        self, provider: str, provider_intent_id: str, *, lock: bool = False
    ) -> PaymentIntent | None:
        statement = select(PaymentIntent).where(
            PaymentIntent.provider == provider,
            PaymentIntent.provider_intent_id == provider_intent_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def refund_by_key(
        self, organization_id: UUID, idempotency_key: str
    ) -> PaymentRefund | None:
        return await self._session.scalar(
            select(PaymentRefund).where(
                PaymentRefund.organization_id == organization_id,
                PaymentRefund.idempotency_key == idempotency_key,
            )
        )

    async def refund_by_provider_id(
        self, provider_refund_id: str, *, lock: bool = False
    ) -> PaymentRefund | None:
        statement = select(PaymentRefund).where(
            PaymentRefund.provider_refund_id == provider_refund_id
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def refund(self, organization_id: UUID, refund_id: UUID) -> PaymentRefund | None:
        return await self._session.scalar(
            select(PaymentRefund).where(
                PaymentRefund.organization_id == organization_id, PaymentRefund.id == refund_id
            )
        )

    async def committed_refund_total(self, organization_id: UUID, payment_id: UUID) -> Decimal:
        value = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
                PaymentRefund.organization_id == organization_id,
                PaymentRefund.payment_id == payment_id,
                PaymentRefund.status.in_(("pending", "succeeded")),
            )
        )
        return Decimal(value or 0)

    async def succeeded_refund_total(self, organization_id: UUID, payment_id: UUID) -> Decimal:
        value = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
                PaymentRefund.organization_id == organization_id,
                PaymentRefund.payment_id == payment_id,
                PaymentRefund.status == "succeeded",
            )
        )
        return Decimal(value or 0)

    async def event(self, provider: str, event_id: str) -> PaymentWebhookEvent | None:
        return await self._session.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.event_id == event_id,
            )
        )

    async def audits(self, organization_id: UUID, payment_id: UUID) -> list[PaymentAuditLog]:
        return list(
            await self._session.scalars(
                select(PaymentAuditLog)
                .where(
                    PaymentAuditLog.organization_id == organization_id,
                    PaymentAuditLog.payment_id == payment_id,
                )
                .order_by(PaymentAuditLog.created_at, PaymentAuditLog.id)
            )
        )
