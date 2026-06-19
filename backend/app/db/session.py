"""
Async SQLAlchemy engine, session factory, and FastAPI dependency.

Design:
- Uses asyncpg driver for high-performance async I/O.
- Pool settings are tuned for a small-to-medium production workload.
- `get_db()` is the standard FastAPI dependency; it auto-commits on success
  and rolls back on any unhandled exception.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Async Engine ───────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,   # Recycle dead connections automatically
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,    # Recycle connections every 30 min (prevents stale conn issues)
)

# ── Session Factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep object attributes accessible after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields an AsyncSession per request.

    Automatically:
    - Commits on clean exit
    - Rolls back on any exception
    - Closes the session in all cases

    Usage:
        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning("db_session_rolled_back", exc_info=True)
            raise
        finally:
            await session.close()
