"""Integration-test bootstrap: apply migrations to the test database once."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

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
