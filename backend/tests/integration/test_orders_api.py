"""Order lifecycle, inventory consistency, concurrency, and tenant isolation tests."""

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
from nexus.modules.orders.models import OrderItem
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def order_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def order_client(order_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=order_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(order_database_url, 5)
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


def auth(token: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def setup_tenant(client: AsyncClient, token: str, slug: str) -> tuple[str, str]:
    organization = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Orders {slug}", "slug": slug},
    )
    branch = await client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": f"Branch {slug}", "slug": f"branch-{slug}"},
    )
    assert organization.status_code == branch.status_code == 201
    return str(organization.json()["id"]), str(branch.json()["id"])


async def create_product(client: AsyncClient, token: str, name: str, price: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": name, "price": price, "status": "active"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def create_stock(
    client: AsyncClient, token: str, branch_id: str, product_id: str, quantity: str
) -> None:
    created = await client.post(
        "/api/v1/inventory/stocks",
        headers=auth(token),
        json={"branch_id": branch_id, "product_id": product_id, "low_stock_threshold": "0"},
    )
    assert created.status_code == 201, created.text
    seeded = await client.post(
        "/api/v1/inventory/adjustments",
        headers=auth(token, f"seed-{branch_id}-{product_id}"),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "quantity_delta": quantity,
            "reason": "Order test seed",
        },
    )
    assert seeded.status_code == 201, seeded.text


async def create_order(client: AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post("/api/v1/orders", headers=auth(token))
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def add_item(
    client: AsyncClient,
    token: str,
    order_id: str,
    product_id: str,
    branch_id: str,
    quantity: str,
) -> Response:
    return await client.post(
        f"/api/v1/orders/{order_id}/items",
        headers=auth(token),
        json={"product_id": product_id, "branch_id": branch_id, "quantity": quantity},
    )


async def stock_quantity(client: AsyncClient, token: str, product_id: str) -> str:
    response = await client.get(
        f"/api/v1/inventory/stocks?product_id={product_id}", headers=auth(token)
    )
    assert response.status_code == 200
    return str(response.json()["items"][0]["quantity"])


async def test_draft_items_server_totals_price_snapshot_confirm_cancel_and_history(
    order_client: AsyncClient, order_database_url: str
) -> None:
    token = await register(order_client, "order-lifecycle@example.com")
    _, branch_id = await setup_tenant(order_client, token, "order-lifecycle")
    product = await create_product(order_client, token, "Snapshot Product", "12.5000")
    await create_stock(order_client, token, branch_id, str(product["id"]), "10")
    order = await create_order(order_client, token)

    added = await add_item(
        order_client, token, str(order["id"]), str(product["id"]), branch_id, "2"
    )
    assert added.status_code == 201, added.text
    item = added.json()["items"][0]
    assert added.json()["total_amount"] == "25.0000"
    assert item["unit_price_snapshot"] == "12.5000"

    price_changed = await order_client.patch(
        f"/api/v1/products/{product['id']}",
        headers=auth(token),
        json={"price": "99.0000", "name": "Renamed Product"},
    )
    assert price_changed.status_code == 200
    updated = await order_client.patch(
        f"/api/v1/orders/{order['id']}/items/{item['id']}",
        headers=auth(token),
        json={"quantity": "3"},
    )
    assert updated.status_code == 200
    assert updated.json()["total_amount"] == "37.5000"
    assert updated.json()["items"][0]["product_name_snapshot"] == "Snapshot Product"
    assert updated.json()["items"][0]["unit_price_snapshot"] == "12.5000"

    confirmed = await order_client.post(
        f"/api/v1/orders/{order['id']}/confirm", headers=auth(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert await stock_quantity(order_client, token, str(product["id"])) == "7.0000"

    cancelled = await order_client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(token))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert await stock_quantity(order_client, token, str(product["id"])) == "10.0000"

    history = await order_client.get(
        "/api/v1/orders?status=cancelled&page=1&page_size=10", headers=auth(token)
    )
    dated_history = await order_client.get(
        "/api/v1/orders?created_from=2000-01-01T00:00:00Z&created_to=2100-01-01T00:00:00Z",
        headers=auth(token),
    )
    invalid_dates = await order_client.get(
        "/api/v1/orders?created_from=2100-01-01T00:00:00Z&created_to=2000-01-01T00:00:00Z",
        headers=auth(token),
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == order["id"]
    assert dated_history.status_code == 200
    assert dated_history.json()["total"] == 1
    assert invalid_dates.status_code == 422

    manager = DatabaseManager(order_database_url, 2)
    with pytest.raises(DBAPIError, match="order item snapshots are immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(OrderItem)
                .where(OrderItem.id == UUID(item["id"]))
                .values(unit_price_snapshot="0.0000")
            )
    await manager.dispose()


async def test_insufficient_inventory_rolls_back_all_items(order_client: AsyncClient) -> None:
    token = await register(order_client, "order-rollback@example.com")
    _, branch_id = await setup_tenant(order_client, token, "order-rollback")
    available = await create_product(order_client, token, "Available", "2.0000")
    insufficient = await create_product(order_client, token, "Insufficient", "3.0000")
    await create_stock(order_client, token, branch_id, str(available["id"]), "5")
    await create_stock(order_client, token, branch_id, str(insufficient["id"]), "1")
    order = await create_order(order_client, token)
    assert (
        await add_item(order_client, token, str(order["id"]), str(available["id"]), branch_id, "2")
    ).status_code == 201
    assert (
        await add_item(
            order_client, token, str(order["id"]), str(insufficient["id"]), branch_id, "2"
        )
    ).status_code == 201

    failed = await order_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=auth(token))
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "insufficient_stock"
    assert await stock_quantity(order_client, token, str(available["id"])) == "5.0000"
    assert await stock_quantity(order_client, token, str(insufficient["id"])) == "1.0000"
    current = await order_client.get(f"/api/v1/orders/{order['id']}", headers=auth(token))
    assert current.json()["status"] == "draft"


async def test_concurrent_confirmation_deducts_inventory_once(order_client: AsyncClient) -> None:
    token = await register(order_client, "order-concurrent@example.com")
    _, branch_id = await setup_tenant(order_client, token, "order-concurrent")
    product = await create_product(order_client, token, "Concurrent Order Product", "4.0000")
    await create_stock(order_client, token, branch_id, str(product["id"]), "5")
    order = await create_order(order_client, token)
    assert (
        await add_item(order_client, token, str(order["id"]), str(product["id"]), branch_id, "4")
    ).status_code == 201

    results = await asyncio.gather(
        order_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=auth(token)),
        order_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=auth(token)),
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    assert await stock_quantity(order_client, token, str(product["id"])) == "1.0000"


async def test_invalid_transitions_and_cross_tenant_access(order_client: AsyncClient) -> None:
    alice_token = await register(order_client, "order-alice@example.com")
    bob_token = await register(order_client, "order-bob@example.com")
    await setup_tenant(order_client, alice_token, "order-alice")
    _, bob_branch = await setup_tenant(order_client, bob_token, "order-bob")
    bob_product = await create_product(order_client, bob_token, "Bob Product", "5.0000")
    bob_order = await create_order(order_client, bob_token)
    alice_order = await create_order(order_client, alice_token)

    cross_get = await order_client.get(
        f"/api/v1/orders/{bob_order['id']}", headers=auth(alice_token)
    )
    cross_item = await add_item(
        order_client,
        alice_token,
        str(alice_order["id"]),
        str(bob_product["id"]),
        bob_branch,
        "1",
    )
    empty_confirm = await order_client.post(
        f"/api/v1/orders/{alice_order['id']}/confirm", headers=auth(alice_token)
    )
    cancelled = await order_client.post(
        f"/api/v1/orders/{alice_order['id']}/cancel", headers=auth(alice_token)
    )
    second_cancel = await order_client.post(
        f"/api/v1/orders/{alice_order['id']}/cancel", headers=auth(alice_token)
    )
    mutate_cancelled = await add_item(
        order_client,
        alice_token,
        str(alice_order["id"]),
        str(bob_product["id"]),
        bob_branch,
        "1",
    )

    assert cross_get.status_code == 404
    assert cross_item.status_code == 404
    assert empty_confirm.status_code == 409
    assert cancelled.status_code == 200
    assert second_cancel.status_code == 409
    assert mutate_cancelled.status_code == 409
