"""Tests for fail-fast application lifecycle behavior."""

import pytest

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.platform.database.manager import DatabaseUnavailableError

pytestmark = pytest.mark.anyio


async def test_startup_fails_when_database_is_unavailable() -> None:
    settings = Settings(
        environment="test",
        log_level="CRITICAL",
        database_url="postgresql+asyncpg://invalid:invalid@127.0.0.1:1/unavailable",
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        database_connect_timeout_seconds=0.1,
        _env_file=None,
    )
    app = create_app(settings)

    with pytest.raises(DatabaseUnavailableError, match="unavailable during startup"):
        async with app.router.lifespan_context(app):
            pytest.fail("Application started without its required database")
