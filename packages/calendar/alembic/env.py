"""Alembic environment: async engine, DSN from Settings.

Two things here are different from `packages/ears-discord`'s copy, and both
exist because this lineage shares a database with that one:

  * `version_table` — ears' migrations stamp `alembic_version`. If this
    lineage stamped the same table the two would read each other's revision
    ids as their own and one of them would fail to find its own head.
  * `include_object` — without it, `alembic revision --autogenerate` run here
    would see ears' eleven tables in the same database, find them absent from
    this metadata, and cheerfully write a migration that DROPs the transcript.
    Everything not owned by this package is filtered out before that can happen.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from gavel_calendar.db.models import Base
from gavel_calendar.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# asyncpg for the engine; the DSN may arrive in either spelling.
dsn = get_settings().async_postgres_dsn
config.set_main_option("sqlalchemy.url", dsn)
target_metadata = Base.metadata

VERSION_TABLE = "alembic_version_calendar"
OWNED_TABLES = frozenset(Base.metadata.tables)


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        return name in OWNED_TABLES
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table=VERSION_TABLE,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        version_table=VERSION_TABLE,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
