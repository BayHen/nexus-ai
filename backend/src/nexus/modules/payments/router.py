"""Secure payment, refund, sandbox simulation, and webhook APIs."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import TenantAccessDeniedError
from nexus.modules.payments.domain import PaymentConflictError, PaymentNotFoundError
from nexus.modules.payments.models import PaymentAuditLog, PaymentIntent, PaymentRefund
from nexus.modules.payments.provider import SandboxPaymentProvider
from nexus.modules.payments.schemas import (
    PaymentAuditResponse,
    PaymentIntentCreateRequest,
    PaymentIntentResponse,
    RefundCreateRequest,
    RefundResponse,
    SandboxPaymentSimulationRequest,
    WebhookEvent,
    WebhookResponse,
)
from nexus.modules.payments.service import PaymentService
from nexus.platform.api.errors import ApplicationError

router = APIRouter(prefix="/payments", tags=["payments"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


SettingsDependency = Annotated[Settings, Depends(get_app_settings)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def provider(settings: Settings) -> SandboxPaymentProvider:
    secret = settings.payment_webhook_secret
    if secret is None:
        raise ApplicationError(
            code="payment_not_configured",
            message="The sandbox payment provider is not configured.",
            status_code=503,
        )
    return SandboxPaymentProvider(secret.get_secret_value())


def require_simulation_environment(settings: Settings) -> None:
    if settings.environment not in {"development", "test"}:
        raise ApplicationError(
            code="sandbox_simulation_disabled",
            message="Sandbox simulation is disabled in this environment.",
            status_code=404,
        )


def intent_response(payment: PaymentIntent, replayed: bool = False) -> PaymentIntentResponse:
    return PaymentIntentResponse(
        id=payment.id,
        order_id=payment.order_id,
        provider=payment.provider,
        provider_intent_id=payment.provider_intent_id,
        amount=payment.amount,
        currency=payment.currency,
        status=cast(Literal["pending", "succeeded", "failed", "refunded"], payment.status),
        failure_code=payment.failure_code,
        succeeded_at=payment.succeeded_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        replayed=replayed,
    )


def refund_response(refund: PaymentRefund, replayed: bool = False) -> RefundResponse:
    return RefundResponse(
        id=refund.id,
        payment_id=refund.payment_id,
        provider_refund_id=refund.provider_refund_id,
        amount=refund.amount,
        status=cast(Literal["pending", "succeeded", "failed"], refund.status),
        reason=refund.reason,
        failure_code=refund.failure_code,
        succeeded_at=refund.succeeded_at,
        created_at=refund.created_at,
        replayed=replayed,
    )


def audit_response(audit: PaymentAuditLog) -> PaymentAuditResponse:
    return PaymentAuditResponse(
        id=audit.id,
        event_type=audit.event_type,
        previous_status=audit.previous_status,
        new_status=audit.new_status,
        actor_user_id=audit.actor_user_id,
        details=audit.details,
        created_at=audit.created_at,
    )


def translate(exc: Exception) -> ApplicationError:
    if isinstance(exc, PaymentNotFoundError):
        return ApplicationError(
            code="resource_not_found",
            message="The requested payment resource was not found.",
            status_code=404,
        )
    if isinstance(exc, TenantAccessDeniedError):
        return ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=403,
        )
    return ApplicationError(
        code="payment_conflict",
        message="The payment operation conflicts with its current state.",
        status_code=409,
    )


@router.post("/intents", response_model=PaymentIntentResponse, status_code=201)
async def create_payment_intent(
    body: PaymentIntentCreateRequest,
    idempotency_key: IdempotencyKey,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> PaymentIntentResponse:
    try:
        payment, replayed = await PaymentService(session, provider(settings)).create_intent(
            context,
            order_id=body.order_id,
            currency=body.currency,
            idempotency_key=idempotency_key,
        )
    except (
        PaymentNotFoundError,
        PaymentConflictError,
        TenantAccessDeniedError,
        IntegrityError,
    ) as exc:
        raise translate(exc) from exc
    return intent_response(payment, replayed)


@router.get("/intents/{payment_id}", response_model=PaymentIntentResponse)
async def get_payment_intent(
    payment_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> PaymentIntentResponse:
    try:
        payment = await PaymentService(session, provider(settings)).get_intent(context, payment_id)
    except (PaymentNotFoundError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return intent_response(payment)


@router.post("/intents/{payment_id}/refunds", response_model=RefundResponse, status_code=201)
async def create_refund(
    payment_id: UUID,
    body: RefundCreateRequest,
    idempotency_key: IdempotencyKey,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> RefundResponse:
    try:
        refund, replayed = await PaymentService(session, provider(settings)).create_refund(
            context,
            payment_id,
            amount=body.amount,
            reason=body.reason,
            idempotency_key=idempotency_key,
        )
    except (
        PaymentNotFoundError,
        PaymentConflictError,
        TenantAccessDeniedError,
        IntegrityError,
    ) as exc:
        raise translate(exc) from exc
    return refund_response(refund, replayed)


@router.get("/intents/{payment_id}/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund(
    payment_id: UUID,
    refund_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> RefundResponse:
    try:
        refund = await PaymentService(session, provider(settings)).get_refund(
            context, payment_id, refund_id
        )
    except (PaymentNotFoundError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return refund_response(refund)


@router.get("/intents/{payment_id}/audit", response_model=list[PaymentAuditResponse])
async def list_payment_audit(
    payment_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> list[PaymentAuditResponse]:
    try:
        items = await PaymentService(session, provider(settings)).audits(context, payment_id)
    except (PaymentNotFoundError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return [audit_response(item) for item in items]


@router.post("/sandbox/intents/{payment_id}/simulate", response_model=WebhookResponse)
async def simulate_payment(
    payment_id: UUID,
    body: SandboxPaymentSimulationRequest,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> WebhookResponse:
    require_simulation_environment(settings)
    sandbox = provider(settings)
    service = PaymentService(session, sandbox)
    try:
        payment = await service.get_intent_for_simulation(context, payment_id)
        raw = sandbox.build_payment_event(payment.provider_intent_id, body.outcome)
        if not sandbox.verify_webhook(raw, sandbox.sign_webhook(raw)):
            raise PaymentConflictError
        event = WebhookEvent.model_validate_json(raw)
        _, _, duplicate = await service.process_webhook(event, raw)
    except (PaymentNotFoundError, PaymentConflictError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return WebhookResponse(duplicate=duplicate)


@router.post("/sandbox/refunds/{refund_id}/simulate", response_model=WebhookResponse)
async def simulate_refund(
    refund_id: UUID,
    body: SandboxPaymentSimulationRequest,
    session: SessionDependency,
    context: TenantContextDependency,
    settings: SettingsDependency,
) -> WebhookResponse:
    require_simulation_environment(settings)
    sandbox = provider(settings)
    service = PaymentService(session, sandbox)
    try:
        refund = await service.get_refund_by_id(context, refund_id)
        raw = sandbox.build_refund_event(refund.provider_refund_id, body.outcome)
        if not sandbox.verify_webhook(raw, sandbox.sign_webhook(raw)):
            raise PaymentConflictError
        event = WebhookEvent.model_validate_json(raw)
        _, _, duplicate = await service.process_webhook(event, raw)
    except (PaymentNotFoundError, PaymentConflictError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return WebhookResponse(duplicate=duplicate)


@router.post("/webhooks/sandbox", response_model=WebhookResponse)
async def sandbox_webhook(
    request: Request,
    session: SessionDependency,
    settings: SettingsDependency,
    signature: Annotated[str, Header(alias="X-Payment-Signature")],
) -> WebhookResponse:
    sandbox = provider(settings)
    raw = await request.body()
    if not sandbox.verify_webhook(raw, signature):
        raise ApplicationError(
            code="invalid_webhook_signature",
            message="The webhook signature is invalid.",
            status_code=401,
        )
    try:
        event = WebhookEvent.model_validate_json(raw)
        _, _, duplicate = await PaymentService(session, sandbox).process_webhook(event, raw)
    except ValidationError as exc:
        raise ApplicationError(
            code="invalid_webhook_payload",
            message="The webhook payload is invalid.",
            status_code=422,
        ) from exc
    except (PaymentNotFoundError, PaymentConflictError, IntegrityError) as exc:
        raise translate(exc) from exc
    return WebhookResponse(duplicate=duplicate)
