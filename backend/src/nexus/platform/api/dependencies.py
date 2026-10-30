"""Framework dependencies shared by operational endpoints."""

from collections.abc import Awaitable, Callable, Sequence

ReadinessCheck = Callable[[], Awaitable[bool]]


async def application_readiness_check() -> bool:
    """Confirm the API event loop can execute a dependency check."""
    return True


def get_readiness_checks() -> Sequence[tuple[str, ReadinessCheck]]:
    """Provide readiness checks through an overridable FastAPI dependency."""
    return (("application", application_readiness_check),)
