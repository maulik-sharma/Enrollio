"""User administration: creation, updates, deactivation, and access control."""

from __future__ import annotations

from typing import TypedDict

from httpx import AsyncClient, Response

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN = "admin@enrollio.dev"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"
PASSWORD = "demo-password-123"


class _NewUser(TypedDict):
    email: str
    full_name: str
    password: str
    roles: list[str]


NEW_USER: _NewUser = {
    "email": "new.counsellor@enrollio.dev",
    "full_name": "New Counsellor",
    "password": "new-password-123",
    "roles": ["admission_counsellor"],
}


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def _token(client: AsyncClient, email: str) -> str:
    response = await _login(client, email)
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_only_system_admin_can_create_users(
    seeded_database: None, app_client: AsyncClient
) -> None:
    for email in (MANAGER, COUNSELLOR):
        token = await _token(app_client, email)
        response = await app_client.post("/api/users", json=NEW_USER, headers=_auth(token))
        assert response.status_code == 403, email

    admin = await _token(app_client, ADMIN)
    created = await app_client.post("/api/users", json=NEW_USER, headers=_auth(admin))

    assert created.status_code == 201
    body = created.json()
    assert body["email"] == NEW_USER["email"]
    assert body["is_active"] is True
    assert [role["slug"] for role in body["roles"]] == ["admission_counsellor"]

    login = await _login(app_client, NEW_USER["email"], NEW_USER["password"])
    assert login.status_code == 200

    me = await app_client.get("/api/auth/me", headers=_auth(login.json()["access_token"]))
    assert "leads.view_assigned" in me.json()["permissions"]


async def test_created_email_is_normalised(seeded_database: None, app_client: AsyncClient) -> None:
    admin = await _token(app_client, ADMIN)
    payload = {**NEW_USER, "email": "Mixed.Case@Enrollio.Dev"}

    created = await app_client.post("/api/users", json=payload, headers=_auth(admin))

    assert created.status_code == 201
    assert created.json()["email"] == "mixed.case@enrollio.dev"

    login = await _login(app_client, "MIXED.CASE@enrollio.dev", NEW_USER["password"])
    assert login.status_code == 200


async def test_duplicate_email_and_unknown_role_are_rejected(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)

    duplicate = await app_client.post(
        "/api/users", json={**NEW_USER, "email": ADMIN}, headers=_auth(admin)
    )
    unknown_role = await app_client.post(
        "/api/users", json={**NEW_USER, "roles": ["not_a_role"]}, headers=_auth(admin)
    )
    weak_password = await app_client.post(
        "/api/users", json={**NEW_USER, "password": "short"}, headers=_auth(admin)
    )

    assert duplicate.status_code == 409
    assert unknown_role.status_code == 400
    assert weak_password.status_code == 422


async def test_admin_can_list_and_update_a_user(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    created = await app_client.post("/api/users", json=NEW_USER, headers=_auth(admin))
    user_id = created.json()["id"]

    listed = await app_client.get("/api/users", headers=_auth(admin))
    assert listed.status_code == 200
    assert NEW_USER["email"] in {user["email"] for user in listed.json()}

    updated = await app_client.patch(
        f"/api/users/{user_id}",
        json={
            "full_name": "Promoted Counsellor",
            "roles": ["admission_manager"],
            "password": "another-password-123",
        },
        headers=_auth(admin),
    )

    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Promoted Counsellor"
    assert [role["slug"] for role in updated.json()["roles"]] == ["admission_manager"]

    login = await _login(app_client, NEW_USER["email"], "another-password-123")
    assert login.status_code == 200
    me = await app_client.get("/api/auth/me", headers=_auth(login.json()["access_token"]))
    assert "leads.view_all" in me.json()["permissions"]


async def test_deactivation_blocks_login_and_existing_tokens(
    seeded_database: None, app_client: AsyncClient
) -> None:
    admin = await _token(app_client, ADMIN)
    created = await app_client.post("/api/users", json=NEW_USER, headers=_auth(admin))
    user_id = created.json()["id"]

    login = await _login(app_client, NEW_USER["email"], NEW_USER["password"])
    user_access = login.json()["access_token"]
    refresh_cookie = app_client.cookies.get("refresh_token")
    assert refresh_cookie is not None

    deactivated = await app_client.post(f"/api/users/{user_id}/deactivate", headers=_auth(admin))
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    blocked_login = await _login(app_client, NEW_USER["email"], NEW_USER["password"])
    assert blocked_login.status_code == 401

    blocked_token = await app_client.get("/api/auth/me", headers=_auth(user_access))
    assert blocked_token.status_code == 401

    app_client.cookies.clear()
    app_client.cookies.set("refresh_token", refresh_cookie, path="/api/auth")
    blocked_refresh = await app_client.post("/api/auth/refresh")
    assert blocked_refresh.status_code == 401


async def test_user_admin_requires_authentication(app_client: AsyncClient) -> None:
    listed = await app_client.get("/api/users")
    created = await app_client.post("/api/users", json=NEW_USER)

    assert listed.status_code == 401
    assert created.status_code == 401


async def test_unknown_user_returns_404(seeded_database: None, app_client: AsyncClient) -> None:
    admin = await _token(app_client, ADMIN)
    missing_id = "00000000-0000-0000-0000-000000000000"

    patched = await app_client.patch(
        f"/api/users/{missing_id}", json={"full_name": "Nobody"}, headers=_auth(admin)
    )
    deactivated = await app_client.post(f"/api/users/{missing_id}/deactivate", headers=_auth(admin))

    assert patched.status_code == 404
    assert deactivated.status_code == 404
