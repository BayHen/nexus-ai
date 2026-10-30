"""Protocols for dependency-injected database lifecycle behavior."""

from typing import Protocol


class DatabaseManagerProtocol(Protocol):
    """Minimal lifecycle contract required by the application shell."""

    async def check_connection(self) -> bool:
        """Return whether the database can execute a trivial query."""
        ...

    async def dispose(self) -> None:
        """Release database engine resources."""
        ...
