"""Lead access scoping (M1.3 security gate)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from app.core.permissions import PermissionName
from app.models.user import User
from app.services.access import can_access_lead


def _user(*permissions: PermissionName) -> User:
    """A lightweight user whose roles grant exactly ``permissions``."""
    role = SimpleNamespace(permissions=[SimpleNamespace(name=p.value) for p in permissions])
    return cast(User, SimpleNamespace(id=uuid.uuid4(), roles=[role]))


@dataclass
class _Lead:
    assigned_counsellor_id: uuid.UUID | None = None


def test_manager_can_access_any_lead() -> None:
    manager = _user(PermissionName.LEADS_VIEW_ALL, PermissionName.LEADS_ASSIGN)
    somebody_else = uuid.uuid4()

    assert can_access_lead(manager, _Lead(assigned_counsellor_id=somebody_else))
    assert can_access_lead(manager, _Lead(assigned_counsellor_id=None))


def test_counsellor_can_access_only_own_leads() -> None:
    counsellor = _user(
        PermissionName.LEADS_VIEW_ASSIGNED,
        PermissionName.MESSAGES_SEND_OWN,
    )
    own = _Lead(assigned_counsellor_id=counsellor.id)
    other = _Lead(assigned_counsellor_id=uuid.uuid4())

    assert can_access_lead(counsellor, own)
    assert not can_access_lead(counsellor, other)
    assert not can_access_lead(counsellor, _Lead(assigned_counsellor_id=None))


def test_user_without_lead_permissions_cannot_access_any_lead() -> None:
    admin = _user(PermissionName.USERS_MANAGE, PermissionName.ROLES_MANAGE)
    counsellor = _user(PermissionName.LEADS_VIEW_ASSIGNED)

    assert not can_access_lead(admin, _Lead(assigned_counsellor_id=None))
    assert not can_access_lead(admin, _Lead(assigned_counsellor_id=counsellor.id))
