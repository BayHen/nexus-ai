"""Tests for typed application settings."""

import pytest
from pydantic import ValidationError

from nexus.bootstrap.config import Settings


def test_settings_use_safe_defaults() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"


def test_settings_reject_invalid_api_prefix() -> None:
    with pytest.raises(ValidationError):
        Settings(
            api_v1_prefix="api/v1",
            database_url="postgresql+asyncpg://unused:unused@localhost/unused",
            jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
            _env_file=None,
        )


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
