"""Fail-open JSON cache services with bounded in-process metrics."""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    errors: int = 0
    sets: int = 0
    deletes: int = 0


class CacheService(Protocol):
    async def get_json(self, key: str) -> dict[str, Any] | None: ...

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None: ...

    async def delete(self, key: str) -> None: ...

    def metrics(self) -> dict[str, int]: ...

    async def close(self) -> None: ...


class NullCacheService:
    """No-op fallback used when Redis is not configured."""

    def __init__(self) -> None:
        self._metrics = CacheMetrics()

    async def get_json(self, key: str) -> dict[str, Any] | None:
        del key
        self._metrics.misses += 1
        return None

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        del key, value, ttl_seconds

    async def delete(self, key: str) -> None:
        del key

    def metrics(self) -> dict[str, int]:
        return asdict(self._metrics)

    async def close(self) -> None:
        return None


class RedisCacheService:
    """Redis cache that degrades to a miss when the dependency is unavailable."""

    def __init__(self, url: str, *, socket_timeout_seconds: float = 0.2) -> None:
        self._client = Redis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=socket_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
        )
        self._metrics = CacheMetrics()

    async def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._client.get(key)
            if raw is None:
                self._metrics.misses += 1
                return None
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("cached JSON must be an object")
            self._metrics.hits += 1
            return value
        except (RedisError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            self._metrics.errors += 1
            logger.warning(
                "Cache read failed; using source of truth",
                extra={"event": "cache_read_failed", "error_type": type(exc).__name__},
            )
            return None

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            await self._client.set(key, json.dumps(value, separators=(",", ":")), ex=ttl_seconds)
            self._metrics.sets += 1
        except (RedisError, OSError, TimeoutError) as exc:
            self._metrics.errors += 1
            logger.warning(
                "Cache write failed; request remains successful",
                extra={"event": "cache_write_failed", "error_type": type(exc).__name__},
            )

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
            self._metrics.deletes += 1
        except (RedisError, OSError, TimeoutError) as exc:
            self._metrics.errors += 1
            logger.warning(
                "Cache invalidation failed; TTL bounds staleness",
                extra={"event": "cache_delete_failed", "error_type": type(exc).__name__},
            )

    def metrics(self) -> dict[str, int]:
        return asdict(self._metrics)

    async def close(self) -> None:
        await self._client.aclose()


def tenant_cache_key(organization_id: UUID, resource: str, resource_id: UUID) -> str:
    """Build a versioned key that cannot collide across tenants."""
    return f"nexus:v1:tenant:{organization_id}:{resource}:{resource_id}"


def schedule_invalidation(session: AsyncSession, key: str) -> None:
    """Register a cache key for deletion only after the DB transaction commits."""
    keys = session.info.setdefault("cache_invalidation_keys", set())
    keys.add(key)
