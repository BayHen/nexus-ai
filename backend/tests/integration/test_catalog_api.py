"""Product and Category workflows against isolated PostgreSQL databases."""

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.catalog.models import Product
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def catalog_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def catalog_client(catalog_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=catalog_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(catalog_database_url, 3)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    payload = cast(dict[str, Any], response.json())
    return str(payload["tokens"]["access_token"]), str(payload["user"]["id"])


def auth(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


async def create_organization(client: AsyncClient, token: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Organization {slug}", "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def create_category(client: AsyncClient, token: str, name: str, slug: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/categories",
        headers=auth(token),
        json={"name": name, "slug": slug, "description": f"{name} description"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def create_product(
    client: AsyncClient,
    token: str,
    name: str,
    price: str,
    category_id: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=auth(token),
        json={
            "name": name,
            "price": price,
            "category_id": category_id,
            "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def invite_and_accept(
    client: AsyncClient,
    owner_token: str,
    member_token: str,
    organization_id: str,
    email: str,
    role: str,
) -> None:
    invited = await client.post(
        "/api/v1/organizations/current/invitations",
        headers=auth(owner_token),
        json={"email": email, "role": role},
    )
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        f"/api/v1/organizations/{organization_id}/invitations/accept",
        headers=auth(member_token),
    )
    assert accepted.status_code == 200, accepted.text


async def test_product_category_crud_search_filter_sort_and_soft_delete(
    catalog_client: AsyncClient,
) -> None:
    token, _ = await register(catalog_client, "catalog-owner@example.com")
    await create_organization(catalog_client, token, "catalog-main")
    category = await create_category(catalog_client, token, "Hardware", "hardware")
    first = await create_product(catalog_client, token, "Alpha Laptop", "1200.5000", category["id"])
    second = await create_product(
        catalog_client, token, "Beta Mouse", "25.2500", category["id"], "draft"
    )
    assert first["sku"] == "PRD-000001"
    assert second["sku"] == "PRD-000002"
    assert first["price"] == "1200.5000"

    listing = await catalog_client.get(
        "/api/v1/products?query=a&status=active&min_price=100&sort_by=price&sort_order=desc&page=1&page_size=1",
        headers=auth(token),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == first["id"]

    updated = await catalog_client.patch(
        f"/api/v1/products/{first['id']}",
        headers=auth(token),
        json={"price": "1199.9900", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == "1199.9900"

    blocked_delete = await catalog_client.delete(
        f"/api/v1/categories/{category['id']}", headers=auth(token)
    )
    assert blocked_delete.status_code == 409
    assert (
        await catalog_client.get(f"/api/v1/categories/{category['id']}", headers=auth(token))
    ).status_code == 200

    for product_id in (first["id"], second["id"]):
        assert (
            await catalog_client.delete(f"/api/v1/products/{product_id}", headers=auth(token))
        ).status_code == 204
        assert (
            await catalog_client.get(f"/api/v1/products/{product_id}", headers=auth(token))
        ).status_code == 404
    assert (
        await catalog_client.delete(f"/api/v1/categories/{category['id']}", headers=auth(token))
    ).status_code == 204
    assert (
        await catalog_client.get(f"/api/v1/categories/{category['id']}", headers=auth(token))
    ).status_code == 404

    replacement = await create_category(catalog_client, token, "Hardware", "hardware")
    assert replacement["id"] != category["id"]


async def test_validation_duplicates_and_failed_request_rollback(
    catalog_client: AsyncClient,
) -> None:
    token, _ = await register(catalog_client, "validation@example.com")
    await create_organization(catalog_client, token, "validation")
    await create_category(catalog_client, token, "Unique", "unique")
    duplicate = await catalog_client.post(
        "/api/v1/categories",
        headers=auth(token),
        json={"name": "Unique", "slug": "different"},
    )
    negative = await catalog_client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": "Invalid", "price": "-0.0001"},
    )
    invalid_category = await catalog_client.post(
        "/api/v1/products",
        headers=auth(token),
        json={"name": "Invalid Category", "price": "1.0000", "category_id": str(uuid4())},
    )
    assert duplicate.status_code == 409
    assert negative.status_code == 422
    assert invalid_category.status_code == 422

    product = await create_product(catalog_client, token, "First Valid", "1.0000")
    assert product["sku"] == "PRD-000001"
    categories = await catalog_client.get("/api/v1/categories", headers=auth(token))
    assert categories.json()["total"] == 1


async def test_catalog_authorization_and_cross_tenant_isolation(
    catalog_client: AsyncClient,
) -> None:
    alice_token, _ = await register(catalog_client, "alice-catalog@example.com")
    bob_token, _ = await register(catalog_client, "bob-catalog@example.com")
    viewer_token, _ = await register(catalog_client, "viewer-catalog@example.com")
    manager_token, _ = await register(catalog_client, "manager-catalog@example.com")
    alice_org = await create_organization(catalog_client, alice_token, "alice-catalog")
    await create_organization(catalog_client, bob_token, "bob-catalog")
    bob_category = await create_category(catalog_client, bob_token, "Bob Category", "bob-category")
    bob_product = await create_product(
        catalog_client, bob_token, "Bob Product", "10.0000", bob_category["id"]
    )
    alice_category = await create_category(
        catalog_client, alice_token, "Alice Category", "alice-category"
    )
    alice_product = await create_product(
        catalog_client, alice_token, "Alice Product", "20.0000", alice_category["id"]
    )
    assert bob_product["sku"] == alice_product["sku"] == "PRD-000001"

    for path in (
        f"/api/v1/products/{bob_product['id']}",
        f"/api/v1/categories/{bob_category['id']}",
    ):
        assert (await catalog_client.get(path, headers=auth(alice_token))).status_code == 404
        assert (
            await catalog_client.patch(path, headers=auth(alice_token), json={"name": "Attack"})
        ).status_code == 404
        assert (await catalog_client.delete(path, headers=auth(alice_token))).status_code == 404
    cross_category = await catalog_client.post(
        "/api/v1/products",
        headers=auth(alice_token),
        json={"name": "Cross Tenant", "price": "1", "category_id": bob_category["id"]},
    )
    assert cross_category.status_code == 422
    spoofed = await catalog_client.get(
        f"/api/v1/products?organization_id={bob_category['id']}",
        headers=auth(alice_token, **{"X-Organization-ID": bob_category["id"]}),
    )
    assert [item["id"] for item in spoofed.json()["items"]] == [alice_product["id"]]

    await invite_and_accept(
        catalog_client,
        alice_token,
        viewer_token,
        alice_org,
        "viewer-catalog@example.com",
        "viewer",
    )
    await invite_and_accept(
        catalog_client,
        alice_token,
        manager_token,
        alice_org,
        "manager-catalog@example.com",
        "manager",
    )
    assert (
        await catalog_client.get("/api/v1/products", headers=auth(viewer_token))
    ).status_code == 200
    assert (
        await catalog_client.post(
            "/api/v1/products",
            headers=auth(viewer_token),
            json={"name": "Denied", "price": "1"},
        )
    ).status_code == 403
    manager_product = await create_product(
        catalog_client, manager_token, "Manager Product", "5.0000"
    )
    assert (
        await catalog_client.patch(
            f"/api/v1/products/{manager_product['id']}",
            headers=auth(manager_token),
            json={"price": "6.0000"},
        )
    ).status_code == 200
    assert (
        await catalog_client.delete(
            f"/api/v1/products/{manager_product['id']}", headers=auth(manager_token)
        )
    ).status_code == 403


async def test_database_rejects_negative_price_and_rolls_back(
    catalog_client: AsyncClient, catalog_database_url: str
) -> None:
    token, _ = await register(catalog_client, "db-price@example.com")
    organization_id = await create_organization(catalog_client, token, "db-price")
    manager = DatabaseManager(catalog_database_url, 3)
    with pytest.raises(IntegrityError):
        async with manager.transaction() as session:
            session.add(
                Product(
                    organization_id=UUID(organization_id),
                    sku="PRD-ATTACK",
                    name="Invalid Database Product",
                    price=Decimal("-1.0000"),
                    status="active",
                )
            )
    async with manager.transaction() as session:
        count = await session.scalar(
            select(func.count()).select_from(Product).where(Product.sku == "PRD-ATTACK")
        )
        assert count == 0
    await manager.dispose()
