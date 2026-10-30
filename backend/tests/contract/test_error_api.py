"""Contract tests for centralized error handling."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from nexus.platform.api.errors import ApplicationError

pytestmark = pytest.mark.anyio


async def test_application_error_uses_stable_envelope(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/_test/application-error")
    async def raise_application_error() -> None:
        raise ApplicationError(
            code="test_conflict",
            message="A test conflict occurred.",
            status_code=409,
        )

    response = await client.get(
        "/_test/application-error",
        headers={"X-Request-ID": "error-request-1"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "test_conflict",
            "message": "A test conflict occurred.",
            "request_id": "error-request-1",
        }
    }
