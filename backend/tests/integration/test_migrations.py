"""Migration tests: the first migration enables extensions and is reversible.

These tests run against ``TEST_DATABASE_URL`` and deliberately refuse to touch a
database whose name does not end with ``_test`` (risk R-001).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import is_test_database, requires_postgres

BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_EXTENSIONS = {"vector", "btree_gist", "pgcrypto"}
EXPECTED_TABLES = {
    "users",
    "roles",
    "permissions",
    "refresh_tokens",
    "students",
    "leads",
    "programmes",
    "campuses",
    "lead_sources",
    "consent_records",
    "timeline_events",
    "import_jobs",
    "mapping_templates",
    "import_row_results",
    "duplicate_candidates",
    "api_keys",
    "mock_email_messages",
    "conversations",
    "messages",
    "message_events",
    "message_templates",
    "approval_items",
}


def _run_alembic(*args: str, database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


async def _installed_extensions(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("SELECT extname FROM pg_extension"))
            return {row[0] for row in rows}
    finally:
        await engine.dispose()


async def _tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            return {row[0] for row in rows}
    finally:
        await engine.dispose()


@requires_postgres
async def test_extensions_enabled_and_migration_is_reversible(database_url: str) -> None:
    if not is_test_database(database_url):
        pytest.fail(
            "Refusing to run a destructive migration test against "
            f"{database_url!r}: the database name must end with '_test' (R-001)."
        )

    _run_alembic("downgrade", "base", database_url=database_url)
    _run_alembic("upgrade", "head", database_url=database_url)

    assert await _installed_extensions(database_url) >= EXPECTED_EXTENSIONS
    assert await _tables(database_url) >= EXPECTED_TABLES

    _run_alembic("downgrade", "base", database_url=database_url)
    assert not EXPECTED_EXTENSIONS & await _installed_extensions(database_url)
    assert not EXPECTED_TABLES & await _tables(database_url)

    _run_alembic("upgrade", "head", database_url=database_url)
    assert await _installed_extensions(database_url) >= EXPECTED_EXTENSIONS
