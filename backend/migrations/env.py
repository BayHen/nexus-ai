"""Alembic environment for asynchronous SQLAlchemy migrations."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from nexus.bootstrap.config import Settings
from nexus.modules.auth import models as auth_models  # noqa: F401
from nexus.modules.catalog import models as catalog_models  # noqa: F401
from nexus.modules.inventory import models as inventory_models  # noqa: F401
from nexus.modules.orders import models as order_models  # noqa: F401
from nexus.modules.organizations import models as organization_models  # noqa: F401
from nexus.modules.payments import models as payment_models  # noqa: F401
from nexus.platform.database.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def resolve_database_url() -> str:
    """Use a programmatic test override or environment-backed application settings."""
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    repository_env = Path(__file__).resolve().parents[2] / ".env"
    settings = Settings(_env_file=repository_env)
    return settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=resolve_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure a synchronous Alembic context over an async connection bridge."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a short-lived async engine and execute migrations."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = resolve_database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
