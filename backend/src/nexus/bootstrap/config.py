"""Typed application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the API process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NEXUS_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "NEXUS AI API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_v1_prefix: str = Field(default="/api/v1", pattern=r"^/[a-z0-9/_-]+$")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    database_connect_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY", min_length=32)
    jwt_algorithm: Literal["HS256"] = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_issuer: str = "nexus-ai"
    jwt_audience: str = "nexus-ai-api"
    access_token_expire_minutes: int = Field(
        default=15, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES", ge=1, le=60
    )
    refresh_token_expire_days: int = Field(
        default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS", ge=1, le=30
    )
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=60)
    auth_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    payment_webhook_secret: SecretStr | None = Field(
        default=None, validation_alias="PAYMENT_WEBHOOK_SECRET", min_length=32
    )
    redis_url: SecretStr | None = Field(default=None, validation_alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=60, ge=1, le=3600)

    @model_validator(mode="after")
    def reject_default_auth_secret(self) -> "Settings":
        """Prevent placeholder secrets outside the test environment."""
        secret = self.jwt_secret_key.get_secret_value()
        if self.environment != "test" and secret.startswith("replace-with"):
            raise ValueError("JWT_SECRET_KEY must be replaced outside test")
        payment_secret = self.payment_webhook_secret
        if (
            self.environment != "test"
            and payment_secret is not None
            and payment_secret.get_secret_value().startswith("replace-with")
        ):
            raise ValueError("PAYMENT_WEBHOOK_SECRET must be replaced outside test")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings dependency."""
    return Settings()
