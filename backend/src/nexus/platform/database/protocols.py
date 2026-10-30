"""Protocols for dependency-injected database lifecycle behavior."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseManagerProtocol(Protocol):
    """Minimal lifecycle contract required by the application shell."""

    async def check_connection(self) -> bool:
        """Return whether the database can execute a trivial query."""
        ...

    async def dispose(self) -> None:
        """Release database engine resources."""
        ...


class TransactionManagerProtocol(DatabaseManagerProtocol, Protocol):
    """Database manager contract required by transactional use cases."""

    def transaction(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Return an atomic async session context."""
        ...
