"""Integration tests for the complete Alembic migration chain."""

from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.integration.conftest import psycopg_url

pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20261031_0011"


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


def test_inventory_migration_preserves_existing_catalog_rows(
    temporary_database_url: str,
) -> None:
    """Revision 0006 must be compatible with catalog data created on 0005."""
    config = alembic_config(temporary_database_url)
    command.upgrade(config, "20261030_0005")
    user_id = uuid4()
    organization_id = uuid4()
    product_id = uuid4()
    with psycopg.connect(psycopg_url(temporary_database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO auth_users (id, email, password_hash, is_active)
                VALUES (%s, %s, %s, true)
                """,
                (user_id, "migration-compatibility@example.com", "not-a-real-hash"),
            )
            cursor.execute(
                """
                INSERT INTO organizations (id, name, slug, created_by_user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (organization_id, "Migration Compatibility", "migration-compatibility", user_id),
            )
            cursor.execute(
                """
                INSERT INTO catalog_products
                    (id, organization_id, sku, name, price, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (product_id, organization_id, "PRD-000001", "Existing Product", 10, "active"),
            )

    command.upgrade(config, "head")
    assert current_revision(temporary_database_url) == HEAD_REVISION
    with psycopg.connect(psycopg_url(temporary_database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT sku, name FROM catalog_products WHERE id = %s", (product_id,))
            assert cursor.fetchone() == ("PRD-000001", "Existing Product")
            cursor.execute(
                """
                SELECT count(*)
                FROM pg_constraint
                WHERE conname = 'uq_catalog_products_org_id'
                """
            )
            assert cursor.fetchone() == (1,)

    command.downgrade(config, "20261030_0005")
    with psycopg.connect(psycopg_url(temporary_database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM catalog_products WHERE id = %s", (product_id,))
            assert cursor.fetchone() == (1,)
