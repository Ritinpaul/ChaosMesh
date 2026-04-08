"""
Alembic env.py — ChaosMesh Arena migrations.

Run migrations:
    alembic upgrade head

Create a new revision:
    alembic revision --autogenerate -m "description"
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from chaosmesh_arena.config import get_settings
from chaosmesh_arena.database.models_db import (  # noqa: F401 — imports register models
    APIKey, EpisodeResult, Membership, Organization, User,
)
from chaosmesh_arena.database.base import Base

# Alembic config
config = context.config
if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata

# Override sqlalchemy.url from env
_db_url = settings.effective_database_url
# Alembic needs sync URL for migrations
_sync_url = (
    _db_url
    .replace("sqlite+aiosqlite://", "sqlite:///")
    .replace("postgresql+asyncpg://", "postgresql://")
)
config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(_db_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
