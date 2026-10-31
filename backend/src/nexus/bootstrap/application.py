"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nexus.bootstrap.config import Settings, get_settings
from nexus.modules.auth.rate_limit import AuthenticationRateLimiter
from nexus.modules.knowledge.providers import DeterministicAIProvider, OpenAIKnowledgeProvider
from nexus.platform.api.errors import register_exception_handlers
from nexus.platform.api.health import router as health_router
from nexus.platform.api.middleware import RequestContextMiddleware
from nexus.platform.api.v1 import router as api_v1_router
from nexus.platform.cache.service import CacheService, NullCacheService, RedisCacheService
from nexus.platform.database.manager import DatabaseManager, DatabaseUnavailableError
from nexus.platform.database.protocols import DatabaseManagerProtocol
from nexus.platform.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    database_manager: DatabaseManagerProtocol | None = None,
) -> FastAPI:
    """Create and configure an isolated FastAPI application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database_manager = database_manager or DatabaseManager(
        database_url=resolved_settings.database_url.get_secret_value(),
        connect_timeout_seconds=resolved_settings.database_connect_timeout_seconds,
    )
    cache_service: CacheService = (
        RedisCacheService(resolved_settings.redis_url.get_secret_value())
        if resolved_settings.redis_url is not None
        else NullCacheService()
    )
    knowledge_provider: OpenAIKnowledgeProvider | DeterministicAIProvider
    if resolved_settings.openai_api_key is not None:
        knowledge_provider = OpenAIKnowledgeProvider(
            resolved_settings.openai_api_key.get_secret_value(),
            resolved_settings.embedding_model,
            resolved_settings.openai_model,
        )
    else:
        knowledge_provider = DeterministicAIProvider()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not await resolved_database_manager.check_connection():
            logger.critical(
                "Database is unavailable during startup",
                extra={"event": "database_startup_check_failed"},
            )
            await cache_service.close()
            await resolved_database_manager.dispose()
            raise DatabaseUnavailableError("Database is unavailable during startup")
        try:
            yield
        finally:
            await cache_service.close()
            await resolved_database_manager.dispose()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database_manager = resolved_database_manager
    application.state.auth_rate_limiter = AuthenticationRateLimiter(
        resolved_settings.auth_rate_limit_attempts,
        resolved_settings.auth_rate_limit_window_seconds,
    )
    application.state.cache_service = cache_service
    application.state.knowledge_embedding_provider = knowledge_provider
    application.state.knowledge_answer_provider = knowledge_provider
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(api_v1_router, prefix=resolved_settings.api_v1_prefix)
    return application
