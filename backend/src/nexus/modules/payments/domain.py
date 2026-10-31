"""Payment contracts, value objects, and domain errors."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

PaymentOutcome = Literal["succeeded", "failed"]
RefundOutcome = Literal["succeeded", "failed"]


class PaymentNotFoundError(LookupError):
    """Raised when a tenant-scoped payment resource is unavailable."""


class PaymentConflictError(RuntimeError):
    """Raised when a payment state or idempotency invariant conflicts."""


class InvalidWebhookSignatureError(RuntimeError):
    """Raised when an inbound provider webhook is not authentic."""


@dataclass(frozen=True)
class ProviderIntent:
    id: str
    status: str


@dataclass(frozen=True)
class ProviderRefund:
    id: str
    status: str


class PaymentProvider(Protocol):
    """Port implemented by sandbox and future real payment adapters."""

    name: str

    async def create_intent(
        self, *, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderIntent: ...

    async def create_refund(
        self, *, payment_intent_id: str, amount: Decimal, idempotency_key: str
    ) -> ProviderRefund: ...

    def verify_webhook(self, body: bytes, signature: str) -> bool: ...

    def build_payment_event(self, provider_intent_id: str, outcome: PaymentOutcome) -> bytes: ...

    def build_refund_event(self, provider_refund_id: str, outcome: RefundOutcome) -> bytes: ...

    def sign_webhook(self, body: bytes) -> str: ...
