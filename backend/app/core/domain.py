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


LIFECYCLE_TERMINAL_STATES: frozenset[LifecycleStatus] = frozenset(
    {
        LifecycleStatus.LOST,
        LifecycleStatus.DISQUALIFIED,
        LifecycleStatus.UNRESPONSIVE,
        LifecycleStatus.OPTED_OUT,
    }
)
