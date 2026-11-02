"""Permission enforcement through the real app and real tokens."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient, Response

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from tests.conftest import requires_postgres

pytestmark = pytest.mark.integration

PASSWORD = "demo-password-123"
ADMIN = "admin@enrollio.dev"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"


async def _login(client: AsyncClient, email: str) -> Response:
    return await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})


async def _access_token(client: AsyncClient, email: str) -> str:
    response = await _login(client, email)
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _add_protected_routes(app: FastAPI) -> None:
    """Register endpoints mirroring how M2 will declare permissions."""

    @app.get(
        "/_test/admin-only",
        dependencies=[Depends(require_permission(PermissionName.USERS_MANAGE))],
    )
    async def admin_only() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/_test/all-leads",
        dependencies=[Depends(require_permission(PermissionName.LEADS_VIEW_ALL))],
    )
    async def all_leads() -> dict[str, str]:
        return {"scope": "all"}


@requires_postgres
async def test_missing_token_is_unauthenticated(
    seeded_database: None, app: FastAPI, app_client: AsyncClient
) -> None:
    _add_protected_routes(app)

    response = await app_client.get("/_test/admin-only")

    assert response.status_code == 401


@requires_postgres
async def test_system_admin_passes_the_permission_gate(
    seeded_database: None, app: FastAPI, app_client: AsyncClient
) -> None:
    _add_protected_routes(app)
    token = await _access_token(app_client, ADMIN)

    response = await app_client.get(
        "/_test/admin-only", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@requires_postgres
@pytest.mark.parametrize("email", [MANAGER, COUNSELLOR])
async def test_other_roles_are_forbidden(
    seeded_database: None,
    app: FastAPI,
    app_client: AsyncClient,
    email: str,
) -> None:
    _add_protected_routes(app)
    token = await _access_token(app_client, email)

    response = await app_client.get(
        "/_test/admin-only", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@requires_postgres
async def test_manager_can_reach_the_all_leads_endpoint(
    seeded_database: None, app: FastAPI, app_client: AsyncClient
) -> None:
    _add_protected_routes(app)
    manager = await _access_token(app_client, MANAGER)
    counsellor = await _access_token(app_client, COUNSELLOR)

    allowed = await app_client.get(
        "/_test/all-leads",
        headers={"Authorization": f"Bearer {manager}"},
    )
    denied = await app_client.get(
        "/_test/all-leads",
        headers={"Authorization": f"Bearer {counsellor}"},
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403
