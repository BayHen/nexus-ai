"""Shared backend test fixtures."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings


@pytest.fixture
def app() -> FastAPI:
    """Create an isolated application with deterministic test settings."""
    return create_app(Settings(environment="test", log_level="CRITICAL"))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Expose an asynchronous client connected directly to the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def anyio_backend() -> str:
    """Use the backend's asyncio runtime for asynchronous API tests."""
    return "asyncio"
