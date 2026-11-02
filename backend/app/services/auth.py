"""Authentication service: login, refresh rotation, and logout."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories import refresh_tokens as refresh_repo
from app.repositories import users as users_repo


class AuthenticationError(Exception):
    """Credentials are invalid, the account is inactive, or it is locked."""


class RefreshTokenError(Exception):
    """The refresh token is unknown, expired, or revoked."""


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> IssuedTokens:
    """Authenticate and start a new refresh-token family."""
    current = now or datetime.now(UTC)
    user = await users_repo.get_by_email(session, email.strip().lower())

    if user is None:
        # Spend the same work as a real verification so timing does not reveal
        # whether the email exists.
        verify_dummy_password(password, settings)
        raise AuthenticationError

    password_ok = verify_password(password, user.password_hash, settings)
    locked = user.locked_until is not None and user.locked_until > current
    if not password_ok or not user.is_active or locked:
        if not password_ok and user.is_active:
            _record_failure(user, settings, current)
            await session.commit()
        raise AuthenticationError

    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None
    user.last_login_at = current
    if needs_rehash(user.password_hash, settings):
        user.password_hash = hash_password(password, settings)

    tokens = await _start_family(session, settings, user, current, user_agent)
    await session.commit()
    return tokens


async def rotate(
    session: AsyncSession,
    settings: Settings,
    *,
    raw_token: str,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> IssuedTokens:
    """Rotate a refresh token, revoking the family when reuse is detected."""
    current = now or datetime.now(UTC)
    token = await refresh_repo.get_by_hash_for_update(session, hash_refresh_token(raw_token))

    if token is None:
        raise RefreshTokenError

    if token.revoked_at is not None:
        if token.replaced_by_id is not None:
            # A rotated token was presented again: assume theft and kill the
            # whole session family.
            await refresh_repo.revoke_family(session, token.family_id, current)
            await session.commit()
        raise RefreshTokenError

    if token.expires_at <= current:
        raise RefreshTokenError

    user = await users_repo.get_with_permissions(session, token.user_id)
    if user is None or not user.is_active:
        await refresh_repo.revoke_family(session, token.family_id, current)
        await session.commit()
        raise RefreshTokenError

    new_raw_token = generate_refresh_token()
    successor = RefreshToken(
        user_id=user.id,
        family_id=token.family_id,
        token_hash=hash_refresh_token(new_raw_token),
        expires_at=current + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=_clean_user_agent(user_agent),
    )
    session.add(successor)
    await session.flush()

    token.revoked_at = current
    token.replaced_by_id = successor.id
    await session.commit()

    return IssuedTokens(
        access_token=create_access_token(user.id, settings, current),
        refresh_token=new_raw_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout(
    session: AsyncSession, *, raw_token: str | None, now: datetime | None = None
) -> None:
    """Revoke the whole family behind ``raw_token`` (idempotent)."""
    if not raw_token:
        return

    current = now or datetime.now(UTC)
    token = await refresh_repo.get_by_hash_for_update(session, hash_refresh_token(raw_token))
    if token is None:
        return

    await refresh_repo.revoke_family(session, token.family_id, current)
    await session.commit()


async def revoke_all_sessions(
    session: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> None:
    """Revoke every refresh token for a user (used when deactivating)."""
    await refresh_repo.revoke_all_for_user(session, user_id, now or datetime.now(UTC))
    await session.commit()


async def _start_family(
    session: AsyncSession,
    settings: Settings,
    user: User,
    now: datetime,
    user_agent: str | None,
) -> IssuedTokens:
    raw_token = generate_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash=hash_refresh_token(raw_token),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=_clean_user_agent(user_agent),
    )
    session.add(record)
    await session.flush()

    return IssuedTokens(
        access_token=create_access_token(user.id, settings, now),
        refresh_token=raw_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _record_failure(user: User, settings: Settings, now: datetime) -> None:
    window_start = now - timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES)
    if user.last_failed_login_at is None or user.last_failed_login_at < window_start:
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1

    user.last_failed_login_at = now
    if user.failed_login_count >= settings.LOGIN_MAX_FAILURES:
        user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def _clean_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return user_agent[:255]
