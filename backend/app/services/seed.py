"""Idempotent seed routines for RBAC and development demo accounts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.permissions import (
    PERMISSION_DESCRIPTIONS,
    ROLE_DEFINITIONS,
    RoleSlug,
    all_permission_names,
)
from app.core.security import hash_password
from app.models.associations import role_permissions, user_roles
from app.models.campus import Campus
from app.models.lead_source import LeadSource
from app.models.permission import Permission
from app.models.programme import Programme
from app.models.role import Role
from app.models.user import User

DEMO_USERS: tuple[tuple[str, str, RoleSlug], ...] = (
    ("admin@enrollio.dev", "System Admin", RoleSlug.SYSTEM_ADMIN),
    ("manager@enrollio.dev", "Admission Manager", RoleSlug.ADMISSION_MANAGER),
    ("counsellor@enrollio.dev", "Admission Counsellor", RoleSlug.ADMISSION_COUNSELLOR),
)

# Demo accounts used before D-023. Seeding removes them so a development
# database does not end up with two accounts per role.
LEGACY_DEMO_EMAILS: tuple[str, ...] = (
    "admin@example.test",
    "manager@example.test",
    "counsellor@example.test",
)

DEMO_PROGRAMMES: tuple[tuple[str, str], ...] = (
    ("B.Tech Computer Science", "BTECH-CSE"),
    ("BBA", "BBA"),
    ("MBA", "MBA"),
    ("B.Sc Data Science", "BSC-DS"),
)
DEMO_CAMPUSES: tuple[tuple[str, str], ...] = (
    ("Main Campus", "Pune"),
    ("North Campus", "Delhi"),
)
DEMO_LEAD_SOURCES: tuple[str, ...] = (
    "Website",
    "Education Fair",
    "Referral",
    "Coaching Partner",
)


@dataclass(frozen=True)
class SeedResult:
    roles: int
    permissions: int
    role_permission_links: int
    demo_users: int
    programmes: int
    campuses: int
    lead_sources: int


async def seed_rbac(session: AsyncSession) -> tuple[int, int, int]:
    """Upsert the permission catalog, roles, and role-permission matrix.

    The matrix is replaced, not merged, so changing ``ROLE_PERMISSIONS`` is
    enough to correct drift. Running this repeatedly is safe.
    """
    permission_values = [
        {"name": permission.value, "description": PERMISSION_DESCRIPTIONS[permission]}
        for permission in all_permission_names()
    ]
    permission_insert = pg_insert(Permission).values(permission_values)
    await session.execute(
        permission_insert.on_conflict_do_update(
            index_elements=[Permission.name],
            set_={"description": permission_insert.excluded.description},
        )
    )

    role_values = [
        {
            "slug": definition.slug.value,
            "name": definition.name,
            "description": definition.description,
        }
        for definition in ROLE_DEFINITIONS
    ]
    role_insert = pg_insert(Role).values(role_values)
    await session.execute(
        role_insert.on_conflict_do_update(
            index_elements=[Role.slug],
            set_={
                "name": role_insert.excluded.name,
                "description": role_insert.excluded.description,
            },
        )
    )
    await session.flush()

    permissions_by_name = {
        permission.name: permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    roles_by_slug = {role.slug: role for role in (await session.execute(select(Role))).scalars()}

    role_ids = [role.id for role in roles_by_slug.values()]
    await session.execute(delete(role_permissions).where(role_permissions.c.role_id.in_(role_ids)))

    links = [
        {
            "role_id": roles_by_slug[definition.slug.value].id,
            "permission_id": permissions_by_name[permission.value].id,
        }
        for definition in ROLE_DEFINITIONS
        for permission in definition.permissions
    ]
    if links:
        await session.execute(pg_insert(role_permissions).values(links).on_conflict_do_nothing())

    return len(role_values), len(permission_values), len(links)


async def seed_demo_users(session: AsyncSession, settings: Settings) -> int:
    """Create the three demo accounts and their roles, without duplicates."""
    await session.execute(delete(User).where(User.email.in_(LEGACY_DEMO_EMAILS)))

    password_hash = hash_password(settings.SEED_DEMO_PASSWORD.get_secret_value(), settings)

    for email, full_name, _ in DEMO_USERS:
        insert_user = pg_insert(User).values(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
        )
        await session.execute(insert_user.on_conflict_do_nothing(index_elements=[User.email]))
    await session.flush()

    emails = [email for email, _, _ in DEMO_USERS]
    users_by_email = {
        user.email: user
        for user in (await session.execute(select(User).where(User.email.in_(emails)))).scalars()
    }
    roles_by_slug = {role.slug: role for role in (await session.execute(select(Role))).scalars()}

    for email, _, role_slug in DEMO_USERS:
        user = users_by_email[email]
        role = roles_by_slug[role_slug.value]
        link = pg_insert(user_roles).values(user_id=user.id, role_id=role.id)
        await session.execute(link.on_conflict_do_nothing())

    return len(DEMO_USERS)


async def seed_catalogues(session: AsyncSession) -> tuple[int, int, int]:
    """Create the demo programmes, campuses, and lead sources once."""
    existing_programmes = set((await session.execute(select(Programme.name))).scalars())
    for name, code in DEMO_PROGRAMMES:
        if name not in existing_programmes:
            session.add(Programme(name=name, code=code))

    existing_campuses = set((await session.execute(select(Campus.name))).scalars())
    for name, city in DEMO_CAMPUSES:
        if name not in existing_campuses:
            session.add(Campus(name=name, city=city))

    existing_sources = set((await session.execute(select(LeadSource.name))).scalars())
    for name in DEMO_LEAD_SOURCES:
        if name not in existing_sources:
            session.add(LeadSource(name=name))

    await session.flush()
    return len(DEMO_PROGRAMMES), len(DEMO_CAMPUSES), len(DEMO_LEAD_SOURCES)


async def seed_all(session: AsyncSession, settings: Settings) -> SeedResult:
    """Seed RBAC and, outside production, the demo accounts and catalogue."""
    roles, permissions, links = await seed_rbac(session)
    demo_users = 0
    programmes = 0
    campuses = 0
    lead_sources = 0
    if settings.SEED_DEMO_USERS:
        demo_users = await seed_demo_users(session, settings)
        programmes, campuses, lead_sources = await seed_catalogues(session)

    return SeedResult(
        roles=roles,
        permissions=permissions,
        role_permission_links=links,
        demo_users=demo_users,
        programmes=programmes,
        campuses=campuses,
        lead_sources=lead_sources,
    )
