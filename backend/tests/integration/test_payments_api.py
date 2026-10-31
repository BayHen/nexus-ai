"""Sandbox payment security, idempotency, webhook, refund, and audit tests."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.payments.models import PaymentAuditLog, PaymentIntent
from nexus.modules.payments.provider import SandboxPaymentProvider
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"
WEBHOOK_SECRET = "task15-test-webhook-secret-at-least-32-characters"


@pytest.fixture
def payment_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def payment_client(payment_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=payment_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        payment_webhook_secret=WEBHOOK_SECRET,
        _env_file=None,
    )
    manager = DatabaseManager(payment_database_url, 5)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["tokens"]["access_token"])


def auth(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


async def setup_confirmed_order(
    client: AsyncClient, token: str, slug: str, *, quantity: str = "2", price: str = "10.0000"
) -> dict[str, Any]:
    organization = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Payments {slug}", "slug": slug},
    )
    branch = await client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": f"Branch {slug}", "slug": f"branch-{slug}"},
    )
    product = await client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": f"Product {slug}", "price": price, "status": "active"},
    )
    assert organization.status_code == branch.status_code == product.status_code == 201
    branch_id = str(branch.json()["id"])
    product_id = str(product.json()["id"])
    stock = await client.post(
        "/api/v1/inventory/stocks",
        headers=auth(token),
        json={"branch_id": branch_id, "product_id": product_id, "low_stock_threshold": "0"},
    )
    seed = await client.post(
        "/api/v1/inventory/adjustments",
        headers=auth(token, f"seed-{slug}"),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "quantity_delta": "10",
            "reason": "Payment test seed",
        },
    )
    order = await client.post("/api/v1/orders", headers=auth(token))
    item = await client.post(
        f"/api/v1/orders/{order.json()['id']}/items",
        headers=auth(token),
        json={"product_id": product_id, "branch_id": branch_id, "quantity": quantity},
    )
    confirmed = await client.post(
        f"/api/v1/orders/{order.json()['id']}/confirm", headers=auth(token)
    )
    assert stock.status_code == seed.status_code == item.status_code == 201
    assert order.status_code == 201 and confirmed.status_code == 200
    return {
        "organization_id": str(organization.json()["id"]),
        "order_id": str(order.json()["id"]),
        "product_id": product_id,
        "amount": confirmed.json()["total_amount"],
    }


async def create_intent(client: AsyncClient, token: str, order_id: str, key: str) -> Response:
    return await client.post(
        "/api/v1/payments/intents",
        headers=auth(token, key),
        json={"order_id": order_id, "currency": "USD"},
    )


def signed_payment_event(provider_intent_id: str, outcome: str) -> tuple[bytes, str]:
    provider = SandboxPaymentProvider(WEBHOOK_SECRET)
    raw = provider.build_payment_event(provider_intent_id, cast(Any, outcome))
    return raw, provider.sign_webhook(raw)


async def send_webhook(client: AsyncClient, raw: bytes, signature: str) -> Response:
    return await client.post(
        "/api/v1/payments/webhooks/sandbox",
        content=raw,
        headers={"Content-Type": "application/json", "X-Payment-Signature": signature},
    )


async def test_intent_idempotency_concurrent_webhook_and_order_completion_once(
    payment_client: AsyncClient,
) -> None:
    token = await register(payment_client, "payment-success@example.com")
    setup = await setup_confirmed_order(payment_client, token, "payment-success")
    first = await create_intent(payment_client, token, setup["order_id"], "intent-key")
    replay = await create_intent(payment_client, token, setup["order_id"], "intent-key")
    second_key = await create_intent(payment_client, token, setup["order_id"], "other-key")
    card_payload = await payment_client.post(
        "/api/v1/payments/intents",
        headers=auth(token, "card-data-must-be-rejected"),
        json={
            "order_id": setup["order_id"],
            "currency": "USD",
            "card_number": "4242424242424242",
        },
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert replay.json()["replayed"] is True
    assert first.json()["amount"] == setup["amount"]
    assert second_key.status_code == 409
    assert card_payload.status_code == 422

    raw, signature = signed_payment_event(first.json()["provider_intent_id"], "succeeded")
    invalid = await send_webhook(payment_client, raw, "0" * 64)
    assert invalid.status_code == 401
    results = await asyncio.gather(
        send_webhook(payment_client, raw, signature),
        send_webhook(payment_client, raw, signature),
    )
    assert sorted(result.status_code for result in results) == [200, 200]
    assert sorted(result.json()["duplicate"] for result in results) == [False, True]
    mismatched_payload = json.loads(raw)
    mismatched_payload["type"] = "payment.failed"
    mismatched_raw = json.dumps(mismatched_payload, separators=(",", ":"), sort_keys=True).encode()
    mismatch_signature = SandboxPaymentProvider(WEBHOOK_SECRET).sign_webhook(mismatched_raw)
    assert (
        await send_webhook(payment_client, mismatched_raw, mismatch_signature)
    ).status_code == 409

    payment = await payment_client.get(
        f"/api/v1/payments/intents/{first.json()['id']}", headers=auth(token)
    )
    order = await payment_client.get(f"/api/v1/orders/{setup['order_id']}", headers=auth(token))
    audit = await payment_client.get(
        f"/api/v1/payments/intents/{first.json()['id']}/audit", headers=auth(token)
    )
    assert payment.json()["status"] == "succeeded"
    assert order.json()["status"] == "completed"
    assert [entry["event_type"] for entry in audit.json()] == [
        "payment_intent_created",
        "payment.succeeded",
    ]


async def test_failed_payment_can_retry_successfully_without_new_charge(
    payment_client: AsyncClient,
) -> None:
    token = await register(payment_client, "payment-retry@example.com")
    setup = await setup_confirmed_order(payment_client, token, "payment-retry")
    intent = await create_intent(payment_client, token, setup["order_id"], "retry-key")
    failed_raw, failed_signature = signed_payment_event(
        intent.json()["provider_intent_id"], "failed"
    )
    assert (await send_webhook(payment_client, failed_raw, failed_signature)).status_code == 200
    failed = await payment_client.get(
        f"/api/v1/payments/intents/{intent.json()['id']}", headers=auth(token)
    )
    order = await payment_client.get(f"/api/v1/orders/{setup['order_id']}", headers=auth(token))
    assert failed.json()["status"] == "failed"
    assert order.json()["status"] == "confirmed"

    success_raw, success_signature = signed_payment_event(
        intent.json()["provider_intent_id"], "succeeded"
    )
    assert (await send_webhook(payment_client, success_raw, success_signature)).status_code == 200
    succeeded = await payment_client.get(
        f"/api/v1/payments/intents/{intent.json()['id']}", headers=auth(token)
    )
    assert succeeded.json()["status"] == "succeeded"
    assert succeeded.json()["provider_intent_id"] == intent.json()["provider_intent_id"]


async def test_ineligible_order_rolls_back_success_webhook(payment_client: AsyncClient) -> None:
    token = await register(payment_client, "payment-rollback@example.com")
    setup = await setup_confirmed_order(payment_client, token, "payment-rollback")
    intent = await create_intent(payment_client, token, setup["order_id"], "rollback-key")
    cancelled = await payment_client.post(
        f"/api/v1/orders/{setup['order_id']}/cancel", headers=auth(token)
    )
    assert cancelled.status_code == 200
    raw, signature = signed_payment_event(intent.json()["provider_intent_id"], "succeeded")
    rejected = await send_webhook(payment_client, raw, signature)
    assert rejected.status_code == 409
    payment = await payment_client.get(
        f"/api/v1/payments/intents/{intent.json()['id']}", headers=auth(token)
    )
    assert payment.json()["status"] == "pending"
    assert cancelled.json()["status"] == "cancelled"


async def test_refund_audit_immutability_and_cross_tenant_isolation(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    alice_token = await register(payment_client, "payment-alice@example.com")
    bob_token = await register(payment_client, "payment-bob@example.com")
    alice = await setup_confirmed_order(payment_client, alice_token, "payment-alice")
    await setup_confirmed_order(payment_client, bob_token, "payment-bob")
    intent = await create_intent(payment_client, alice_token, alice["order_id"], "alice-intent")
    raw, signature = signed_payment_event(intent.json()["provider_intent_id"], "succeeded")
    assert (await send_webhook(payment_client, raw, signature)).status_code == 200

    cross_tenant = await payment_client.get(
        f"/api/v1/payments/intents/{intent.json()['id']}", headers=auth(bob_token)
    )
    assert cross_tenant.status_code == 404
    refund = await payment_client.post(
        f"/api/v1/payments/intents/{intent.json()['id']}/refunds",
        headers=auth(alice_token, "refund-key"),
        json={"amount": alice["amount"], "reason": "Customer request"},
    )
    replay = await payment_client.post(
        f"/api/v1/payments/intents/{intent.json()['id']}/refunds",
        headers=auth(alice_token, "refund-key"),
        json={"amount": alice["amount"], "reason": "Customer request"},
    )
    over_refund = await payment_client.post(
        f"/api/v1/payments/intents/{intent.json()['id']}/refunds",
        headers=auth(alice_token, "refund-over"),
        json={"amount": "1.0000", "reason": "Too much"},
    )
    assert refund.status_code == replay.status_code == 201
    assert refund.json()["id"] == replay.json()["id"]
    assert replay.json()["replayed"] is True
    assert over_refund.status_code == 409
    simulated = await payment_client.post(
        f"/api/v1/payments/sandbox/refunds/{refund.json()['id']}/simulate",
        headers=auth(alice_token),
        json={"outcome": "succeeded"},
    )
    assert simulated.status_code == 200
    payment = await payment_client.get(
        f"/api/v1/payments/intents/{intent.json()['id']}", headers=auth(alice_token)
    )
    assert payment.json()["status"] == "refunded"

    manager = DatabaseManager(payment_database_url, 2)
    with pytest.raises(DBAPIError, match="financial records cannot be deleted"):
        async with manager.transaction() as session:
            await session.execute(
                delete(PaymentIntent).where(PaymentIntent.id == UUID(intent.json()["id"]))
            )
    with pytest.raises(DBAPIError, match="payment history is immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(PaymentAuditLog)
                .where(PaymentAuditLog.payment_id == UUID(intent.json()["id"]))
                .values(event_type="tampered")
            )
    await manager.dispose()
