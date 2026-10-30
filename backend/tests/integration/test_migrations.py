"""Integration tests for the complete Alembic migration chain."""

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.integration.conftest import psycopg_url

pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20261030_0005"


def alembic_config(database_url: str) -> Config:
    """Build an Alembic config pinned to an isolated test database."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def current_revision(database_url: str) -> str | None:
    """Read the revision recorded by Alembic."""
    with psycopg.connect(psycopg_url(database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            row = cursor.fetchone()
    return None if row is None else str(row[0])


def test_migrations_upgrade_downgrade_and_reapply(temporary_database_url: str) -> None:
    config = alembic_config(temporary_database_url)

    command.upgrade(config, "head")
    assert current_revision(temporary_database_url) == HEAD_REVISION

    command.downgrade(config, "base")
    assert current_revision(temporary_database_url) is None

    command.upgrade(config, "head")
    assert current_revision(temporary_database_url) == HEAD_REVISION
