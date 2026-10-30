"""Async SQLAlchemy engine, session, and transaction management."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(RuntimeError):
    """Raised when a required database connection cannot be established."""


class DatabaseManager:
    """Own the SQLAlchemy engine and create transaction-scoped sessions."""

    def __init__(self, database_url: str, connect_timeout_seconds: float) -> None:
        self._connect_timeout_seconds = connect_timeout_seconds
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )

    async def check_connection(self) -> bool:
        """Execute a bounded connectivity probe without leaking credentials."""
        try:
            async with asyncio.timeout(self._connect_timeout_seconds):
                async with self.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            return True
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            logger.warning(
                "Database connectivity check failed",
                extra={
                    "event": "database_connectivity_check_failed",
                    "error_type": type(exc).__name__,
                },
            )
            return False

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield one session inside one atomic transaction boundary."""
        async with self.session_factory() as session, session.begin():
            yield session

    async def dispose(self) -> None:
        """Close pooled connections owned by this process."""
        await self.engine.dispose()
