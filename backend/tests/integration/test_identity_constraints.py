"""Database constraints protecting identity data."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from tests.conftest import requires_postgres

pytestmark = pytest.mark.integration

TEST_HASH_SETTINGS = Settings(
    JWT_SECRET="test-secret",
    ARGON2_TIME_COST=1,
    ARGON2_MEMORY_COST=8192,
    ARGON2_PARALLELISM=1,
    _env_file=None,
)


def _user(email: str) -> User:
    return User(
        email=email,
        password_hash=hash_password("password-123", TEST_HASH_SETTINGS),
        full_name="Test User",
    )


@requires_postgres
async def test_duplicate_email_is_rejected(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(_user("duplicate@enrollio.dev"))
        await session.commit()

    async with db_session_factory() as session:
        session.add(_user("duplicate@enrollio.dev"))
        with pytest.raises(IntegrityError):
            await session.commit()


@requires_postgres
async def test_uppercase_email_is_rejected(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(_user("MixedCase@enrollio.dev"))
        with pytest.raises(IntegrityError):
            await session.commit()


@requires_postgres
async def test_duplicate_role_slug_is_rejected(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(Role(slug="manager", name="Manager", description=""))
        await session.commit()

    async with db_session_factory() as session:
        session.add(Role(slug="manager", name="Another Manager", description=""))
        with pytest.raises(IntegrityError):
            await session.commit()
