"""Role administration endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep, require_permission
from app.core.permissions import PermissionName
from app.models.role import Role
from app.schemas.roles import RolePermissionsUpdate, RoleRead
from app.services import roles as roles_service
from app.services.roles import RoleNotFound, UnknownPermission

router = APIRouter(prefix="/api/roles", tags=["roles"])


def _role_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        permissions=sorted(permission.name for permission in role.permissions),
    )


@router.get(
    "",
    response_model=list[RoleRead],
    dependencies=[Depends(require_permission(PermissionName.USERS_MANAGE))],
)
async def list_roles(session: SessionDep) -> list[RoleRead]:
    """List roles and the permissions they grant.

    User administration needs this to populate the role picker, so
    ``users.manage`` is enough; editing permissions needs ``roles.manage``.
    """
    roles = await roles_service.list_roles(session)
    return [_role_read(role) for role in roles]


@router.put(
    "/{role_id}/permissions",
    response_model=RoleRead,
    dependencies=[Depends(require_permission(PermissionName.ROLES_MANAGE))],
)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdate,
    session: SessionDep,
) -> RoleRead:
    """Replace the permissions granted by a role."""
    try:
        role = await roles_service.set_role_permissions(session, role_id, payload.permissions)
    except RoleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        ) from exc
    except UnknownPermission as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _role_read(role)
