"""
ChaosMesh Arena — SQLAlchemy Async Engine + Session Factory.

Uses SQLite for local dev, Postgres for production.
All DB access is async via asyncpg (Postgres) or aiosqlite (SQLite).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from chaosmesh_arena.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _make_engine():
    settings = get_settings()
    url = settings.effective_database_url

    if url.startswith("postgresql"):
        # Postgres — async driver
        if "asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return create_async_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
    else:
        # SQLite — aiosqlite driver
        return create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )


engine = _make_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (idempotent — safe to call on startup)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
