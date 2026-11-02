"""The ``require_permission`` dependency denies with 403, never leaks.

FastAPI calls the dependency with the current user. Calling it directly keeps
this a unit test while still exercising the real function FastAPI would run.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException

from app.api.deps import require_permission
from app.core.permissions import PermissionName
from app.models.user import User


def _user(*permissions: PermissionName) -> User:
    role = SimpleNamespace(permissions=[SimpleNamespace(name=p.value) for p in permissions])
    return cast(User, SimpleNamespace(id=uuid.uuid4(), roles=[role]))


async def test_dependency_returns_the_user_when_permitted() -> None:
    dependency = require_permission(PermissionName.LEADS_ASSIGN)
    user = _user(PermissionName.LEADS_VIEW_ALL, PermissionName.LEADS_ASSIGN)

    assert await dependency(user) is user


async def test_dependency_rejects_a_user_without_the_permission() -> None:
    dependency = require_permission(PermissionName.LEADS_ASSIGN)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(PermissionName.LEADS_VIEW_ASSIGNED))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient permissions"


async def test_dependency_accepts_a_plain_string_permission() -> None:
    dependency = require_permission("users.manage")

    assert await dependency(_user(PermissionName.USERS_MANAGE))


async def test_dependency_denies_a_user_with_no_roles() -> None:
    dependency = require_permission(PermissionName.USERS_MANAGE)
    user = cast(User, SimpleNamespace(id=uuid.uuid4(), roles=[]))

    with pytest.raises(HTTPException) as exc_info:
        await dependency(user)

    assert exc_info.value.status_code == 403
