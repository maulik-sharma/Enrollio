"""Integration-test bootstrap: apply migrations to the test database once."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Environment, Settings
from app.main import create_app
from app.services.seed import seed_all
from tests.conftest import DATABASE_URL, POSTGRES_AVAILABLE, is_test_database

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Iterator[None]:
    if not POSTGRES_AVAILABLE:
        yield
        return

    if not is_test_database(DATABASE_URL):
        pytest.fail(
            f"Refusing to migrate {DATABASE_URL!r}: the database name must end with '_test'."
        )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": DATABASE_URL},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "Could not migrate the test database. Run `make create-test-db` first.\n"
            f"{result.stderr}"
        )
    yield


@pytest.fixture
def test_settings(database_url: str) -> Settings:
    """Hermetic settings for API tests."""
    return Settings(
        ENV=Environment.test,
        DATABASE_URL=database_url,
        JWT_SECRET="integration-test-secret-key-32-chars",
        ACCESS_TOKEN_EXPIRE_MINUTES=15,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        LOGIN_MAX_FAILURES=5,
        LOGIN_FAILURE_WINDOW_MINUTES=15,
        LOGIN_LOCKOUT_MINUTES=15,
        ARGON2_TIME_COST=1,
        ARGON2_MEMORY_COST=8192,
        ARGON2_PARALLELISM=1,
        CORS_ORIGINS="http://localhost:3000",
        SEED_DEMO_USERS=True,
        SEED_DEMO_PASSWORD="demo-password-123",
        _env_file=None,
    )


@pytest.fixture
async def seeded_database(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    async with db_session_factory() as session:
        await seed_all(session, test_settings)
        await session.commit()


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
async def app_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
        ) as client,
    ):
        yield client
