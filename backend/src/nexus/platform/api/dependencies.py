"""Framework dependencies shared by operational endpoints."""

from collections.abc import Awaitable, Callable, Sequence

from fastapi import Request

from nexus.platform.database.protocols import DatabaseManagerProtocol

ReadinessCheck = Callable[[], Awaitable[bool]]


def get_database_manager(request: Request) -> DatabaseManagerProtocol:
    """Resolve the process database manager from application state."""
    manager: DatabaseManagerProtocol = request.app.state.database_manager
    return manager


def get_readiness_checks(request: Request) -> Sequence[tuple[str, ReadinessCheck]]:
    """Provide readiness checks through an overridable FastAPI dependency."""
    manager = get_database_manager(request)
    return (("database", manager.check_connection),)
