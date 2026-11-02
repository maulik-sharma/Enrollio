"""User administration services.

Every write happens here so routers and future agent tools share the same
rules: emails are normalised, roles must exist, passwords are hashed, and
deactivating a user or changing their password revokes their sessions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user import User
from app.repositories import refresh_tokens as refresh_repo
from app.repositories import roles as roles_repo
from app.repositories import users as users_repo


class UserNotFound(Exception):
    """No user has the requested id."""


class EmailAlreadyExists(Exception):
    """Another account already uses the email."""


class UnknownRole(Exception):
    """One or more role slugs are not in the catalog."""

    def __init__(self, slugs: list[str]) -> None:
        self.slugs = slugs
        super().__init__(f"Unknown roles: {', '.join(slugs)}")


async def list_users(session: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[User]:
    """Return users with their roles."""
    return await users_repo.list_users(session, limit=limit, offset=offset)


async def create_user(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    full_name: str,
    password: str,
    role_slugs: list[str],
) -> User:
    """Create an active user with the given roles."""
    normalized = email.strip().lower()
    if await users_repo.get_by_email(session, normalized) is not None:
        raise EmailAlreadyExists

    roles = await roles_repo.get_by_slugs(session, role_slugs)
    missing = sorted(set(role_slugs) - {role.slug for role in roles})
    if missing:
        raise UnknownRole(missing)

    user = User(
        email=normalized,
        password_hash=hash_password(password, settings),
        full_name=full_name.strip(),
    )
    user.roles = roles
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # A concurrent request created the same email between the check and the
        # insert; the unique constraint is the source of truth.
        await session.rollback()
        raise EmailAlreadyExists from exc

    return user


async def update_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings | None = None,
    full_name: str | None = None,
    password: str | None = None,
    is_active: bool | None = None,
    role_slugs: list[str] | None = None,
) -> User:
    """Update profile fields, roles, password, or active state."""
    user = await users_repo.get_with_permissions(session, user_id)
    if user is None:
        raise UserNotFound

    revoke_sessions = False

    if full_name is not None:
        user.full_name = full_name.strip()

    if password is not None:
        if settings is None:
            raise ValueError("settings are required when changing a password")
        user.password_hash = hash_password(password, settings)
        revoke_sessions = True

    if role_slugs is not None:
        roles = await roles_repo.get_by_slugs(session, role_slugs)
        missing = sorted(set(role_slugs) - {role.slug for role in roles})
        if missing:
            raise UnknownRole(missing)
        user.roles = roles

    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        if not is_active:
            revoke_sessions = True

    if revoke_sessions:
        await refresh_repo.revoke_all_for_user(session, user.id, datetime.now(UTC))

    await session.commit()
    return user


async def deactivate_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Deactivate a user and revoke every session (idempotent)."""
    return await update_user(session, user_id=user_id, is_active=False)
