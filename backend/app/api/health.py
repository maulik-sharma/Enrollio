"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.database import ping_database
from app.core.redis import ping_redis

router = APIRouter(tags=["health"])


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe: the process is up."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(request: Request) -> JSONResponse:
    """Readiness probe: the database and Redis are reachable."""
    state: Any = request.app.state
    database_ok = await ping_database(state.db_engine)
    redis_ok = await ping_redis(state.redis_client)
    ready = database_ok and redis_ok

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "unavailable",
            "checks": {"database": database_ok, "redis": redis_ok},
        },
    )
