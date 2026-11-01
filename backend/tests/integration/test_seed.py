"""RBAC and demo-user seeding is complete, correct, and idempotent."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Environment, Settings
from app.core.permissions import ROLE_DEFINITIONS, RoleSlug
from app.core.security import verify_password
from app.models.associations import role_permissions, user_roles
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.seed import seed_all
from tests.conftest import requires_postgres

pytestmark = pytest.mark.integration

EXPECTED_ROLES = len(ROLE_DEFINITIONS)
EXPECTED_PERMISSIONS = 17
EXPECTED_LINKS = sum(len(definition.permissions) for definition in ROLE_DEFINITIONS)


@pytest.fixture
def seed_settings(database_url: str) -> Settings:
    return Settings(
        ENV=Environment.test,
        DATABASE_URL=database_url,
        JWT_SECRET="test-secret",
        SEED_DEMO_USERS=True,
        SEED_DEMO_PASSWORD="demo-password-123",
        ARGON2_TIME_COST=1,
        ARGON2_MEMORY_COST=8192,
        ARGON2_PARALLELISM=1,
        _env_file=None,
    )


@requires_postgres
async def test_seed_is_idempotent_and_matches_the_matrix(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    seed_settings: Settings,
) -> None:
    async with db_session_factory() as session:
        first = await seed_all(session, seed_settings)
        await session.commit()
    async with db_session_factory() as session:
        second = await seed_all(session, seed_settings)
        await session.commit()

    assert first == second
    assert first.roles == EXPECTED_ROLES
    assert first.permissions == EXPECTED_PERMISSIONS
    assert first.role_permission_links == EXPECTED_LINKS
    assert first.demo_users == 3

    async with db_session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Role))).scalar_one() == 3
        assert (
            await session.execute(select(func.count()).select_from(Permission))
        ).scalar_one() == EXPECTED_PERMISSIONS
        assert (
            await session.execute(select(func.count()).select_from(role_permissions))
        ).scalar_one() == EXPECTED_LINKS
        assert (await session.execute(select(func.count()).select_from(User))).scalar_one() == 3
        assert (
            await session.execute(select(func.count()).select_from(user_roles))
        ).scalar_one() == 3

        roles = (
            (
                await session.execute(
                    select(Role).where(Role.slug.in_([d.slug.value for d in ROLE_DEFINITIONS]))
                )
            )
            .scalars()
            .all()
        )
        matrix = {role.slug: {permission.name for permission in role.permissions} for role in roles}

    assert matrix == {
        definition.slug.value: {permission.value for permission in definition.permissions}
        for definition in ROLE_DEFINITIONS
    }


@requires_postgres
async def test_demo_users_can_log_in_with_the_seed_password(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    seed_settings: Settings,
) -> None:
    async with db_session_factory() as session:
        await seed_all(session, seed_settings)
        await session.commit()

    async with db_session_factory() as session:
        users = (await session.execute(select(User))).scalars().all()
        by_email = {user.email: user for user in users}

    assert set(by_email) == {
        "admin@example.test",
        "manager@example.test",
        "counsellor@example.test",
    }
    for user in by_email.values():
        assert verify_password("demo-password-123", user.password_hash, seed_settings)
        assert [role.slug for role in user.roles] == [
            {
                "admin@example.test": RoleSlug.SYSTEM_ADMIN.value,
                "manager@example.test": RoleSlug.ADMISSION_MANAGER.value,
                "counsellor@example.test": RoleSlug.ADMISSION_COUNSELLOR.value,
            }[user.email]
        ]
        assert user.is_active is True
