"""Readiness endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import requires_infrastructure, requires_redis

pytestmark = pytest.mark.integration


def test_healthz_returns_ok_without_dependencies() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",
        REDIS_URL="redis://127.0.0.1:1/0",
        JWT_SECRET="test-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@requires_infrastructure
def test_readyz_returns_200_when_dependencies_are_available(
    database_url: str, redis_url: str
) -> None:
    app = create_app(
        Settings(DATABASE_URL=database_url, REDIS_URL=redis_url, JWT_SECRET="test-secret")
    )

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": True, "redis": True},
    }


@requires_redis
def test_readyz_returns_503_when_database_is_unreachable(redis_url: str) -> None:
    app = create_app(
        Settings(
            DATABASE_URL="postgresql+asyncpg://enrollio:enrollio@127.0.0.1:1/enrollio",
            REDIS_URL=redis_url,
            JWT_SECRET="test-secret",
        )
    )

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": False, "redis": True},
    }
