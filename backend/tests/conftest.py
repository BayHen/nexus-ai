"""Shared backend test fixtures."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings


class AvailableDatabaseManager:
    """Deterministic database lifecycle test double."""

    disposed = False

    async def check_connection(self) -> bool:
        return True

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def app() -> FastAPI:
    """Create an isolated application with deterministic test settings."""
    settings = Settings(
        environment="test",
        log_level="CRITICAL",
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
    )
    return create_app(settings, database_manager=AvailableDatabaseManager())


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
