"""Authentication endpoints: login, refresh rotation, logout, lockout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User
from tests.conftest import requires_postgres

pytestmark = pytest.mark.integration

ADMIN = "admin@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"
PASSWORD = "demo-password-123"


async def _login(client: AsyncClient, email: str = ADMIN, password: str = PASSWORD) -> Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def _use_refresh_cookie(client: AsyncClient, token: str) -> None:
    """Replace the client's refresh cookie with ``token``.

    Clearing first matters: otherwise the jar keeps the cookie from the last
    response and the request would silently reuse the newest token.
    """
    client.cookies.clear()
    client.cookies.set("refresh_token", token, path="/api/auth")


@requires_postgres
async def test_login_returns_access_token_and_secure_refresh_cookie(
    seeded_database: None, app_client: AsyncClient
) -> None:
    response = await _login(app_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["access_token"]

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Path=/api/auth" in set_cookie

    me = await app_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == ADMIN
    assert profile["is_active"] is True
    assert "users.manage" in profile["permissions"]
    assert [role["slug"] for role in profile["roles"]] == ["system_admin"]


@requires_postgres
async def test_admin_can_log_in_and_me_reflects_the_role(
    seeded_database: None, app_client: AsyncClient
) -> None:
    response = await _login(app_client, COUNSELLOR)
    assert response.status_code == 200

    me = await app_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    profile = me.json()

    assert "leads.view_assigned" in profile["permissions"]
    assert "leads.view_all" not in profile["permissions"]
    assert "users.manage" not in profile["permissions"]


@requires_postgres
async def test_wrong_password_and_unknown_email_are_indistinguishable(
    seeded_database: None, app_client: AsyncClient
) -> None:
    wrong_password = await _login(app_client, ADMIN, "definitely-wrong")
    unknown_email = await _login(app_client, "nobody@enrollio.dev", "definitely-wrong")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


@requires_postgres
async def test_refresh_rotation_and_reuse_revokes_the_family(
    seeded_database: None, app_client: AsyncClient
) -> None:
    login = await _login(app_client)
    original_refresh = app_client.cookies.get("refresh_token")
    assert original_refresh is not None
    original_access = login.json()["access_token"]

    rotated = await app_client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    rotated_access = rotated.json()["access_token"]
    assert rotated_access != original_access
    rotated_refresh = app_client.cookies.get("refresh_token")
    assert rotated_refresh not in {None, original_refresh}

    # Presenting the rotated token again is treated as theft: it fails and the
    # whole family is revoked, including the newest token.
    _use_refresh_cookie(app_client, original_refresh)
    reuse = await app_client.post("/api/auth/refresh")
    assert reuse.status_code == 401

    _use_refresh_cookie(app_client, rotated_refresh)
    after_reuse = await app_client.post("/api/auth/refresh")
    assert after_reuse.status_code == 401


@requires_postgres
async def test_unknown_refresh_token_is_rejected(
    seeded_database: None, app_client: AsyncClient
) -> None:
    _use_refresh_cookie(app_client, "not-a-real-token")
    response = await app_client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


@requires_postgres
async def test_logout_revokes_the_refresh_token(
    seeded_database: None, app_client: AsyncClient
) -> None:
    await _login(app_client)
    refresh_token = app_client.cookies.get("refresh_token")
    assert refresh_token is not None

    logout = await app_client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}

    _use_refresh_cookie(app_client, refresh_token)
    refresh = await app_client.post("/api/auth/refresh")
    assert refresh.status_code == 401


@requires_postgres
async def test_account_locks_after_five_failures(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    for _ in range(5):
        response = await _login(app_client, ADMIN, "wrong-password")
        assert response.status_code == 401

    locked = await _login(app_client, ADMIN, PASSWORD)
    assert locked.status_code == 401

    async with db_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == ADMIN))
        assert user is not None
        assert user.locked_until is not None
        assert user.failed_login_count == 5

        user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    recovered = await _login(app_client, ADMIN, PASSWORD)
    assert recovered.status_code == 200


@requires_postgres
async def test_inactive_user_cannot_log_in_and_existing_token_is_rejected(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    login = await _login(app_client)
    access_token = login.json()["access_token"]

    async with db_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == ADMIN))
        assert user is not None
        user.is_active = False
        await session.commit()

    rejected = await app_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert rejected.status_code == 401

    login_again = await _login(app_client)
    assert login_again.status_code == 401


@requires_postgres
async def test_me_requires_a_valid_bearer_token(
    seeded_database: None, app_client: AsyncClient
) -> None:
    missing = await app_client.get("/api/auth/me")
    malformed = await app_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


@requires_postgres
async def test_refresh_without_cookie_is_rejected(
    seeded_database: None, app_client: AsyncClient
) -> None:
    response = await app_client.post("/api/auth/refresh")

    assert response.status_code == 401


@requires_postgres
async def test_cors_preflight_allows_the_frontend_origin(
    seeded_database: None, app_client: AsyncClient
) -> None:
    response = await app_client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
