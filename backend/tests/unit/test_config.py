"""Tests for typed application settings."""

import pytest
from pydantic import ValidationError

from nexus.bootstrap.config import Settings


def test_settings_use_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"


def test_settings_reject_invalid_api_prefix() -> None:
    with pytest.raises(ValidationError):
        Settings(api_v1_prefix="api/v1", _env_file=None)
