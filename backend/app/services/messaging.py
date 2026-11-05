"""The single entry point for sending messages (M3.3).

Every outbound message — API, agent, or campaign — must go through
:meth:`send` so the consent, frequency-cap, quiet-hours, and approval guards
always run and every step is logged. No other module may call a provider
adapter directly; a unit grep-test enforces that (``tests/unit/
test_messaging_is_entry_point.py``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.domain import (
    ActorType,
    ConsentCategory,
    ConsentChannel,
    MessageCategory,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    SendStatus,
)
from app.integrations.email.base import EmailMessage, EmailProvider
from app.integrations.whatsapp.base import WhatsAppNotImplemented
from app.models.lead import Lead
from app.repositories import approvals as approvals_repo
from app.repositories import conversations as conversations_repo
from app.repositories import messages as messages_repo
from app.repositories import students as students_repo
from app.repositories import timeline as timeline_repo
from app.services import consent as consent_service

logger = logging.getLogger(__name__)

MESSAGE_SEND_APPROVAL_TYPE = "message_send"

SENSITIVE_CATEGORIES: frozenset[MessageCategory] = frozenset(
    {
        MessageCategory.SCHOLARSHIP,
        MessageCategory.FEE,
        MessageCategory.ADMISSION_OFFER,
        MessageCategory.DEADLINE_CHANGE,
    }
)

PROMOTIONAL_FREQ_CAP_KEY = "promotional_frequency_cap"
QUIET_HOURS_KEY = "quiet_hours"
CONSENT_KEY = "consent_not_granted"
MISSING_RECIPIENT_KEY = "missing_recipient_address"


class MessagingError(Exception):
    """Base class for messaging domain failures."""


class StudentNotFound(MessagingError):
    """The lead has no student record to resolve a recipient from."""


@dataclass(frozen=True)
class MessageContent:
    """What to say: subject plus text (and optional HTML) bodies."""

    subject: str
    text_body: str
    html_body: str | None = None
    #: Extra context for the timeline payload and provider metadata.
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageActor:
    """Who asked for the send."""

    actor_type: ActorType
    actor_id: uuid.UUID | None = None
    #: Set when an agent requested the send (stored on the message row).
    agent_action_id: uuid.UUID | None = None


@dataclass(frozen=True)
class SendResult:
    """Outcome of one :meth:`send` call.

    ``sent``: delivered to the provider; ``queued``: held for quiet hours;
    ``pending_approval``: waiting on a human; ``blocked``: a guard refused
    and ``reason`` explains which one.
    """

    status: SendStatus
    reason: str | None = None
    message_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    approval_item_id: uuid.UUID | None = None
    next_allowed_at: datetime | None = None


def is_quiet_hours(hour: int, *, start_hour: int, end_hour: int) -> bool:
    """Whether ``hour`` (0–23) falls inside the quiet window.

    Windows may wrap midnight (start 21, end 9) or sit inside one day
    (start 12, end 14); an empty window (start == end) never quiets.
    """
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def next_allowed_at(
    now: datetime,
    *,
    timezone_name: str,
    start_hour: int,
    end_hour: int,
) -> datetime:
    """When the quiet window next ends (equal to ``now`` outside quiet hours)."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise MessagingError(f"unknown quiet hours timezone {timezone_name!r}") from exc
    local = now.astimezone(zone)
    if not is_quiet_hours(local.hour, start_hour=start_hour, end_hour=end_hour):
        return local
    candidate = local.replace(hour=end_hour % 24, minute=0, second=0, microsecond=0, fold=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def consent_category_for(category: MessageCategory) -> ConsentCategory:
    """Map a message category to its consent class.

    Sensitive categories (scholarship, fee, admission offer, deadline change)
    ride the transactional consent class; everything promotional uses the
    promotional class, which requires an explicit grant.
    """
    if category is MessageCategory.PROMOTIONAL:
        return ConsentCategory.PROMOTIONAL
    return ConsentCategory.TRANSACTIONAL


def consent_channel_for(channel: MessageChannel) -> ConsentChannel:
    """Map a message channel to its consent channel."""
    return ConsentChannel(channel.value)


async def _resolve_email(session: AsyncSession, lead: Lead) -> str | None:
    student = await students_repo.get(session, lead.student_id)
    if student is None:
        raise StudentNotFound
    return student.email_normalised


async def send(
    session: AsyncSession,
    settings: Settings,
    provider: EmailProvider,
    *,
    lead: Lead,
    channel: MessageChannel,
    category: MessageCategory,
    content: MessageContent,
    actor: MessageActor,
    now: datetime | None = None,
) -> SendResult:
    """Send one message, or refuse/queue it, and record the outcome.

    Guard order (each step logs its decision, and every refusal stops here):

    1. Consent (M2.6): the latest consent record for the mapped channel and
       category must allow the send.
    2. Frequency cap: promotional messages count ``message_sent`` timeline
       events inside the rolling window.
    3. Quiet hours: non-urgent (promotional) sends inside the window are
       stored as ``queued`` message rows without touching the provider.
    4. Approval: sensitive categories need a human decision; the first
       request creates a pending approval item and repeats return it.
    """
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    student_id = lead.student_id

    logger.info(
        "messaging.send requested",
        extra={
            "lead_id": str(lead.id),
            "student_id": str(student_id),
            "channel": channel.value,
            "category": category.value,
            "actor_type": actor.actor_type.value,
        },
    )

    if channel is not MessageChannel.EMAIL:
        logger.warning(
            "messaging.send refused: unsupported channel",
            extra={"lead_id": str(lead.id), "channel": channel.value},
        )
        raise WhatsAppNotImplemented("WhatsApp sending is implemented in Phase 2")

    recipient = await _resolve_email(session, lead)
    if recipient is None:
        logger.info(
            "messaging.send blocked: missing recipient address",
            extra={"lead_id": str(lead.id), "channel": channel.value},
        )
        return SendResult(status=SendStatus.BLOCKED, reason=MISSING_RECIPIENT_KEY)

    consent_category = consent_category_for(category)
    allowed = await _consent_allows(
        session,
        student_id=student_id,
        channel=channel,
        category=consent_category,
    )
    if not allowed:
        logger.info(
            "messaging.send blocked: consent not granted",
            extra={
                "lead_id": str(lead.id),
                "channel": channel.value,
                "consent_category": consent_category.value,
            },
        )
        return SendResult(status=SendStatus.BLOCKED, reason=CONSENT_KEY)

    if category is MessageCategory.PROMOTIONAL:
        cap = settings.PROMOTIONAL_CAP_PER_WINDOW
        window = timedelta(days=settings.PROMOTIONAL_CAP_WINDOW_DAYS)
        counted = await timeline_repo.count_message_sent(
            session,
            student_id=student_id,
            category=category.value,
            since=moment - window,
        )
        if counted >= cap:
            logger.info(
                "messaging.send blocked: promotional frequency cap",
                extra={
                    "lead_id": str(lead.id),
                    "counted": counted,
                    "cap": cap,
                    "window_days": settings.PROMOTIONAL_CAP_WINDOW_DAYS,
                },
            )
            return SendResult(status=SendStatus.BLOCKED, reason=PROMOTIONAL_FREQ_CAP_KEY)

    in_quiet_hours = is_quiet_hours(
        _local_hour(moment, settings.QUIET_HOURS_TIMEZONE),
        start_hour=settings.QUIET_HOURS_START_HOUR,
        end_hour=settings.QUIET_HOURS_END_HOUR,
    )
    if in_quiet_hours and category is MessageCategory.PROMOTIONAL:
        resume = next_allowed_at(
            moment,
            timezone_name=settings.QUIET_HOURS_TIMEZONE,
            start_hour=settings.QUIET_HOURS_START_HOUR,
            end_hour=settings.QUIET_HOURS_END_HOUR,
        )
        conversation = await conversations_repo.get_or_create(
            session, lead_id=lead.id, channel=channel
        )
        message = await messages_repo.create(
            session,
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
            channel=channel,
            status=MessageStatus.QUEUED,
            content_text=content.text_body,
            content_html=content.html_body,
            intent=category.value,
            created_by_agent_action_id=actor.agent_action_id,
        )
        logger.info(
            "messaging.send queued for quiet hours",
            extra={"lead_id": str(lead.id), "message_id": str(message.id)},
        )
        return SendResult(
            status=SendStatus.QUEUED,
            reason=QUIET_HOURS_KEY,
            message_id=message.id,
            conversation_id=conversation.id,
            next_allowed_at=resume,
        )

    if category in SENSITIVE_CATEGORIES:
        pending = await approvals_repo.latest_pending(
            session,
            lead_id=lead.id,
            item_type=MESSAGE_SEND_APPROVAL_TYPE,
        )
        if pending is not None:
            logger.info(
                "messaging.send awaits an existing pending approval",
                extra={
                    "lead_id": str(lead.id),
                    "approval_item_id": str(pending.id),
                },
            )
            return SendResult(
                status=SendStatus.PENDING_APPROVAL,
                reason="approval_already_pending",
                approval_item_id=pending.id,
            )
        item = await approvals_repo.create(
            session,
            item_type=MESSAGE_SEND_APPROVAL_TYPE,
            lead_id=lead.id,
            payload={
                "channel": channel.value,
                "category": category.value,
                "subject": content.subject,
                **content.metadata,
            },
            draft_content=content.text_body,
        )
        logger.info(
            "messaging.send created a pending approval",
            extra={"lead_id": str(lead.id), "approval_item_id": str(item.id)},
        )
        return SendResult(
            status=SendStatus.PENDING_APPROVAL,
            approval_item_id=item.id,
        )

    email_message = EmailMessage(
        to_address=recipient,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
    )
    provider_message_id = await provider.send(email_message)

    conversation = await conversations_repo.get_or_create(session, lead_id=lead.id, channel=channel)
    message = await messages_repo.create(
        session,
        conversation_id=conversation.id,
        direction=MessageDirection.OUTBOUND,
        channel=channel,
        status=MessageStatus.SENT,
        content_text=content.text_body,
        content_html=content.html_body,
        provider_message_id=provider_message_id,
        intent=category.value,
        created_by_agent_action_id=actor.agent_action_id,
    )
    await conversations_repo.touch_last_message_at(session, conversation, at=moment)
    await timeline_repo.create_message_sent(
        session,
        student_id=student_id,
        lead_id=lead.id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        payload={
            "category": category.value,
            "channel": channel.value,
            "message_id": str(message.id),
            "subject": content.subject,
            **content.metadata,
        },
    )
    logger.info(
        "messaging.send sent",
        extra={
            "lead_id": str(lead.id),
            "message_id": str(message.id),
            "category": category.value,
            "channel": channel.value,
        },
    )
    return SendResult(
        status=SendStatus.SENT,
        message_id=message.id,
        conversation_id=conversation.id,
    )


async def _consent_allows(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    channel: MessageChannel,
    category: ConsentCategory,
) -> bool:
    """Latest consent decision via the consent service (M2.6 policy)."""
    allowed = await consent_service.can_send(
        session,
        student_id=student_id,
        channel=consent_channel_for(channel),
        category=category,
    )
    return bool(allowed)


def _local_hour(moment: datetime, timezone_name: str) -> int:
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise MessagingError(f"unknown quiet hours timezone {timezone_name!r}") from exc
    return moment.astimezone(zone).hour


__all__ = [
    "CONSENT_KEY",
    "MESSAGE_SEND_APPROVAL_TYPE",
    "MISSING_RECIPIENT_KEY",
    "PROMOTIONAL_FREQ_CAP_KEY",
    "QUIET_HOURS_KEY",
    "SENSITIVE_CATEGORIES",
    "MessageActor",
    "MessageContent",
    "MessagingError",
    "SendResult",
    "StudentNotFound",
    "consent_category_for",
    "consent_channel_for",
    "is_quiet_hours",
    "next_allowed_at",
    "send",
]
