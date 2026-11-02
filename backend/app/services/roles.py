"""Role administration services."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.models.role import Role
from app.repositories import roles as roles_repo


class RoleNotFound(Exception):
    """No role has the requested id."""


class UnknownPermission(Exception):
    """One or more permission names are not in the database catalog."""

    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(f"Unknown permissions: {', '.join(names)}")


async def list_roles(session: AsyncSession) -> list[Role]:
    """Return every role with its permissions."""
    return await roles_repo.list_roles(session)


async def set_role_permissions(
    session: AsyncSession, role_id: uuid.UUID, permission_names: list[str]
) -> Role:
    """Replace the permissions granted by a role."""
    role = await roles_repo.get_by_id(session, role_id)
    if role is None:
        raise RoleNotFound

    permissions = list(
        (await session.execute(select(Permission).where(Permission.name.in_(permission_names))))
        .scalars()
        .all()
    )
    missing = sorted(set(permission_names) - {permission.name for permission in permissions})
    if missing:
        raise UnknownPermission(missing)

    role.permissions = permissions
    await session.commit()
    return role
