"""Payment API and webhook schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictPaymentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentIntentCreateRequest(StrictPaymentModel):
    order_id: UUID
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class PaymentIntentResponse(BaseModel):
    id: UUID
    order_id: UUID
    provider: str
    provider_intent_id: str
    amount: Decimal
    currency: str
    status: Literal["pending", "succeeded", "failed", "refunded"]
    failure_code: str | None
    succeeded_at: datetime | None
    created_at: datetime
    updated_at: datetime
    replayed: bool = False


class RefundCreateRequest(StrictPaymentModel):
    amount: Decimal = Field(gt=0, max_digits=19, decimal_places=4)
    reason: str = Field(min_length=3, max_length=200)


class RefundResponse(BaseModel):
    id: UUID
    payment_id: UUID
    provider_refund_id: str
    amount: Decimal
    status: Literal["pending", "succeeded", "failed"]
    reason: str
    failure_code: str | None
    succeeded_at: datetime | None
    created_at: datetime
    replayed: bool = False


class SandboxPaymentSimulationRequest(StrictPaymentModel):
    outcome: Literal["succeeded", "failed"]


class WebhookEventData(StrictPaymentModel):
    provider_intent_id: str | None = None
    provider_refund_id: str | None = None


class WebhookEvent(StrictPaymentModel):
    event_id: str = Field(min_length=1, max_length=128)
    type: Literal["payment.succeeded", "payment.failed", "refund.succeeded", "refund.failed"]
    data: WebhookEventData


class WebhookResponse(BaseModel):
    accepted: bool = True
    duplicate: bool = False


class PaymentAuditResponse(BaseModel):
    id: UUID
    event_type: str
    previous_status: str | None
    new_status: str
    actor_user_id: UUID | None
    details: dict[str, object]
    created_at: datetime
