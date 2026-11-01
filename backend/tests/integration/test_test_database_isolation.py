"""R-001: destructive migration tests must never touch the development database."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from tests.conftest import is_test_database, requires_postgres
from tests.integration.test_migrations import _run_alembic

pytestmark = pytest.mark.integration


def _development_url() -> str:
    return os.getenv("DATABASE_URL") or get_settings().DATABASE_URL


@requires_postgres
def test_test_database_is_distinct_from_development_database(database_url: str) -> None:
    assert is_test_database(database_url)

    development_url = _development_url()
    assert urlparse(development_url).path != urlparse(database_url).path


@requires_postgres
async def test_migration_downgrade_leaves_the_development_database_untouched(
    database_url: str,
) -> None:
    development_url = _development_url()
    if urlparse(development_url).path == urlparse(database_url).path:
        pytest.skip("No separate development database is configured")

    development_engine = create_async_engine(development_url)
    sentinel = str(uuid.uuid4())
    try:
        async with development_engine.begin() as connection:
            await connection.execute(
                text("CREATE TABLE IF NOT EXISTS _r001_sentinel (value text NOT NULL)")
            )
            await connection.execute(
                text("INSERT INTO _r001_sentinel (value) VALUES (:value)"), {"value": sentinel}
            )

        # This is the destructive call the migration test makes.
        _run_alembic("downgrade", "base", database_url=database_url)
        _run_alembic("upgrade", "head", database_url=database_url)

        async with development_engine.connect() as connection:
            result = await connection.execute(text("SELECT value FROM _r001_sentinel"))
            assert [row[0] for row in result] == [sentinel]
    finally:
        async with development_engine.begin() as connection:
            await connection.execute(text("DROP TABLE IF EXISTS _r001_sentinel"))
        await development_engine.dispose()
