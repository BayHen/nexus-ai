"""Task 13 reliability audit for the Product and Inventory modules."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import StockLevel, StockMovement
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def reliability_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def reliability_client(reliability_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=reliability_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(reliability_database_url, 5)
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
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def create_organization(client: AsyncClient, token: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Organization {slug}", "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def create_branch(client: AsyncClient, token: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": f"Branch {slug}", "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def create_product(client: AsyncClient, token: str, name: str) -> Response:
    return await client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": name, "price": "10.0000", "status": "active"},
    )


async def create_stock(client: AsyncClient, token: str, branch_id: str, product_id: str) -> None:
    response = await client.post(
        "/api/v1/inventory/stocks",
        headers=auth(token),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "low_stock_threshold": "5.0000",
        },
    )
    assert response.status_code == 201, response.text


async def adjust(
    client: AsyncClient,
    token: str,
    branch_id: str,
    product_id: str,
    quantity_delta: str,
    key: str,
) -> Response:
    return await client.post(
        "/api/v1/inventory/adjustments",
        headers=auth(token, key),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "quantity_delta": quantity_delta,
            "reason": "Task 13 reliability test",
        },
    )


async def test_concurrent_product_creation_allocates_unique_monotonic_skus(
    reliability_client: AsyncClient, reliability_database_url: str
) -> None:
    token = await register(reliability_client, "concurrent-products@example.com")
    organization_id = await create_organization(reliability_client, token, "concurrent-products")

    responses = await asyncio.gather(
        *(
            create_product(reliability_client, token, f"Concurrent Product {index:02d}")
            for index in range(20)
        )
    )

    assert {response.status_code for response in responses} == {201}
    skus = [str(response.json()["sku"]) for response in responses]
    assert len(set(skus)) == 20
    assert sorted(skus) == [f"PRD-{index:06d}" for index in range(1, 21)]

    manager = DatabaseManager(reliability_database_url, 2)
    async with manager.transaction() as session:
        duplicate_groups = await session.scalar(
            select(func.count()).select_from(
                select(Product.sku)
                .where(Product.organization_id == UUID(organization_id))
                .group_by(Product.sku)
                .having(func.count() > 1)
                .subquery()
            )
        )
        assert duplicate_groups == 0
    await manager.dispose()


async def test_invalid_adjustments_and_failed_reduction_leave_state_unchanged(
    reliability_client: AsyncClient,
) -> None:
    token = await register(reliability_client, "invalid-adjustment@example.com")
    await create_organization(reliability_client, token, "invalid-adjustment")
    branch_id = await create_branch(reliability_client, token, "invalid-adjustment")
    product = await create_product(reliability_client, token, "Adjustment Product")
    product_id = str(product.json()["id"])
    await create_stock(reliability_client, token, branch_id, product_id)

    zero = await adjust(reliability_client, token, branch_id, product_id, "0", "zero")
    missing_key = await reliability_client.post(
        "/api/v1/inventory/adjustments",
        headers=auth(token),
        json={
            "branch_id": branch_id,
            "product_id": product_id,
            "quantity_delta": "1",
            "reason": "Missing key",
        },
    )
    missing_stock = await adjust(
        reliability_client,
        token,
        branch_id,
        "00000000-0000-0000-0000-000000000001",
        "1",
        "missing-stock",
    )
    excessive = await adjust(
        reliability_client, token, branch_id, product_id, "-1", "excessive-reduction"
    )

    assert zero.status_code == 422
    assert missing_key.status_code == 422
    assert missing_stock.status_code == 404
    assert excessive.status_code == 409
    stock = await reliability_client.get("/api/v1/inventory/stocks", headers=auth(token))
    movements = await reliability_client.get("/api/v1/inventory/movements", headers=auth(token))
    assert stock.json()["items"][0]["quantity"] == "0.0000"
    assert movements.json()["total"] == 0


async def test_concurrent_reduction_and_failed_transfer_rollback(
    reliability_client: AsyncClient,
) -> None:
    token = await register(reliability_client, "concurrent-stock-task13@example.com")
    await create_organization(reliability_client, token, "concurrent-stock-task13")
    source_id = await create_branch(reliability_client, token, "task13-source")
    destination_id = await create_branch(reliability_client, token, "task13-destination")
    product = await create_product(reliability_client, token, "Concurrent Stock Product")
    product_id = str(product.json()["id"])
    await create_stock(reliability_client, token, source_id, product_id)
    await create_stock(reliability_client, token, destination_id, product_id)
    assert (
        await adjust(reliability_client, token, source_id, product_id, "10", "seed-task13")
    ).status_code == 201

    reductions = await asyncio.gather(
        *(
            adjust(
                reliability_client,
                token,
                source_id,
                product_id,
                "-3",
                f"reduce-{index}",
            )
            for index in range(4)
        )
    )
    assert sorted(response.status_code for response in reductions) == [201, 201, 201, 409]

    failed_transfer = await reliability_client.post(
        "/api/v1/inventory/transfers",
        headers=auth(token, "failed-task13-transfer"),
        json={
            "source_branch_id": source_id,
            "destination_branch_id": destination_id,
            "product_id": product_id,
            "quantity": "2",
            "reason": "Must rollback",
        },
    )
    assert failed_transfer.status_code == 409
    listing = await reliability_client.get("/api/v1/inventory/stocks", headers=auth(token))
    quantities = {item["branch_id"]: item["quantity"] for item in listing.json()["items"]}
    assert quantities == {source_id: "1.0000", destination_id: "0.0000"}
    movements = await reliability_client.get("/api/v1/inventory/movements", headers=auth(token))
    assert movements.json()["total"] == 4


async def test_cross_tenant_ids_cannot_read_or_mutate_inventory(
    reliability_client: AsyncClient,
) -> None:
    alice_token = await register(reliability_client, "task13-alice@example.com")
    bob_token = await register(reliability_client, "task13-bob@example.com")
    await create_organization(reliability_client, alice_token, "task13-alice")
    await create_organization(reliability_client, bob_token, "task13-bob")
    alice_branch = await create_branch(reliability_client, alice_token, "task13-alice")
    bob_branch = await create_branch(reliability_client, bob_token, "task13-bob")
    alice_product = await create_product(reliability_client, alice_token, "Alice Product")
    bob_product = await create_product(reliability_client, bob_token, "Bob Product")
    alice_product_id = str(alice_product.json()["id"])
    bob_product_id = str(bob_product.json()["id"])
    await create_stock(reliability_client, alice_token, alice_branch, alice_product_id)
    await create_stock(reliability_client, bob_token, bob_branch, bob_product_id)

    mixed_stock = await reliability_client.post(
        "/api/v1/inventory/stocks",
        headers=auth(alice_token),
        json={
            "branch_id": bob_branch,
            "product_id": alice_product_id,
            "low_stock_threshold": "1",
        },
    )
    cross_adjust = await adjust(
        reliability_client, alice_token, bob_branch, bob_product_id, "1", "cross-tenant"
    )
    spoofed = await reliability_client.get(
        f"/api/v1/inventory/stocks?branch_id={bob_branch}&product_id={bob_product_id}&organization_id=ignored",
        headers={**auth(alice_token), "X-Organization-ID": bob_branch},
    )

    assert mixed_stock.status_code == 404
    assert cross_adjust.status_code == 404
    assert spoofed.status_code == 200
    assert spoofed.json()["total"] == 0


async def test_category_dependency_pagination_search_and_large_inventory_dataset(
    reliability_client: AsyncClient, reliability_database_url: str
) -> None:
    token = await register(reliability_client, "large-inventory@example.com")
    organization_id = await create_organization(reliability_client, token, "large-inventory")
    branch_id = await create_branch(reliability_client, token, "large-inventory")
    category = await reliability_client.post(
        "/api/v1/categories",
        headers=auth(token),
        json={"name": "Bulk Category", "slug": "bulk-category"},
    )
    assert category.status_code == 201
    category_id = str(category.json()["id"])

    manager = DatabaseManager(reliability_database_url, 3)
    products = [
        Product(
            organization_id=UUID(organization_id),
            category_id=UUID(category_id),
            sku=f"BULK-{index:04d}",
            name=f"Bulk Product {index:04d}",
            price="10.0000",
            status="active",
        )
        for index in range(300)
    ]
    async with manager.transaction() as session:
        session.add_all(products)
        await session.flush()
        session.add_all(
            StockLevel(
                organization_id=UUID(organization_id),
                branch_id=UUID(branch_id),
                product_id=product.id,
                quantity=index,
                low_stock_threshold=5,
            )
            for index, product in enumerate(products)
        )

    blocked_delete = await reliability_client.delete(
        f"/api/v1/categories/{category_id}", headers=auth(token)
    )
    assert blocked_delete.status_code == 409

    first_page = await reliability_client.get(
        "/api/v1/inventory/stocks?page=1&page_size=50", headers=auth(token)
    )
    last_page = await reliability_client.get(
        "/api/v1/inventory/stocks?page=6&page_size=50", headers=auth(token)
    )
    search = await reliability_client.get(
        "/api/v1/inventory/stocks?query=BULK-0123", headers=auth(token)
    )
    product_page = await reliability_client.get(
        "/api/v1/products?query=Bulk&page=3&page_size=40&sort_by=name&sort_order=asc",
        headers=auth(token),
    )

    assert first_page.status_code == last_page.status_code == search.status_code == 200
    assert first_page.json()["total"] == 300
    assert len(first_page.json()["items"]) == len(last_page.json()["items"]) == 50
    assert set(
        (item["branch_id"], item["product_id"]) for item in first_page.json()["items"]
    ).isdisjoint((item["branch_id"], item["product_id"]) for item in last_page.json()["items"])
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["product_sku"] == "BULK-0123"
    assert product_page.json()["total"] == 300
    assert product_page.json()["items"][0]["name"] == "Bulk Product 0080"

    async with manager.transaction() as session:
        stock_count = await session.scalar(
            select(func.count())
            .select_from(StockLevel)
            .where(StockLevel.organization_id == UUID(organization_id))
        )
        movement_count = await session.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(StockMovement.organization_id == UUID(organization_id))
        )
        assert stock_count == 300
        assert movement_count == 0
    await manager.dispose()
