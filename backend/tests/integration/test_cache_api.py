"""Redis cache integration, tenant isolation, and invalidation tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from statistics import median
from time import perf_counter
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.platform.cache.service import RedisCacheService, tenant_cache_key
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_catalog_api import (
    auth,
    create_organization,
    create_product,
    register,
)
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
REDIS_URL = "redis://127.0.0.1:6379/15"


@pytest.fixture
def cache_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        pytest.skip(f"Redis integration service is unavailable: {type(exc).__name__}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture
async def cache_client(
    cache_database_url: str, redis_client: Redis
) -> AsyncIterator[AsyncClient]:
    del redis_client
    settings = Settings(
        environment="test",
        database_url=cache_database_url,
        redis_url=REDIS_URL,
        cache_ttl_seconds=60,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(cache_database_url, 3)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await app.state.cache_service.close()
    await manager.dispose()


async def prepare_product(
    client: AsyncClient, email: str, slug: str
) -> tuple[str, str, dict[str, Any]]:
    token, _ = await register(client, email)
    organization_id = await create_organization(client, token, slug)
    product = await create_product(client, token, f"Product {slug}", "19.9900")
    return token, organization_id, product


async def test_cache_hit_tenant_isolation_and_post_commit_invalidation(
    cache_client: AsyncClient, redis_client: Redis
) -> None:
    alice_token, alice_org, product = await prepare_product(
        cache_client, "cache-alice@example.com", "cache-alice"
    )
    first = await cache_client.get(
        f"/api/v1/products/{product['id']}", headers=auth(alice_token)
    )
    second = await cache_client.get(
        f"/api/v1/products/{product['id']}", headers=auth(alice_token)
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    alice_key = tenant_cache_key(
        UUID(alice_org),
        "product",
        UUID(product["id"]),
    )
    assert await redis_client.exists(alice_key) == 1

    bob_token, bob_org, _ = await prepare_product(
        cache_client, "cache-bob@example.com", "cache-bob"
    )
    cross_tenant = await cache_client.get(
        f"/api/v1/products/{product['id']}", headers=auth(bob_token)
    )
    assert cross_tenant.status_code == 404
    bob_key = alice_key.replace(alice_org, bob_org)
    assert await redis_client.exists(bob_key) == 0

    updated = await cache_client.patch(
        f"/api/v1/products/{product['id']}",
        headers=auth(alice_token),
        json={"name": "Product after commit"},
    )
    assert updated.status_code == 200
    assert await redis_client.exists(alice_key) == 0
    refreshed = await cache_client.get(
        f"/api/v1/products/{product['id']}", headers=auth(alice_token)
    )
    assert refreshed.json()["name"] == "Product after commit"

    metrics = await cache_client.get("/api/v1/cache/metrics", headers=auth(alice_token))
    assert metrics.status_code == 200
    assert metrics.json()["hits"] >= 1
    assert metrics.json()["misses"] >= 3
    assert metrics.json()["deletes"] >= 1


async def test_cache_benchmark_reports_cold_and_warm_latency(
    cache_client: AsyncClient, redis_client: Redis
) -> None:
    token, organization_id, product = await prepare_product(
        cache_client, "cache-benchmark@example.com", "cache-benchmark"
    )
    key = tenant_cache_key(UUID(organization_id), "product", UUID(product["id"]))
    endpoint = f"/api/v1/products/{product['id']}"
    headers = auth(token)
    cold_samples: list[float] = []
    warm_samples: list[float] = []

    for _ in range(30):
        await redis_client.delete(key)
        started = perf_counter()
        response = await cache_client.get(endpoint, headers=headers)
        cold_samples.append((perf_counter() - started) * 1000)
        assert response.status_code == 200

        started = perf_counter()
        response = await cache_client.get(endpoint, headers=headers)
        warm_samples.append((perf_counter() - started) * 1000)
        assert response.status_code == 200

    print(
        "CACHE_BENCHMARK "
        f"samples=30 cold_median_ms={median(cold_samples):.3f} "
        f"warm_median_ms={median(warm_samples):.3f}"
    )
    assert len(cold_samples) == len(warm_samples) == 30


async def test_catalog_api_falls_back_to_database_when_redis_is_unavailable(
    cache_client: AsyncClient,
) -> None:
    token, _, product = await prepare_product(
        cache_client, "cache-fallback@example.com", "cache-fallback"
    )
    app = cache_client._transport.app  # type: ignore[attr-defined]
    available_cache = app.state.cache_service
    unavailable_cache = RedisCacheService(
        "redis://127.0.0.1:6399/0", socket_timeout_seconds=0.05
    )
    app.state.cache_service = unavailable_cache
    try:
        response = await cache_client.get(
            f"/api/v1/products/{product['id']}", headers=auth(token)
        )
        assert response.status_code == 200
        assert response.json()["id"] == product["id"]
        assert unavailable_cache.metrics()["errors"] >= 2
    finally:
        app.state.cache_service = available_cache
        await unavailable_cache.close()
