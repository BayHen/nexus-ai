"""Sandbox payment provider adapter with HMAC-signed events."""

import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4

from nexus.modules.payments.domain import (
    PaymentOutcome,
    ProviderIntent,
    ProviderRefund,
    RefundOutcome,
)


class SandboxPaymentProvider:
    """Generate fake provider tokens; never accepts or stores card data."""

    name = "sandbox"

    def __init__(self, webhook_secret: str) -> None:
        if len(webhook_secret) < 32:
            raise ValueError("Payment webhook secret must contain at least 32 characters")
        self._secret = webhook_secret.encode()

    async def create_intent(
        self, *, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderIntent:
        del amount, currency
        token = hashlib.sha256(f"payment:{idempotency_key}".encode()).hexdigest()[:32]
        return ProviderIntent(id=f"pi_sandbox_{token}", status="pending")

    async def create_refund(
        self, *, payment_intent_id: str, amount: Decimal, idempotency_key: str
    ) -> ProviderRefund:
        del amount
        token = hashlib.sha256(
            f"refund:{payment_intent_id}:{idempotency_key}".encode()
        ).hexdigest()[:32]
        return ProviderRefund(id=f"re_sandbox_{token}", status="pending")

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign_webhook(body), signature)

    def sign_webhook(self, body: bytes) -> str:
        return hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    def build_payment_event(self, provider_intent_id: str, outcome: PaymentOutcome) -> bytes:
        return self._event(f"payment.{outcome}", provider_intent_id=provider_intent_id)

    def build_refund_event(self, provider_refund_id: str, outcome: RefundOutcome) -> bytes:
        return self._event(f"refund.{outcome}", provider_refund_id=provider_refund_id)

    @staticmethod
    def _event(event_type: str, **data: str) -> bytes:
        return json.dumps(
            {"event_id": f"evt_sandbox_{uuid4().hex}", "type": event_type, "data": data},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
