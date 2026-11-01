"""Shared pytest fixtures and environment probes."""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest

DEFAULT_DATABASE_URL = "postgresql+asyncpg://enrollio:enrollio@localhost:5432/enrollio"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

DATABASE_URL = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
REDIS_URL = os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", DEFAULT_REDIS_URL))


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

requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE, reason=f"PostgreSQL is not reachable at {DATABASE_URL}"
)
requires_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE, reason=f"Redis is not reachable at {REDIS_URL}"
)
requires_infrastructure = pytest.mark.skipif(
    not (POSTGRES_AVAILABLE and REDIS_AVAILABLE),
    reason="PostgreSQL and Redis are required",
)


@pytest.fixture
def database_url() -> str:
    return DATABASE_URL


@pytest.fixture
def redis_url() -> str:
    return REDIS_URL
