"""Unit tests for the test-database guard."""

from __future__ import annotations

import pytest

from tests.conftest import is_test_database


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql+asyncpg://u:p@localhost:5432/enrollio_test", True),
        ("postgresql+asyncpg://u:p@localhost:5432/enrollio_test/", True),
        ("postgresql+asyncpg://u:p@localhost:5432/enrollio", False),
        ("postgresql+asyncpg://u:p@localhost:5432/enrollio_production", False),
        ("postgresql+asyncpg://u:p@localhost:5432/testing", False),
    ],
)
def test_is_test_database(url: str, expected: bool) -> None:
    assert is_test_database(url) is expected
