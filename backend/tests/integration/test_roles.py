"""Role administration: listing and replacing role permissions."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient, Response

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN = "admin@enrollio.dev"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"
PASSWORD = "demo-password-123"


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _roles(client: AsyncClient, token: str) -> list[dict[str, Any]]:
    response = await client.get("/api/roles", headers=_auth(token))
    assert response.status_code == 200, response.text
    return list(response.json())


async def test_admin_lists_roles_with_permissions(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    roles = await _roles(app_client, admin)

    by_slug = {str(role["slug"]): role for role in roles}
    assert set(by_slug) == {
        "system_admin",
        "admission_manager",
        "admission_counsellor",
    }
    assert by_slug["system_admin"]["permissions"] == sorted(
        ["users.manage", "roles.manage", "knowledge.manage", "integrations.manage", "audit.view"]
    )
    assert "leads.view_all" in by_slug["admission_manager"]["permissions"]
    assert "leads.view_assigned" in by_slug["admission_counsellor"]["permissions"]


async def test_non_admins_cannot_list_or_edit_roles(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    roles = await _roles(app_client, admin)
    counsellor_role = next(role for role in roles if role["slug"] == "admission_counsellor")

    for email in (MANAGER, COUNSELLOR):
        token = await _token(app_client, email)
        listed = await app_client.get("/api/roles", headers=_auth(token))
        edited = await app_client.put(
            f"/api/roles/{counsellor_role['id']}/permissions",
            json={"permissions": []},
            headers=_auth(token),
        )
        assert listed.status_code == 403, email
        assert edited.status_code == 403, email


async def test_admin_replaces_role_permissions_and_users_see_it(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    roles = await _roles(app_client, admin)
    counsellor_role = next(role for role in roles if role["slug"] == "admission_counsellor")

    new_permissions = ["leads.view_assigned", "messages.send_own", "audit.view"]
    updated = await app_client.put(
        f"/api/roles/{counsellor_role['id']}/permissions",
        json={"permissions": new_permissions},
        headers=_auth(admin),
    )

    assert updated.status_code == 200
    assert updated.json()["permissions"] == sorted(new_permissions)

    login = await app_client.post(
        "/api/auth/login", json={"email": COUNSELLOR, "password": PASSWORD}
    )
    me = await app_client.get("/api/auth/me", headers=_auth(login.json()["access_token"]))
    assert sorted(me.json()["permissions"]) == sorted(new_permissions)


async def test_unknown_permission_and_role_are_rejected(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    roles = await _roles(app_client, admin)
    counsellor_role = next(role for role in roles if role["slug"] == "admission_counsellor")
    missing_role = "00000000-0000-0000-0000-000000000000"

    unknown_permission = await app_client.put(
        f"/api/roles/{counsellor_role['id']}/permissions",
        json={"permissions": ["not.a.permission"]},
        headers=_auth(admin),
    )
    unknown_role = await app_client.put(
        f"/api/roles/{missing_role}/permissions",
        json={"permissions": []},
        headers=_auth(admin),
    )

    assert unknown_permission.status_code == 400
    assert unknown_role.status_code == 404


async def test_role_permissions_require_authentication(app_client: AsyncClient) -> None:
    response: Response = await app_client.get("/api/roles")
    assert response.status_code == 401
