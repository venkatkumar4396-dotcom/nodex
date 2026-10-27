"""
Database engine and async session factory.

Uses SQLAlchemy 2.0 async API with asyncpg driver.
Session lifecycle is managed via FastAPI dependency injection
(get_db_session) to ensure proper cleanup on every request.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from agentflow.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


# ── Engine ─────────────────────────────────────────────────────────────────
# SQLite vs Postgres engine options
is_sqlite = "sqlite" in settings.database_url
engine_kwargs: dict = {"echo": False}

if is_sqlite:
    from sqlalchemy.pool import StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
else:
    # pool_pre_ping=True: automatically reconnects stale connections from the
    # pool before handing them to application code — essential for Postgres
    # behind a load balancer or after network blips.
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **engine_kwargs)

# ── Session factory ────────────────────────────────────────────────────────
# expire_on_commit=False: after a commit(), already-loaded attributes stay
# accessible without hitting the DB again. This is standard for async API
# handlers where we read-then-return immediately after commit.
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session():
    """FastAPI dependency: yields an AsyncSession and auto-closes it."""
    async with async_session() as session:
        yield session
