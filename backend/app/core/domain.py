"""Domain enums shared by models, services, and the API.

These are stored as strings with a database check constraint (``native_enum``
is off), so adding a value later is a normal migration instead of a PostgreSQL
type change. Values are lower-case snake case and are the wire format.
"""

from __future__ import annotations

from enum import StrEnum


class LifecycleStatus(StrEnum):
    """FR-03 lifecycle states, in funnel order followed by terminal states."""

    NEW_ENQUIRY = "new_enquiry"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    COUNSELLING_SCHEDULED = "counselling_scheduled"
    COUNSELLING_COMPLETED = "counselling_completed"
    APPLICATION_STARTED = "application_started"
    APPLICATION_SUBMITTED = "application_submitted"
    ADMISSION_OFFERED = "admission_offered"
    CONVERTED = "converted"
    LOST = "lost"
    DISQUALIFIED = "disqualified"
    UNRESPONSIVE = "unresponsive"
    OPTED_OUT = "opted_out"


class ActorType(StrEnum):
    """Who caused a timeline event."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class ConsentChannel(StrEnum):
    """Channels a consent record applies to."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    PHONE = "phone"


class ConsentCategory(StrEnum):
    """FR-04 message categories."""

    TRANSACTIONAL = "transactional"
    PROMOTIONAL = "promotional"


class EmailDirection(StrEnum):
    """Whether an email left the system or arrived from a provider."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageChannel(StrEnum):
    """Channels a conversation or message can use."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class MessageCategory(StrEnum):
    """Outbound message categories (FR-04 consent classes plus FR-08 intents)."""

    TRANSACTIONAL = "transactional"
    PROMOTIONAL = "promotional"
    SCHOLARSHIP = "scholarship"
    FEE = "fee"
    ADMISSION_OFFER = "admission_offer"
    DEADLINE_CHANGE = "deadline_change"


class SendStatus(StrEnum):
    """Outcome of one `messaging.send` call."""

    SENT = "sent"
    QUEUED = "queued"
    BLOCKED = "blocked"
    PENDING_APPROVAL = "pending_approval"


class TemplateStatus(StrEnum):
    """Review state of a message template."""

    DRAFT = "draft"
    APPROVED = "approved"


class MessageDirection(StrEnum):
    """Whether a message left the system or arrived from a provider."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageStatus(StrEnum):
    """Delivery state of one message."""

    QUEUED = "queued"
    SENT = "sent"
    RECEIVED = "received"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"


class MessageEventType(StrEnum):
    """Provider or system event that changes a message's state."""

    SENT = "sent"
    RECEIVED = "received"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"


class ConversationStatus(StrEnum):
    """Whether a conversation is still active."""

    OPEN = "open"
    CLOSED = "closed"


class ImportJobStatus(StrEnum):
    """Lifecycle of one uploaded file."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportRowStatus(StrEnum):
    """Outcome for one row in an import file."""

    CREATED = "created"
    MERGED = "merged"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class DuplicateMatchReason(StrEnum):
    """Why an import row was flagged for duplicate review."""

    NAME_ONLY = "name_only"
    CONFLICTING_CONTACT = "conflicting_contact"


class DuplicateCandidateStatus(StrEnum):
    """Review state of a possible duplicate."""

    PENDING = "pending"
    RESOLVED = "resolved"


class DuplicateResolution(StrEnum):
    """Manual decision for a possible duplicate."""

    MERGED = "merged"
    KEPT_SEPARATE = "kept_separate"
    REJECTED = "rejected"


class ApprovalStatus(StrEnum):
    """Review state of an approval item (FR-15)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


LIFECYCLE_TERMINAL_STATES: frozenset[LifecycleStatus] = frozenset(
    {
        LifecycleStatus.LOST,
        LifecycleStatus.DISQUALIFIED,
        LifecycleStatus.UNRESPONSIVE,
        LifecycleStatus.OPTED_OUT,
    }
)
