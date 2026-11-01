"""Permission names, role slugs, and the role-permission matrix.

This module is pure data: it imports no models, so services, seed code, and
tests can share it without circular imports. The migration and seed routines
mirror this catalog into the database; it is the single source of truth for
RBAC defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PermissionName(StrEnum):
    """Every permission named in PRD section 4."""

    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    KNOWLEDGE_MANAGE = "knowledge.manage"
    INTEGRATIONS_MANAGE = "integrations.manage"
    AUDIT_VIEW = "audit.view"

    LEADS_VIEW_ALL = "leads.view_all"
    LEADS_ASSIGN = "leads.assign"
    CAMPAIGNS_MANAGE = "campaigns.manage"
    SCORING_CONFIGURE = "scoring.configure"
    FOLLOWUP_POLICY_MANAGE = "followup_policy.manage"
    DASHBOARD_MANAGER = "dashboard.manager"

    LEADS_VIEW_ASSIGNED = "leads.view_assigned"
    APPOINTMENTS_MANAGE_OWN = "appointments.manage_own"
    RECORDINGS_UPLOAD_OWN = "recordings.upload_own"
    MOM_REVIEW_OWN = "mom.review_own"
    ASSESSMENT_CREATE_OWN = "assessment.create_own"
    MESSAGES_SEND_OWN = "messages.send_own"


class RoleSlug(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    ADMISSION_MANAGER = "admission_manager"
    ADMISSION_COUNSELLOR = "admission_counsellor"


@dataclass(frozen=True)
class RoleDefinition:
    slug: RoleSlug
    name: str
    description: str
    permissions: frozenset[PermissionName]


PERMISSION_DESCRIPTIONS: dict[PermissionName, str] = {
    PermissionName.USERS_MANAGE: "Create, update, and deactivate users",
    PermissionName.ROLES_MANAGE: "Change which permissions a role grants",
    PermissionName.KNOWLEDGE_MANAGE: "Manage the admission knowledge base",
    PermissionName.INTEGRATIONS_MANAGE: "Configure external integrations",
    PermissionName.AUDIT_VIEW: "View the audit log",
    PermissionName.LEADS_VIEW_ALL: "View every lead in the funnel",
    PermissionName.LEADS_ASSIGN: "Assign or reassign leads to counsellors",
    PermissionName.CAMPAIGNS_MANAGE: "Create and run communication campaigns",
    PermissionName.SCORING_CONFIGURE: "Configure lead scoring rules",
    PermissionName.FOLLOWUP_POLICY_MANAGE: "Configure follow-up policies and SLAs",
    PermissionName.DASHBOARD_MANAGER: "View manager dashboards",
    PermissionName.LEADS_VIEW_ASSIGNED: "View leads assigned to the current user",
    PermissionName.APPOINTMENTS_MANAGE_OWN: "Manage the current user's appointments",
    PermissionName.RECORDINGS_UPLOAD_OWN: "Upload recordings for the current user's sessions",
    PermissionName.MOM_REVIEW_OWN: "Review minutes of meeting for own sessions",
    PermissionName.ASSESSMENT_CREATE_OWN: "Create assessments for own leads",
    PermissionName.MESSAGES_SEND_OWN: "Send messages to own leads",
}

ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        slug=RoleSlug.SYSTEM_ADMIN,
        name="System Admin",
        description="Platform setup, users, roles, integrations, and knowledge base",
        permissions=frozenset(
            {
                PermissionName.USERS_MANAGE,
                PermissionName.ROLES_MANAGE,
                PermissionName.KNOWLEDGE_MANAGE,
                PermissionName.INTEGRATIONS_MANAGE,
                PermissionName.AUDIT_VIEW,
            }
        ),
    ),
    RoleDefinition(
        slug=RoleSlug.ADMISSION_MANAGER,
        name="Admission Manager",
        description="Owns the funnel, campaigns, assignment, and admissions policy",
        permissions=frozenset(
            {
                PermissionName.LEADS_VIEW_ALL,
                PermissionName.LEADS_ASSIGN,
                PermissionName.CAMPAIGNS_MANAGE,
                PermissionName.SCORING_CONFIGURE,
                PermissionName.FOLLOWUP_POLICY_MANAGE,
                PermissionName.DASHBOARD_MANAGER,
            }
        ),
    ),
    RoleDefinition(
        slug=RoleSlug.ADMISSION_COUNSELLOR,
        name="Admission Counsellor",
        description="Works assigned leads, runs sessions, and reviews MOMs",
        permissions=frozenset(
            {
                PermissionName.LEADS_VIEW_ASSIGNED,
                PermissionName.APPOINTMENTS_MANAGE_OWN,
                PermissionName.RECORDINGS_UPLOAD_OWN,
                PermissionName.MOM_REVIEW_OWN,
                PermissionName.ASSESSMENT_CREATE_OWN,
                PermissionName.MESSAGES_SEND_OWN,
            }
        ),
    ),
)

ROLE_PERMISSIONS: dict[RoleSlug, frozenset[PermissionName]] = {
    definition.slug: definition.permissions for definition in ROLE_DEFINITIONS
}


def all_permission_names() -> tuple[PermissionName, ...]:
    """Return the catalog in a stable order."""
    return tuple(PermissionName)
