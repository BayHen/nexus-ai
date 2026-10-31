"""Transactional outbox, recovery, idempotent consumer, and reconciliation tests."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from nexus.modules.orders.models import Order
from nexus.platform.database.manager import DatabaseManager
from nexus.platform.reliability.models import BusinessAuditEvent, InboxReceipt, OutboxEvent
from nexus.platform.reliability.service import OutboxProcessor, OutboxWriter
from tests.integration.test_payments_api import (
    auth,
    register,
    send_webhook,
    setup_confirmed_order,
    signed_payment_event,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
pytest_plugins = ("tests.integration.test_payments_api",)


async def test_outbox_is_atomic_correlated_immutable_and_tenant_scoped(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    alice_token = await register(payment_client, "reliability-alice@example.com")
    bob_token = await register(payment_client, "reliability-bob@example.com")
    alice = await setup_confirmed_order(payment_client, alice_token, "reliability-alice")
    await setup_confirmed_order(payment_client, bob_token, "reliability-bob")
    headers = {
        **auth(alice_token, "reliability-intent"),
        "X-Request-ID": "corr-task16-intent",
    }
    intent = await payment_client.post(
        "/api/v1/payments/intents",
        headers=headers,
        json={"order_id": alice["order_id"], "currency": "USD"},
    )
    assert intent.status_code == 201

    alice_outbox = await payment_client.get("/api/v1/reliability/outbox", headers=auth(alice_token))
    bob_outbox = await payment_client.get("/api/v1/reliability/outbox", headers=auth(bob_token))
    assert alice_outbox.status_code == bob_outbox.status_code == 200
    correlated = [
        item for item in alice_outbox.json() if item["event_type"] == "payment.intent.created"
    ]
    assert len(correlated) == 1
    assert correlated[0]["correlation_id"] == "corr-task16-intent"
    assert set(item["id"] for item in alice_outbox.json()).isdisjoint(
        item["id"] for item in bob_outbox.json()
    )

    manager = DatabaseManager(payment_database_url, 2)
    with pytest.raises(RuntimeError, match="force transaction rollback"):
        async with manager.transaction() as session:
            OutboxWriter(session, "corr-rollback").append(
                organization_id=UUID(alice["organization_id"]),
                aggregate_type="payment",
                aggregate_id=UUID(intent.json()["id"]),
                event_type="payment.must_not_commit",
                payload={},
            )
            raise RuntimeError("force transaction rollback")
    async with manager.transaction() as session:
        rolled_back = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "payment.must_not_commit")
        )
        assert rolled_back == 0
    with pytest.raises(DBAPIError, match="reliability history is immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(BusinessAuditEvent)
                .where(BusinessAuditEvent.organization_id == UUID(alice["organization_id"]))
                .values(event_type="tampered")
            )
    await manager.dispose()


async def test_worker_crash_retry_idempotency_and_out_of_order_delivery(
    payment_client: AsyncClient,
    payment_database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = await register(payment_client, "reliability-worker@example.com")
    setup = await setup_confirmed_order(payment_client, token, "reliability-worker")
    caplog.set_level(logging.INFO, logger="nexus.platform.reliability.service")
    reliability_logger = logging.getLogger("nexus.platform.reliability.service")
    reliability_logger.disabled = False
    reliability_logger.addHandler(caplog.handler)
    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        writer = OutboxWriter(session, "corr-worker")
        first = writer.append(
            organization_id=UUID(setup["organization_id"]),
            aggregate_type="payment",
            aggregate_id=UUID(setup["order_id"]),
            event_type="test.first",
            payload={"sequence": 1},
        )
        second = writer.append(
            organization_id=UUID(setup["organization_id"]),
            aggregate_type="payment",
            aggregate_id=UUID(setup["order_id"]),
            event_type="test.second",
            payload={"sequence": 2},
        )
        dead = writer.append(
            organization_id=UUID(setup["organization_id"]),
            aggregate_type="payment",
            aggregate_id=UUID(setup["order_id"]),
            event_type="test.dead",
            payload={"must_not_be_logged": "sensitive-example"},
            max_attempts=1,
        )
        await session.flush()
        first_id, second_id, dead_id = first.id, second.id, dead.id

    async with manager.transaction() as session:
        claimed = await OutboxProcessor(session).claim("crashed-worker", limit=100)
        assert {first_id, second_id, dead_id}.issubset(event.id for event in claimed)
    async with manager.transaction() as session:
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id.in_((first_id, second_id, dead_id)))
            .values(locked_at=datetime.now(UTC) - timedelta(minutes=5))
        )
    async with manager.transaction() as session:
        recovered = await OutboxProcessor(session).claim(
            "recovery-worker", limit=100, lease_seconds=60
        )
        assert {first_id, second_id, dead_id}.issubset(event.id for event in recovered)

    # Consume deliberately out of creation order; consumer state remains idempotent.
    async with manager.transaction() as session:
        processor = OutboxProcessor(session, base_retry_seconds=1)
        assert await processor.consume(second_id, worker_id="recovery-worker") is True
        assert (
            await processor.consume(dead_id, worker_id="recovery-worker", simulate_failure=True)
            is False
        )
    async with manager.transaction() as session:
        processor = OutboxProcessor(session, base_retry_seconds=1)
        assert (
            await processor.consume(first_id, worker_id="recovery-worker", simulate_failure=True)
            is False
        )
    async with manager.transaction() as session:
        failed = await session.get(OutboxEvent, first_id)
        assert failed is not None
        assert failed.status == "pending"
        assert failed.attempt_count == 1
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == first_id)
            .values(available_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    async with manager.transaction() as session:
        claimed = await OutboxProcessor(session).claim("retry-worker", limit=100)
        assert first_id in {event.id for event in claimed}
    async with manager.transaction() as session:
        processor = OutboxProcessor(session)
        assert await processor.consume(first_id, worker_id="retry-worker") is True
        # A redelivery after publish sees the durable inbox receipt and has no side effect.
        assert await processor.consume(first_id, worker_id="another-worker") is True
    async with manager.transaction() as session:
        receipt_count = await session.scalar(
            select(func.count()).select_from(InboxReceipt).where(InboxReceipt.event_id == first_id)
        )
        assert receipt_count == 1
        dead_event = await session.get(OutboxEvent, dead_id)
        assert dead_event is not None
        assert dead_event.status == "dead"
    reliability_records = [
        record for record in caplog.records if record.name == "nexus.platform.reliability.service"
    ]
    assert any(
        getattr(record, "correlation_id", None) == "corr-worker" for record in reliability_records
    )
    assert all(not hasattr(record, "payload") for record in reliability_records)
    reliability_logger.removeHandler(caplog.handler)
    await manager.dispose()


async def test_webhook_retry_and_reconciliation_detect_inconsistency(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    token = await register(payment_client, "reliability-reconcile@example.com")
    setup = await setup_confirmed_order(payment_client, token, "reliability-reconcile")
    intent = await payment_client.post(
        "/api/v1/payments/intents",
        headers=auth(token, "reconcile-intent"),
        json={"order_id": setup["order_id"], "currency": "USD"},
    )
    raw, signature = signed_payment_event(intent.json()["provider_intent_id"], "succeeded")
    first = await send_webhook(payment_client, raw, signature)
    retry = await send_webhook(payment_client, raw, signature)
    assert first.status_code == retry.status_code == 200
    assert first.json()["duplicate"] is False
    assert retry.json()["duplicate"] is True
    healthy = await payment_client.post("/api/v1/reliability/reconcile", headers=auth(token))
    assert healthy.status_code == 200
    assert healthy.json()["finding_count"] == 0

    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        await session.execute(
            update(Order).where(Order.id == UUID(setup["order_id"])).values(status="confirmed")
        )
    finding = await payment_client.post(
        "/api/v1/reliability/reconcile",
        headers={**auth(token), "X-Request-ID": "corr-reconciliation"},
    )
    listed = await payment_client.get("/api/v1/reliability/findings", headers=auth(token))
    assert finding.status_code == 200
    assert finding.json()["finding_count"] == 1
    assert listed.status_code == 200
    assert listed.json()[0]["finding_code"] == "paid_order_not_completed"
    assert listed.json()[0]["correlation_id"] == "corr-reconciliation"
    await manager.dispose()
