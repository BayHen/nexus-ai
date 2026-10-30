"""FastAPI application factory."""

from fastapi import FastAPI

from nexus.bootstrap.config import Settings, get_settings
from nexus.platform.api.errors import register_exception_handlers
from nexus.platform.api.health import router as health_router
from nexus.platform.api.middleware import RequestContextMiddleware
from nexus.platform.api.v1 import router as api_v1_router
from nexus.platform.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure an isolated FastAPI application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.state.settings = resolved_settings
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(api_v1_router, prefix=resolved_settings.api_v1_prefix)
    return application
