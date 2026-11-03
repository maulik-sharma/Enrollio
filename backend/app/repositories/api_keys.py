"""API key lookups."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


async def get_active_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    """Return an active, unexpired key with this hash."""
    now = datetime.now(UTC)
    return await session.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
            or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
        )
    )
