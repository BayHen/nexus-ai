"""Integration tests for database connectivity and transaction semantics."""

import pytest
from prometheus_client import generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from nexus.platform.database.manager import DatabaseManager
from nexus.platform.observability.metrics import ApplicationMetrics

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_connection_and_transaction_commit_and_rollback(
    temporary_database_url: str,
) -> None:
    manager = DatabaseManager(temporary_database_url, connect_timeout_seconds=2)
    try:
        assert await manager.check_connection() is True

        async with manager.transaction() as session:
            await session.execute(text("CREATE TABLE committed_probe (id integer PRIMARY KEY)"))

        async with manager.engine.connect() as connection:
            committed = await connection.scalar(text("SELECT to_regclass('committed_probe')"))
        assert committed == "committed_probe"

        with pytest.raises(RuntimeError, match="force rollback"):
            async with manager.transaction() as session:
                await session.execute(
                    text("CREATE TABLE rolled_back_probe (id integer PRIMARY KEY)")
                )
                raise RuntimeError("force rollback")

        async with manager.engine.connect() as connection:
            rolled_back = await connection.scalar(text("SELECT to_regclass('rolled_back_probe')"))
        assert rolled_back is None
    finally:
        await manager.dispose()


async def test_database_metrics_record_success_failure_and_hide_sql(
    temporary_database_url: str,
) -> None:
    metrics = ApplicationMetrics()
    manager = DatabaseManager(
        temporary_database_url,
        connect_timeout_seconds=2,
        metrics=metrics,
    )
    try:
        assert await manager.check_connection() is True
        with pytest.raises(SQLAlchemyError):
            async with manager.engine.connect() as connection:
                await connection.execute(text("SELECT * FROM private_missing_table"))

        payload = generate_latest(metrics.registry).decode()
        assert 'operation="select",status="success"' in payload
        assert 'operation="select",status="error"' in payload
        assert "private_missing_table" not in payload
        assert "nexus_db_connections_checked_out 0.0" in payload
    finally:
        await manager.dispose()
