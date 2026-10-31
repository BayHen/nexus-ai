"""Contract tests for health and version endpoints."""

from collections.abc import Sequence

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tests.conftest import AvailableDatabaseManager

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.platform.api.dependencies import ReadinessCheck, get_readiness_checks

pytestmark = pytest.mark.anyio


async def test_liveness_endpoint_returns_request_id(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "test-live-1"})

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "checks": None}
    assert response.headers["X-Request-ID"] == "test-live-1"


async def test_readiness_endpoint_reports_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "up"}}


async def test_readiness_endpoint_returns_503_when_check_fails(
    app: FastAPI, client: AsyncClient
) -> None:
    async def unavailable() -> bool:
        return False

    def failing_checks() -> Sequence[tuple[str, ReadinessCheck]]:
        return (("dependency", unavailable),)

    app.dependency_overrides[get_readiness_checks] = failing_checks
    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"dependency": "down"},
    }


async def test_versioned_api_route_is_available(client: AsyncClient) -> None:
    response = await client.get("/api/v1")

    assert response.status_code == 200
    assert response.json() == {"name": "NEXUS AI API", "version": "v1"}


async def test_openapi_and_documentation_are_available(client: AsyncClient) -> None:
    openapi_response = await client.get("/openapi.json")
    docs_response = await client.get("/docs")

    assert openapi_response.status_code == 200
    assert "/api/v1" in openapi_response.json()["paths"]
    assert "/health/live" in openapi_response.json()["paths"]
    assert docs_response.status_code == 200


async def test_production_disables_interactive_api_documentation() -> None:
    settings = Settings(
        environment="production",
        log_level="CRITICAL",
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
        jwt_secret_key="production-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    production_app = create_app(settings, database_manager=AvailableDatabaseManager())
    async with AsyncClient(
        transport=ASGITransport(app=production_app),
        base_url="http://test",
    ) as production_client:
        assert (await production_client.get("/docs")).status_code == 404
        assert (await production_client.get("/openapi.json")).status_code == 404
