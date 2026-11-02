"""Refresh-token queries and bulk revocation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


async def get_by_hash_for_update(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    """Lock and return the token row, so concurrent refreshes cannot both win."""
    return await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )


async def revoke_family(session: AsyncSession, family_id: uuid.UUID, now: datetime) -> None:
    """Revoke every token in a session family."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    """Revoke every refresh token belonging to a user."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
