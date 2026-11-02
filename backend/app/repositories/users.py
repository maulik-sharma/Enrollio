"""User queries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role
from app.models.user import User

USER_WITH_PERMISSIONS = selectinload(User.roles).selectinload(Role.permissions)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    """Return the user with ``email`` (already normalised), or None."""
    return await session.scalar(select(User).where(User.email == email))


async def get_with_permissions(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Return the user with roles and permissions eagerly loaded."""
    return await session.scalar(
        select(User).options(USER_WITH_PERMISSIONS).where(User.id == user_id)
    )


async def list_users(session: AsyncSession, *, limit: int, offset: int) -> list[User]:
    result = await session.execute(
        select(User)
        .options(USER_WITH_PERMISSIONS)
        .order_by(User.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars())
