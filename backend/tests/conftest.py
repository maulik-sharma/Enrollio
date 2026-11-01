"""Shared pytest fixtures and environment probes."""

from __future__ import annotations

import os
import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine

DEFAULT_DATABASE_URL = "postgresql+asyncpg://enrollio:enrollio@localhost:5432/enrollio_test"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# Integration tests always use TEST_DATABASE_URL. There is deliberately no
# fallback to DATABASE_URL: the migration test downgrades to base and must never
# touch the development database (risk R-001).
DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL") or get_settings().TEST_DATABASE_URL or DEFAULT_DATABASE_URL
)
REDIS_URL = os.getenv("TEST_REDIS_URL") or os.getenv("REDIS_URL") or DEFAULT_REDIS_URL

IS_CI = os.getenv("CI", "").lower() in {"1", "true", "yes"}


def is_test_database(url: str) -> bool:
    """Return True when the URL points at a database named `*_test`."""
    database = urlparse(url).path.strip("/")
    return database.endswith("_test")


def _port_is_open(url: str, default_port: int) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


POSTGRES_AVAILABLE = _port_is_open(DATABASE_URL, 5432)
REDIS_AVAILABLE = _port_is_open(REDIS_URL, 6379)

# Locally, missing infrastructure skips integration tests. In CI the same
# condition is an error so a broken service container cannot silently pass.
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE and not IS_CI,
    reason=f"PostgreSQL is not reachable at {DATABASE_URL}",
)
requires_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE and not IS_CI,
    reason=f"Redis is not reachable at {REDIS_URL}",
)
requires_infrastructure = pytest.mark.skipif(
    not (POSTGRES_AVAILABLE and REDIS_AVAILABLE) and not IS_CI,
    reason="PostgreSQL and Redis are required",
)


@pytest.fixture(scope="session")
def database_url() -> str:
    return DATABASE_URL


@pytest.fixture(scope="session")
def redis_url() -> str:
    return REDIS_URL


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Engine for the dedicated test database."""
    if not POSTGRES_AVAILABLE:
        pytest.skip(f"PostgreSQL is not reachable at {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def clean_database(db_engine: AsyncEngine) -> AsyncIterator[None]:
    """Empty every application table before a test.

    Table names are discovered at runtime so the fixture keeps working as the
    schema grows.
    """
    async with db_engine.begin() as connection:
        rows = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in rows if row[0] != "alembic_version"]
        if tables:
            quoted = ", ".join(f'"{table}"' for table in tables)
            await connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    yield
