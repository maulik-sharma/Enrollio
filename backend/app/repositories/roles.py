"""Role queries."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role


async def list_roles(session: AsyncSession) -> list[Role]:
    """Return every role with its permissions, ordered by slug."""
    result = await session.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.slug)
    )
    return list(result.scalars())


async def get_by_id(session: AsyncSession, role_id: uuid.UUID) -> Role | None:
    """Return one role with its permissions."""
    return await session.scalar(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )


async def get_by_slugs(session: AsyncSession, slugs: Sequence[str]) -> list[Role]:
    """Return the roles whose slugs are in ``slugs``."""
    if not slugs:
        return []
    result = await session.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.slug.in_(slugs))
    )
    return list(result.scalars())
