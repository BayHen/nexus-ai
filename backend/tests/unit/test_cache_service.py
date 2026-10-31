"""Cache key and fail-open behavior tests."""

from uuid import uuid4

import pytest

from nexus.platform.cache.service import RedisCacheService, tenant_cache_key

pytestmark = pytest.mark.anyio


def test_tenant_cache_keys_do_not_collide() -> None:
    resource_id = uuid4()
    first_tenant = tenant_cache_key(uuid4(), "product", resource_id)
    second_tenant = tenant_cache_key(uuid4(), "product", resource_id)

    assert first_tenant != second_tenant
    assert first_tenant.startswith("nexus:v1:tenant:")


async def test_unavailable_redis_fails_open_as_cache_miss() -> None:
    cache = RedisCacheService(
        "redis://127.0.0.1:6399/0", socket_timeout_seconds=0.05
    )
    try:
        assert await cache.get_json("unavailable") is None
        await cache.set_json("unavailable", {"value": True}, 30)
        await cache.delete("unavailable")
        assert cache.metrics()["errors"] == 3
    finally:
        await cache.close()
