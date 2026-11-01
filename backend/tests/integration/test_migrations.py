"""Migration tests: the first migration enables extensions and is reversible."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import requires_postgres

BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_EXTENSIONS = {"vector", "btree_gist", "pgcrypto"}


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


@requires_postgres
async def test_extensions_enabled_and_migration_is_reversible(database_url: str) -> None:
    _run_alembic("downgrade", "base", database_url=database_url)
    _run_alembic("upgrade", "head", database_url=database_url)

    assert await _installed_extensions(database_url) >= EXPECTED_EXTENSIONS

    _run_alembic("downgrade", "base", database_url=database_url)
    assert not EXPECTED_EXTENSIONS & await _installed_extensions(database_url)

    _run_alembic("upgrade", "head", database_url=database_url)
    assert await _installed_extensions(database_url) >= EXPECTED_EXTENSIONS
