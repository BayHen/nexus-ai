"""Async SQLAlchemy engine, session, and transaction management."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nexus.platform.observability.metrics import ApplicationMetrics

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(RuntimeError):
    """Raised when a required database connection cannot be established."""


class DatabaseManager:
    """Own the SQLAlchemy engine and create transaction-scoped sessions."""

    def __init__(
        self,
        database_url: str,
        connect_timeout_seconds: float,
        metrics: ApplicationMetrics | None = None,
        tracer_provider: TracerProvider | None = None,
    ) -> None:
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
        if tracer_provider is not None:
            SQLAlchemyInstrumentor().instrument(
                engine=self.engine.sync_engine,
                tracer_provider=tracer_provider,
                enable_commenter=False,
            )
        if metrics is not None:
            self._register_metrics(metrics)

    def _register_metrics(self, metrics: ApplicationMetrics) -> None:
        """Observe timings without exporting statements, parameters, or tenant IDs."""

        @event.listens_for(self.engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            del cursor, parameters, context, executemany
            operation = _bounded_operation(statement)
            connection.info.setdefault("nexus_query_timers", []).append(
                (perf_counter(), operation)
            )

        @event.listens_for(self.engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            del cursor, statement, parameters, context, executemany
            started_at, operation = connection.info["nexus_query_timers"].pop()
            metrics.observe_database(operation, "success", perf_counter() - started_at)

        @event.listens_for(self.engine.sync_engine, "handle_error")
        def handle_error(exception_context: Any) -> None:
            connection = exception_context.connection
            timers = connection.info.get("nexus_query_timers", []) if connection else []
            if timers:
                started_at, operation = timers.pop()
                metrics.observe_database(operation, "error", perf_counter() - started_at)

        @event.listens_for(self.engine.sync_engine.pool, "checkout")
        def connection_checked_out(*_: Any) -> None:
            metrics.db_connections.inc()

        @event.listens_for(self.engine.sync_engine.pool, "checkin")
        def connection_checked_in(*_: Any) -> None:
            metrics.db_connections.dec()

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


def _bounded_operation(statement: str) -> str:
    operation = statement.lstrip().split(maxsplit=1)[0].lower() if statement.strip() else "other"
    return operation if operation in {"select", "insert", "update", "delete"} else "other"
