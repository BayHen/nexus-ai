"""PostgreSQL integration fixtures using isolated temporary databases."""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url


def psycopg_url(database_url: str) -> str:
    """Convert a SQLAlchemy psycopg URL into a libpq-compatible URL."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def temporary_database_url() -> Iterator[str]:
    """Create and reliably remove an isolated PostgreSQL database."""
    admin_url = os.getenv("NEXUS_TEST_DATABASE_ADMIN_URL")
    if not admin_url:
        pytest.skip("NEXUS_TEST_DATABASE_ADMIN_URL is required for PostgreSQL integration tests")

    database_name = f"nexus_test_{uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    parsed_admin_url = make_url(admin_url)
    database_url = parsed_admin_url.set(
        drivername="postgresql+asyncpg",
        database=database_name,
    ).render_as_string(hide_password=False)
    try:
        yield database_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
