"""SQLAlchemy models. Importing this package registers every table on Base."""

from __future__ import annotations

from app.models.api_key import ApiKey
from app.models.approval_item import ApprovalItem
from app.models.base import Base
from app.models.campaign import Campaign, CampaignRecipient
from app.models.campus import Campus
from app.models.consent_record import ConsentRecord
from app.models.conversation import Conversation
from app.models.duplicate_candidate import DuplicateCandidate
from app.models.import_job import ImportJob, ImportRowResult, MappingTemplate
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.message import Message
from app.models.message_event import MessageEvent
from app.models.message_template import MessageTemplate
from app.models.mock_email_message import MockEmailMessage
from app.models.permission import Permission
from app.models.programme import Programme
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.segment import Segment
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
from app.models.user import User

__all__ = [
    "ApiKey",
    "ApprovalItem",
    "Base",
    "Campaign",
    "CampaignRecipient",
    "MessageTemplate",
    "Segment",
    "Campus",
    "ConsentRecord",
    "Conversation",
    "DuplicateCandidate",
    "ImportJob",
    "ImportRowResult",
    "Lead",
    "LeadSource",
    "MappingTemplate",
    "Message",
    "MessageEvent",
    "MockEmailMessage",
    "Permission",
    "Programme",
    "RefreshToken",
    "Role",
    "Student",
    "TimelineEvent",
    "User",
]
