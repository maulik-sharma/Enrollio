"""Resource-level authorisation rules shared by every service.

These helpers are pure: they take the user and the resource shape they need, so
lead services can share one rule without importing each other. The API layer
turns ``False`` into a 404 for scoped reads so the caller cannot tell an
existing-but-unassigned resource from a missing one.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.permissions import PermissionName, user_has_permission
from app.models.user import User


class AssignedLead(Protocol):
    """The part of a lead that decides who may read it."""

    assigned_counsellor_id: uuid.UUID | None


def can_access_lead(user: User, lead: AssignedLead) -> bool:
    """Return True when ``user`` may read ``lead``.

    Managers and other holders of ``leads.view_all`` see every lead.
    Counsellors see only leads assigned to them. A user with neither permission
    (for example a system admin) sees none.
    """
    if user_has_permission(user, PermissionName.LEADS_VIEW_ALL):
        return True
    if user_has_permission(user, PermissionName.LEADS_VIEW_ASSIGNED):
        return lead.assigned_counsellor_id == user.id
    return False
