"""Permission catalog invariants."""

from __future__ import annotations

from app.core.permissions import (
    ROLE_DEFINITIONS,
    ROLE_PERMISSIONS,
    PermissionName,
    RoleSlug,
    all_permission_names,
)


def test_catalog_has_no_duplicates() -> None:
    names = [permission.value for permission in all_permission_names()]

    assert len(names) == len(set(names))


def test_every_role_is_in_the_matrix() -> None:
    assert set(ROLE_PERMISSIONS) == set(RoleSlug)


def test_roles_do_not_share_permissions() -> None:
    seen: dict[PermissionName, RoleSlug] = {}
    for definition in ROLE_DEFINITIONS:
        for permission in definition.permissions:
            assert permission not in seen, f"{permission} is granted to two roles"
            seen[permission] = definition.slug

    assert set(seen) == set(PermissionName)


def test_system_admin_can_manage_users_and_roles() -> None:
    permissions = ROLE_PERMISSIONS[RoleSlug.SYSTEM_ADMIN]

    assert PermissionName.USERS_MANAGE in permissions
    assert PermissionName.ROLES_MANAGE in permissions


def test_counsellor_cannot_view_all_leads() -> None:
    permissions = ROLE_PERMISSIONS[RoleSlug.ADMISSION_COUNSELLOR]

    assert PermissionName.LEADS_VIEW_ASSIGNED in permissions
    assert PermissionName.LEADS_VIEW_ALL not in permissions
