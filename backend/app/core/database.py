"""PostgreSQL engine helpers."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

CHECK_TIMEOUT_SECONDS = 2.0
DEFAULT_DATABASE_URL = "postgresql+asyncpg://enrollio:enrollio@localhost:5432/enrollio"


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async engine. Connections are opened lazily."""
    return create_async_engine(database_url, pool_pre_ping=True)


async def ping_database(engine: AsyncEngine) -> bool:
    """Return True when a simple query succeeds within the timeout."""
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
