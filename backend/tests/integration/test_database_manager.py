"""Integration tests for database connectivity and transaction semantics."""

import pytest
from sqlalchemy import text

from nexus.platform.database.manager import DatabaseManager

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
