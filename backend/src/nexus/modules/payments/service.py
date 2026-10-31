"""Payment use cases and transaction-safe webhook state transitions."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.organizations.domain import (
    Permission,
    TenantAccessDeniedError,
    TenantContext,
    has_permission,
)
from nexus.modules.payments.domain import (
    PaymentConflictError,
    PaymentNotFoundError,
    PaymentProvider,
)
from nexus.modules.payments.models import (
    PaymentAuditLog,
    PaymentIntent,
    PaymentRefund,
    PaymentWebhookEvent,
)
from nexus.modules.payments.repository import PaymentRepository
from nexus.modules.payments.schemas import WebhookEvent
from nexus.platform.api.request_context import get_request_id
from nexus.platform.reliability.service import OutboxWriter


class PaymentService:
    def __init__(self, session: AsyncSession, provider: PaymentProvider) -> None:
        self._session = session
        self._provider = provider
        self._repository = PaymentRepository(session)
        self._outbox = OutboxWriter(session, get_request_id())

    async def create_intent(
        self,
        context: TenantContext,
        *,
        order_id: UUID,
        currency: str,
        idempotency_key: str,
    ) -> tuple[PaymentIntent, bool]:
        self._authorize(context, Permission.PAYMENT_WRITE)
        fingerprint = self._fingerprint(order_id, currency)
        existing = await self._repository.intent_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            return self._replay_intent(existing, fingerprint)
        order = await self._repository.order_for_update(context.organization_id, order_id)
        if order is None:
            raise PaymentNotFoundError
        if order.status != "confirmed" or order.total_amount <= 0:
            raise PaymentConflictError
        order_payment = await self._repository.intent_for_order(context.organization_id, order_id)
        if order_payment is not None:
            raise PaymentConflictError
        provider_intent = await self._provider.create_intent(
            amount=order.total_amount,
            currency=currency,
            idempotency_key=f"{context.organization_id}:{idempotency_key}",
        )
        payment = PaymentIntent(
            organization_id=context.organization_id,
            order_id=order.id,
            provider=self._provider.name,
            provider_intent_id=provider_intent.id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            amount=order.total_amount,
            currency=currency,
            status=provider_intent.status,
            created_by_user_id=context.user_id,
        )
        self._repository.add(payment)
        await self._session.flush()
        self._audit(payment, "payment_intent_created", None, payment.status, context.user_id)
        self._emit(
            payment,
            "payment.intent.created",
            {
                "order_id": str(payment.order_id),
                "amount": str(payment.amount),
                "currency": currency,
            },
        )
        await self._session.flush()
        return payment, False

    async def get_intent(self, context: TenantContext, payment_id: UUID) -> PaymentIntent:
        self._authorize(context, Permission.PAYMENT_READ)
        payment = await self._repository.intent(context.organization_id, payment_id)
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def get_intent_for_simulation(
        self, context: TenantContext, payment_id: UUID
    ) -> PaymentIntent:
        self._authorize(context, Permission.PAYMENT_WRITE)
        payment = await self._repository.intent(context.organization_id, payment_id)
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def create_refund(
        self,
        context: TenantContext,
        payment_id: UUID,
        *,
        amount: Decimal,
        reason: str,
        idempotency_key: str,
    ) -> tuple[PaymentRefund, bool]:
        self._authorize(context, Permission.PAYMENT_REFUND)
        fingerprint = self._fingerprint(payment_id, amount, reason)
        existing = await self._repository.refund_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise PaymentConflictError
            return existing, True
        payment = await self._repository.intent(context.organization_id, payment_id, lock=True)
        if payment is None:
            raise PaymentNotFoundError
        if payment.status != "succeeded":
            raise PaymentConflictError
        committed = await self._repository.committed_refund_total(
            context.organization_id, payment.id
        )
        if committed + amount > payment.amount:
            raise PaymentConflictError
        provider_refund = await self._provider.create_refund(
            payment_intent_id=payment.provider_intent_id,
            amount=amount,
            idempotency_key=f"{context.organization_id}:{idempotency_key}",
        )
        refund = PaymentRefund(
            organization_id=context.organization_id,
            payment_id=payment.id,
            provider_refund_id=provider_refund.id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            amount=amount,
            status=provider_refund.status,
            reason=reason,
            created_by_user_id=context.user_id,
        )
        self._repository.add(refund)
        await self._session.flush()
        self._audit(
            payment,
            "refund_created",
            payment.status,
            payment.status,
            context.user_id,
            {"refund_id": str(refund.id), "amount": str(amount)},
        )
        self._emit(
            payment,
            "payment.refund.created",
            {"refund_id": str(refund.id), "amount": str(amount)},
        )
        await self._session.flush()
        return refund, False

    async def get_refund(
        self, context: TenantContext, payment_id: UUID, refund_id: UUID
    ) -> PaymentRefund:
        self._authorize(context, Permission.PAYMENT_READ)
        payment = await self._repository.intent(context.organization_id, payment_id)
        refund = await self._repository.refund(context.organization_id, refund_id)
        if payment is None or refund is None or refund.payment_id != payment.id:
            raise PaymentNotFoundError
        return refund

    async def get_refund_by_id(self, context: TenantContext, refund_id: UUID) -> PaymentRefund:
        self._authorize(context, Permission.PAYMENT_REFUND)
        refund = await self._repository.refund(context.organization_id, refund_id)
        if refund is None:
            raise PaymentNotFoundError
        return refund

    async def audits(self, context: TenantContext, payment_id: UUID) -> list[PaymentAuditLog]:
        self._authorize(context, Permission.PAYMENT_READ)
        if await self._repository.intent(context.organization_id, payment_id) is None:
            raise PaymentNotFoundError
        return await self._repository.audits(context.organization_id, payment_id)

    async def process_webhook(
        self, event: WebhookEvent, raw_body: bytes
    ) -> tuple[PaymentIntent | None, PaymentRefund | None, bool]:
        if event.type.startswith("payment."):
            provider_id = event.data.provider_intent_id
            if provider_id is None:
                raise PaymentConflictError
            payment = await self._repository.intent_by_provider_id(
                self._provider.name, provider_id, lock=True
            )
            if payment is None:
                raise PaymentNotFoundError
            if await self._is_duplicate_event(event, raw_body):
                return payment, None, True
            await self._apply_payment_event(payment, event.type)
            self._record_event(event, raw_body, payment_id=payment.id)
            await self._session.flush()
            return payment, None, False

        provider_refund_id = event.data.provider_refund_id
        if provider_refund_id is None:
            raise PaymentConflictError
        refund = await self._repository.refund_by_provider_id(provider_refund_id, lock=True)
        if refund is None:
            raise PaymentNotFoundError
        payment = await self._repository.intent(
            refund.organization_id, refund.payment_id, lock=True
        )
        if payment is None:
            raise PaymentNotFoundError
        if await self._is_duplicate_event(event, raw_body):
            return payment, refund, True
        await self._apply_refund_event(payment, refund, event.type)
        self._record_event(event, raw_body, payment_id=payment.id, refund_id=refund.id)
        await self._session.flush()
        return payment, refund, False

    async def _is_duplicate_event(self, event: WebhookEvent, raw_body: bytes) -> bool:
        existing = await self._repository.event(self._provider.name, event.event_id)
        if existing is None:
            return False
        if existing.payload_digest != hashlib.sha256(raw_body).hexdigest():
            raise PaymentConflictError
        return True

    async def _apply_payment_event(self, payment: PaymentIntent, event_type: str) -> None:
        previous = payment.status
        if event_type == "payment.succeeded" and payment.status in {"pending", "failed"}:
            order = await self._repository.order_for_update(
                payment.organization_id, payment.order_id
            )
            if order is None or order.status not in {"confirmed", "completed"}:
                raise PaymentConflictError
            transitioned_at = datetime.now(UTC)
            payment.status = "succeeded"
            payment.failure_code = None
            payment.succeeded_at = transitioned_at
            payment.updated_at = transitioned_at
            order.status = "completed"
            order.updated_at = transitioned_at
            self._audit(payment, event_type, previous, payment.status, None)
            self._emit(payment, "payment.succeeded", {"order_id": str(order.id)})
            self._outbox.append(
                organization_id=payment.organization_id,
                aggregate_type="order",
                aggregate_id=order.id,
                event_type="order.completed",
                payload={"payment_id": str(payment.id)},
            )
        elif event_type == "payment.failed" and payment.status in {"pending", "failed"}:
            payment.status = "failed"
            payment.failure_code = "sandbox_declined"
            payment.updated_at = datetime.now(UTC)
            self._audit(payment, event_type, previous, payment.status, None)
            self._emit(
                payment,
                "payment.failed",
                {"failure_code": payment.failure_code or "unknown"},
            )
        else:
            self._audit(payment, f"{event_type}.ignored", previous, payment.status, None)

    async def _apply_refund_event(
        self, payment: PaymentIntent, refund: PaymentRefund, event_type: str
    ) -> None:
        previous = refund.status
        if event_type == "refund.succeeded" and refund.status in {"pending", "failed"}:
            transitioned_at = datetime.now(UTC)
            refund.status = "succeeded"
            refund.failure_code = None
            refund.succeeded_at = transitioned_at
            refund.updated_at = transitioned_at
            await self._session.flush()
            total = await self._repository.succeeded_refund_total(
                payment.organization_id, payment.id
            )
            payment_previous = payment.status
            if total >= payment.amount:
                payment.status = "refunded"
                payment.updated_at = transitioned_at
            self._audit(
                payment,
                event_type,
                payment_previous,
                payment.status,
                None,
                {"refund_id": str(refund.id), "refund_status": refund.status},
            )
            self._emit(
                payment,
                "payment.refund.succeeded",
                {"refund_id": str(refund.id), "amount": str(refund.amount)},
            )
        elif event_type == "refund.failed" and refund.status in {"pending", "failed"}:
            refund.status = "failed"
            refund.failure_code = "sandbox_refund_failed"
            refund.updated_at = datetime.now(UTC)
            self._audit(
                payment,
                event_type,
                payment.status,
                payment.status,
                None,
                {"refund_id": str(refund.id), "previous_refund_status": previous},
            )
            self._emit(
                payment,
                "payment.refund.failed",
                {"refund_id": str(refund.id), "failure_code": refund.failure_code or "unknown"},
            )
        else:
            self._audit(
                payment,
                f"{event_type}.ignored",
                payment.status,
                payment.status,
                None,
                {"refund_id": str(refund.id)},
            )

    def _record_event(
        self,
        event: WebhookEvent,
        raw_body: bytes,
        *,
        payment_id: UUID,
        refund_id: UUID | None = None,
    ) -> None:
        self._repository.add(
            PaymentWebhookEvent(
                provider=self._provider.name,
                event_id=event.event_id,
                event_type=event.type,
                payload_digest=hashlib.sha256(raw_body).hexdigest(),
                payment_id=payment_id,
                refund_id=refund_id,
            )
        )

    def _audit(
        self,
        payment: PaymentIntent,
        event_type: str,
        previous_status: str | None,
        new_status: str,
        actor_user_id: UUID | None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._repository.add(
            PaymentAuditLog(
                organization_id=payment.organization_id,
                payment_id=payment.id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                actor_user_id=actor_user_id,
                details=details or {},
            )
        )

    def _emit(self, payment: PaymentIntent, event_type: str, payload: dict[str, object]) -> None:
        self._outbox.append(
            organization_id=payment.organization_id,
            aggregate_type="payment",
            aggregate_id=payment.id,
            event_type=event_type,
            payload=payload,
        )

    @staticmethod
    def _replay_intent(payment: PaymentIntent, fingerprint: str) -> tuple[PaymentIntent, bool]:
        if payment.request_fingerprint != fingerprint:
            raise PaymentConflictError
        return payment, True

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        payload = json.dumps([str(part) for part in parts], separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _authorize(context: TenantContext, permission: Permission) -> None:
        if not has_permission(context.role, permission):
            raise TenantAccessDeniedError
