"""
Async SQLAlchemy engine + session factory.

A single async engine is created per process (not per request) with a
connection pool sized via settings — critical when talking to Supabase's
pooled connection endpoint, which itself sits in front of a bounded
Postgres connection count.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,  # guards against stale connections from a serverless pooler
    # Supabase's transaction-mode pooler (port 6543) multiplexes several
    # clients over one backend, so a prepared statement cached by asyncpg
    # can be replayed against a connection that never saw it -- the
    # classic `prepared statement "__asyncpg_stmt_x__" does not exist`
    # failure. Disabling the cache is required there and merely costs a
    # little planning time on a direct connection, so it stays
    # configurable rather than hard-coded off.
    connect_args=(
        {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
        if settings.DB_DISABLE_STATEMENT_CACHE
        else {}
    ),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — one session per request, always closed/rolled back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
