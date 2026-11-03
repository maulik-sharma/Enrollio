"""SQLAlchemy models. Importing this package registers every table on Base."""

from __future__ import annotations

from app.models.api_key import ApiKey
from app.models.base import Base
from app.models.campus import Campus
from app.models.consent_record import ConsentRecord
from app.models.duplicate_candidate import DuplicateCandidate
from app.models.import_job import ImportJob, ImportRowResult, MappingTemplate
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.mock_email_message import MockEmailMessage
from app.models.permission import Permission
from app.models.programme import Programme
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
from app.models.user import User

__all__ = [
    "ApiKey",
    "Base",
    "Campus",
    "ConsentRecord",
    "DuplicateCandidate",
    "ImportJob",
    "ImportRowResult",
    "Lead",
    "LeadSource",
    "MappingTemplate",
    "MockEmailMessage",
    "Permission",
    "Programme",
    "RefreshToken",
    "Role",
    "Student",
    "TimelineEvent",
    "User",
]
