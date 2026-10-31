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
    celery_broker_url: SecretStr = Field(
        default=SecretStr("amqp://guest:guest@127.0.0.1:5672//"),
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: SecretStr = Field(
        default=SecretStr("redis://127.0.0.1:6379/1"),
        validation_alias="CELERY_RESULT_BACKEND",
    )
    background_job_max_attempts: int = Field(default=5, ge=1, le=20)
    background_job_retry_base_seconds: int = Field(default=2, ge=1, le=300)
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL"
    )
    knowledge_max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    knowledge_retrieval_limit: int = Field(default=5, ge=1, le=20)
    knowledge_distance_threshold: float = Field(default=0.45, gt=0, lt=2)
    agent_tool_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    mcp_issuer_url: str = Field(default="http://127.0.0.1:8000", pattern=r"^https?://")
    mcp_server_url: str = Field(default="http://127.0.0.1:8001/mcp", pattern=r"^https?://")
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8001, ge=1, le=65535)

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
