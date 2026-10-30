"""Concurrent and failure-oriented inventory integration tests."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.inventory.models import StockMovement
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def inventory_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def inventory_client(inventory_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=inventory_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(inventory_database_url, 3)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201
    payload = cast(dict[str, Any], response.json())
    return str(payload["tokens"]["access_token"]), str(payload["user"]["id"])


def auth(token: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def setup_catalog(client: AsyncClient, token: str, slug: str) -> tuple[str, str, str]:
    organization = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Inventory {slug}", "slug": slug},
    )
    branch = await client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": f"Branch {slug}", "slug": f"branch-{slug}"},
    )
    product = await client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": f"Product {slug}", "price": "10.0000", "status": "active"},
    )
    assert organization.status_code == branch.status_code == product.status_code == 201
    return organization.json()["id"], branch.json()["id"], product.json()["id"]


async def create_stock(
    client: AsyncClient, token: str, branch_id: str, product_id: str, threshold: str = "2"
) -> None:
    response = await client.post(
        "/api/v1/inventory/stocks",
        headers=auth(token),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "low_stock_threshold": threshold,
        },
    )
    assert response.status_code == 201, response.text


async def adjust(
    client: AsyncClient,
    token: str,
    branch_id: str,
    product_id: str,
    delta: str,
    key: str,
) -> Response:
    return await client.post(
        "/api/v1/inventory/adjustments",
        headers=auth(token, key),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "quantity_delta": delta,
            "reason": "integration adjustment",
            "reference": "TASK-12",
        },
    )


async def test_concurrent_adjustments_cannot_oversell(inventory_client: AsyncClient) -> None:
    token, _ = await register(inventory_client, "concurrent@example.com")
    _, branch_id, product_id = await setup_catalog(inventory_client, token, "concurrent")
    await create_stock(inventory_client, token, branch_id, product_id)
    assert (
        await adjust(inventory_client, token, branch_id, product_id, "10", "seed")
    ).status_code == 201

    results = await asyncio.gather(
        adjust(inventory_client, token, branch_id, product_id, "-7", "concurrent-a"),
        adjust(inventory_client, token, branch_id, product_id, "-7", "concurrent-b"),
    )
    assert sorted(response.status_code for response in results) == [201, 409]
    stock = await inventory_client.get(
        f"/api/v1/inventory/stocks?branch_id={branch_id}&product_id={product_id}",
        headers=auth(token),
    )
    assert stock.json()["items"][0]["quantity"] == "3.0000"
    movements = await inventory_client.get("/api/v1/inventory/movements", headers=auth(token))
    assert movements.json()["total"] == 2


async def test_idempotency_replay_and_payload_conflict(
    inventory_client: AsyncClient, inventory_database_url: str
) -> None:
    token, _ = await register(inventory_client, "idempotency@example.com")
    _, branch_id, product_id = await setup_catalog(inventory_client, token, "idempotency")
    await create_stock(inventory_client, token, branch_id, product_id)
    first = await adjust(inventory_client, token, branch_id, product_id, "5", "same-key")
    replay = await adjust(inventory_client, token, branch_id, product_id, "5", "same-key")
    conflict = await adjust(inventory_client, token, branch_id, product_id, "6", "same-key")
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert replay.json()["replayed"] is True
    assert conflict.status_code == 409
    stock = await inventory_client.get("/api/v1/inventory/stocks", headers=auth(token))
    assert stock.json()["items"][0]["quantity"] == "5.0000"
    manager = DatabaseManager(inventory_database_url, 3)
    with pytest.raises(DBAPIError, match="inventory movements are immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(StockMovement)
                .where(StockMovement.id == UUID(first.json()["id"]))
                .values(reason="tampered")
            )
    await manager.dispose()


async def test_transfer_is_atomic_on_failure_and_reports_low_stock(
    inventory_client: AsyncClient,
) -> None:
    token, _ = await register(inventory_client, "transfer@example.com")
    _, source_id, product_id = await setup_catalog(inventory_client, token, "transfer")
    destination = await inventory_client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": "Destination", "slug": "destination"},
    )
    destination_id = destination.json()["id"]
    await create_stock(inventory_client, token, source_id, product_id, "2")
    await create_stock(inventory_client, token, destination_id, product_id, "1")
    await adjust(inventory_client, token, source_id, product_id, "5", "transfer-seed")

    failed = await inventory_client.post(
        "/api/v1/inventory/transfers",
        headers=auth(token, "failed-transfer"),
        json={
            "source_branch_id": source_id,
            "destination_branch_id": destination_id,
            "product_id": product_id,
            "quantity": "8",
            "reason": "must rollback",
        },
    )
    assert failed.status_code == 409
    before = await inventory_client.get("/api/v1/inventory/stocks", headers=auth(token))
    quantities = {item["branch_id"]: item["quantity"] for item in before.json()["items"]}
    assert quantities == {source_id: "5.0000", destination_id: "0.0000"}

    success = await inventory_client.post(
        "/api/v1/inventory/transfers",
        headers=auth(token, "successful-transfer"),
        json={
            "source_branch_id": source_id,
            "destination_branch_id": destination_id,
            "product_id": product_id,
            "quantity": "3",
            "reason": "replenishment",
            "reference": "MOVE-1",
        },
    )
    assert success.status_code == 201
    assert success.json()["source_quantity_after"] == "2.0000"
    assert success.json()["destination_quantity_after"] == "3.0000"
    low = await inventory_client.get("/api/v1/inventory/stocks?low_stock=true", headers=auth(token))
    assert low.json()["total"] == 1
    assert low.json()["items"][0]["branch_id"] == source_id


async def test_negative_policy_authorization_and_tenant_isolation(
    inventory_client: AsyncClient,
) -> None:
    owner_token, _ = await register(inventory_client, "inventory-owner@example.com")
    other_token, _ = await register(inventory_client, "inventory-other@example.com")
    viewer_token, _ = await register(inventory_client, "inventory-viewer@example.com")
    organization_id, branch_id, product_id = await setup_catalog(
        inventory_client, owner_token, "inventory-owner"
    )
    _, other_branch, other_product = await setup_catalog(
        inventory_client, other_token, "inventory-other"
    )
    await create_stock(inventory_client, owner_token, branch_id, product_id)
    await create_stock(inventory_client, other_token, other_branch, other_product)

    cross_tenant = await inventory_client.post(
        "/api/v1/inventory/stocks",
        headers=auth(owner_token),
        json={"branch_id": other_branch, "product_id": other_product},
    )
    assert cross_tenant.status_code == 404

    await inventory_client.post(
        "/api/v1/organizations/current/invitations",
        headers=auth(owner_token),
        json={"email": "inventory-viewer@example.com", "role": "viewer"},
    )
    await inventory_client.post(
        f"/api/v1/organizations/{organization_id}/invitations/accept",
        headers=auth(viewer_token),
    )
    assert (
        await inventory_client.get("/api/v1/inventory/stocks", headers=auth(viewer_token))
    ).status_code == 200
    assert (
        await adjust(inventory_client, viewer_token, branch_id, product_id, "1", "viewer-denied")
    ).status_code == 403

    enabled = await inventory_client.patch(
        "/api/v1/inventory/policy",
        headers=auth(owner_token),
        json={"allow_negative_stock": True},
    )
    assert enabled.status_code == 200
    negative = await adjust(
        inventory_client, owner_token, branch_id, product_id, "-2", "negative-allowed"
    )
    assert negative.status_code == 201
    blocked_disable = await inventory_client.patch(
        "/api/v1/inventory/policy",
        headers=auth(owner_token),
        json={"allow_negative_stock": False},
    )
    assert blocked_disable.status_code == 409
