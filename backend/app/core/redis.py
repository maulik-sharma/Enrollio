"""Redis client helpers."""

from __future__ import annotations

import asyncio
from typing import cast

from redis.asyncio import Redis

CHECK_TIMEOUT_SECONDS = 2.0
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def create_redis_client(redis_url: str) -> Redis:
    """Create a Redis client. Connections are opened lazily."""
    return cast(
        Redis,
        Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        ),
    )


async def ping_redis(client: Redis) -> bool:
    """Return True when Redis responds to PING within the timeout."""
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            return bool(await client.ping())
    except Exception:
        return False
