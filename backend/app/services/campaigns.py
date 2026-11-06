"""Campaign lifecycle: create, preview, launch, batch-send, report (M3.5).

Campaign sends always go through the M3.3 messaging entry point
(``messaging.send``), which runs every guard (consent, cap, quiet hours,
approval) before touching a provider. ``launch_campaign`` snapshots the
segment into ``campaign_recipients``, refuses oversized launches without a
prior approval, and then either runs ``send_campaign_batch`` inline or queues
the Celery task (mirroring the import pipeline's processing mode).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import ImportProcessingMode, Settings
from app.core.domain import (
    ActorType,
    ApprovalStatus,
    CampaignRecipientStatus,
    CampaignStatus,
    MessageChannel,
    SendStatus,
)
from app.integrations.email.base import EmailError, EmailProvider
from app.integrations.whatsapp.base import WhatsAppNotImplemented
from app.models.campaign import Campaign, CampaignRecipient
from app.models.lead import Lead
from app.models.message import Message
from app.models.message_template import MessageTemplate
from app.repositories import approvals as approvals_repo
from app.repositories import campaigns as campaigns_repo
from app.repositories import leads as leads_repo
from app.services import messaging
from app.services import segments as segments_service
from app.services.messaging import MessageActor, MessageContent, SendResult
from app.services.templates import TemplateRenderError, render_template

logger = logging.getLogger(__name__)

CAMPAIGN_LAUNCH_APPROVAL_TYPE = "campaign_launch"
MISSING_FIELD_PREFIX = "missing_field"
PROVIDER_ERROR_PREFIX = "provider_error"


class CampaignError(Exception):
    """Base class for campaign domain failures."""


class CampaignNotFound(CampaignError):
    """No campaign has the requested id."""


class TemplateNotFound(CampaignError):
    """The referenced message template does not exist."""


class SegmentNotFound(CampaignError):
    """The referenced segment does not exist."""


class InvalidCampaign(CampaignError):
    """The request/launch combination is not valid (API maps to 422/409)."""


@dataclass(frozen=True)
class LaunchOutcome:
    """What one launch attempt produced."""

    status: CampaignStatus
    approval_status: ApprovalStatus | None
    recipients_created: int
    dispatch: str | None
    approval_threshold: int


@dataclass(frozen=True)
class CampaignReport:
    """Status counts (and reason breakdown) for one campaign."""

    total: int
    by_status: dict[str, int]
    reasons: dict[str, int]


def recipient_context(lead: Lead) -> dict[str, Any]:
    """Render context for one lead; fields that are absent stay absent.

    Missing keys make the renderer report them per recipient (AC5.2) instead
    of sending a placeholder-littered message.
    """
    context: dict[str, Any] = {"admission_cycle": lead.admission_cycle}
    student = lead.student
    if student is not None:
        context["first_name"] = student.first_name
        context["last_name"] = student.last_name
        context["email"] = student.email_normalised
    if lead.programme is not None:
        context["programme"] = lead.programme.name
    if lead.campus is not None:
        context["campus"] = lead.campus.name
    counsellor = lead.assigned_counsellor
    if counsellor is not None:
        context["counsellor_name"] = counsellor.full_name
    return {key: value for key, value in context.items() if value is not None}


def render_for_lead(
    template: MessageTemplate,
    lead: Lead,
    *,
    unsubscribe_url: str,
) -> tuple[str, str, str]:
    """Render the template for one lead, raising ``TemplateRenderError``.

    Returns ``(subject, text_body, html_body)``; the API layer maps the
    renderer error to a 422 listing the missing fields.
    """
    rendered = render_template(
        template,
        recipient_context(lead),
        unsubscribe_url=unsubscribe_url,
    )
    return rendered.subject, rendered.text_body, rendered.html_body


async def create_campaign(
    session: AsyncSession,
    *,
    name: str,
    channel: MessageChannel,
    template_id: uuid.UUID,
    segment_id: uuid.UUID,
    created_by: uuid.UUID | None,
    scheduled_at: datetime | None = None,
) -> Campaign:
    """Create a draft campaign after validating the referenced rows."""
    template = await session.get(MessageTemplate, template_id)
    if template is None:
        raise TemplateNotFound
    if channel is not MessageChannel.EMAIL:
        raise WhatsAppNotImplemented("WhatsApp sending is implemented in Phase 2")
    if template.channel is not channel:
        raise InvalidCampaign(
            f"template channel {template.channel.value} does not match "
            f"campaign channel {channel.value}"
        )
    if await segments_service.get_segment(session, segment_id) is None:
        raise SegmentNotFound

    return await campaigns_repo.create_campaign(
        session,
        name=name,
        channel=channel,
        template_id=template_id,
        segment_id=segment_id,
        created_by=created_by,
        scheduled_at=scheduled_at,
    )


async def launch_campaign(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    campaign_id: uuid.UUID,
    email_provider: EmailProvider | None = None,
) -> LaunchOutcome:
    """Snapshot the segment and dispatch (or park for approval) one launch.

    Raises ``CampaignNotFound`` / ``InvalidCampaign`` for state problems.
    Launches above ``CAMPAIGN_LAUNCH_APPROVAL_THRESHOLD`` without
    ``approval_status=approved`` create one pending ``approval_items`` row
    (type ``campaign_launch``) and send nothing; the decision endpoint lands
    with the M4.6 approvals queue.
    """
    async with session_factory() as session:
        campaign = await campaigns_repo.get_campaign(session, campaign_id)
        if campaign is None:
            raise CampaignNotFound
        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED):
            raise InvalidCampaign(f"campaign status {campaign.status.value} cannot be launched")
        if campaign.template.status.value != "approved":
            raise InvalidCampaign("campaign template is not approved")

        statement = segments_service.build_statement(campaign.segment.filter_definition)
        lead_ids = [lead.id for lead in await session.scalars(statement)]

        threshold = settings.CAMPAIGN_LAUNCH_APPROVAL_THRESHOLD
        pending_approval = (
            len(lead_ids) > threshold and campaign.approval_status is not ApprovalStatus.APPROVED
        )
        if pending_approval:
            if campaign.approval_status is not ApprovalStatus.PENDING:
                await approvals_repo.create(
                    session,
                    item_type=CAMPAIGN_LAUNCH_APPROVAL_TYPE,
                    lead_id=None,
                    payload={"campaign_id": str(campaign.id)},
                )
                campaign.approval_status = ApprovalStatus.PENDING
            await session.commit()
            logger.info(
                "campaign launch requires approval",
                extra={"campaign_id": str(campaign.id), "recipients": len(lead_ids)},
            )
            return LaunchOutcome(
                status=campaign.status,
                approval_status=ApprovalStatus.PENDING,
                recipients_created=0,
                dispatch=None,
                approval_threshold=threshold,
            )

        recipients_created = await campaigns_repo.create_recipients(
            session, campaign_id=campaign.id, lead_ids=lead_ids
        )
        campaign.status = CampaignStatus.SENDING
        await session.commit()

    if settings.CAMPAIGN_SEND_MODE is ImportProcessingMode.inline:
        await send_campaign_batch(session_factory, settings, campaign_id, provider=email_provider)
        dispatch = "inline"
    else:
        from app.workers.campaigns import send_campaign_batch_task

        send_campaign_batch_task.delay(str(campaign_id))
        dispatch = "queued"

    logger.info(
        "campaign launch dispatched",
        extra={
            "campaign_id": str(campaign_id),
            "recipients": recipients_created,
            "dispatch": dispatch,
        },
    )
    final_status, final_approval = await _campaign_state_after_dispatch(
        session_factory,
        campaign_id,
    )
    return LaunchOutcome(
        status=final_status,
        approval_status=final_approval,
        recipients_created=recipients_created,
        dispatch=dispatch,
        approval_threshold=threshold,
    )


async def _campaign_state_after_dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    campaign_id: uuid.UUID,
) -> tuple[CampaignStatus, ApprovalStatus | None]:
    async with session_factory() as session:
        campaign = await campaigns_repo.get_campaign(session, campaign_id)
        if campaign is None:
            return CampaignStatus.SENDING, None
        return campaign.status, campaign.approval_status


async def send_campaign_batch(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    campaign_id: uuid.UUID,
    *,
    provider: EmailProvider | None = None,
) -> None:
    """Send every pending recipient of a campaign through ``messaging.send``.

    Each recipient gets its own transaction: a render failure or provider
    error for one student must not roll back the outcome of the others. Only
    rows still ``pending`` are processed, so re-invocations after a crash
    resume instead of re-sending.
    """
    if provider is None:
        from app.integrations.email.factory import build_email_provider

        provider = build_email_provider(settings, session_factory)

    pending_lead_ids = await _pending_lead_ids(session_factory, campaign_id)
    for lead_id in pending_lead_ids:
        result = await _send_one(
            session_factory,
            settings,
            provider,
            campaign_id,
            lead_id,
        )
        logger.info(
            "campaign recipient processed",
            extra={
                "campaign_id": str(campaign_id),
                "status": result.status.value,
                "reason": result.reason,
            },
        )

    await finalise_campaign_status(session_factory, campaign_id)


async def _send_one(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    provider: EmailProvider,
    campaign_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> SendResult:
    """Render, send, and persist one recipient's outcome in one transaction."""
    async with session_factory() as session:
        lead = await leads_repo.get(session, lead_id)
        recipient = await campaigns_repo.get_recipient(
            session, campaign_id=campaign_id, lead_id=lead_id
        )
        if recipient is None:
            raise CampaignError("campaign recipient row disappeared")
        if lead is None:
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.FAILED,
                reason="missing_lead",
            )
            await session.commit()
            return SendResult(status=SendStatus.BLOCKED, reason="missing_lead")

        campaign = await campaigns_repo.get_campaign(session, campaign_id)
        if campaign is None:
            raise CampaignNotFound
        template = campaign.template

        try:
            subject, text_body, html_body = render_for_lead(
                template,
                lead,
                unsubscribe_url=settings.UNSUBSCRIBE_URL,
            )
        except TemplateRenderError as exc:
            reason = MISSING_FIELD_PREFIX
            if exc.missing:
                reason = f"{MISSING_FIELD_PREFIX}: {', '.join(sorted(exc.missing))}"
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.FAILED,
                reason=reason,
            )
            await session.commit()
            logger.info(
                "campaign render failed",
                extra={"campaign_id": str(campaign_id), "reason": reason},
            )
            return SendResult(status=SendStatus.BLOCKED, reason=reason)

        message_content = MessageContent(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        try:
            result = await messaging.send(
                session,
                settings,
                provider,
                lead=lead,
                channel=template.channel,
                category=template.category,
                content=message_content,
                actor=MessageActor(actor_type=ActorType.USER, actor_id=campaign.created_by),
            )
        except EmailError as exc:
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.FAILED,
                reason=f"{PROVIDER_ERROR_PREFIX}: {exc}",
            )
            await session.commit()
            return SendResult(status=SendStatus.BLOCKED, reason=str(exc))

        if result.status is SendStatus.SENT:
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.SENT,
                provider_message_id=await _provider_message_id(session, result.message_id),
            )
        elif result.status is SendStatus.QUEUED:
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.QUEUED,
                reason=result.reason,
            )
        else:
            await campaigns_repo.update_recipient(
                session,
                recipient,
                status=CampaignRecipientStatus.BLOCKED,
                reason=result.reason,
            )
        await session.commit()
        return result


async def _provider_message_id(
    session: AsyncSession,
    message_id: uuid.UUID | None,
) -> str | None:
    if message_id is None:
        return None
    message = await session.get(Message, message_id)
    return message.provider_message_id if message is not None else None


async def _pending_lead_ids(
    session_factory: async_sessionmaker[AsyncSession],
    campaign_id: uuid.UUID,
) -> list[uuid.UUID]:
    async with session_factory() as session:
        recipients = await campaigns_repo.list_recipients(
            session,
            campaign_id=campaign_id,
            status=CampaignRecipientStatus.PENDING,
        )
        return [recipient.lead_id for recipient in recipients]


async def finalise_campaign_status(
    session_factory: async_sessionmaker[AsyncSession],
    campaign_id: uuid.UUID,
) -> None:
    """Move a sending campaign to completed when no pending rows remain."""
    async with session_factory() as session:
        campaign = await campaigns_repo.get_campaign(session, campaign_id)
        if campaign is None or campaign.status is not CampaignStatus.SENDING:
            return
        remaining = await session.scalar(
            select(CampaignRecipient.id)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == CampaignRecipientStatus.PENDING,
            )
            .limit(1)
        )
        if remaining is None:
            campaign.status = CampaignStatus.COMPLETED
        await session.commit()


async def campaign_report(session: AsyncSession, campaign_id: uuid.UUID) -> CampaignReport:
    """Counts by recipient status plus a reason breakdown."""
    campaign = await campaigns_repo.get_campaign(session, campaign_id)
    if campaign is None:
        raise CampaignNotFound
    by_status = await campaigns_repo.status_breakdown(session, campaign_id=campaign_id)
    reasons: dict[str, int] = {}
    for recipient in await campaigns_repo.list_recipients(session, campaign_id=campaign_id):
        if recipient.reason:
            reasons[recipient.reason] = reasons.get(recipient.reason, 0) + 1
    return CampaignReport(
        total=sum(by_status.values()),
        by_status=by_status,
        reasons=reasons,
    )


__all__ = [
    "CAMPAIGN_LAUNCH_APPROVAL_TYPE",
    "MISSING_FIELD_PREFIX",
    "PROVIDER_ERROR_PREFIX",
    "CampaignError",
    "CampaignNotFound",
    "CampaignReport",
    "InvalidCampaign",
    "LaunchOutcome",
    "SegmentNotFound",
    "TemplateNotFound",
    "campaign_report",
    "create_campaign",
    "finalise_campaign_status",
    "launch_campaign",
    "recipient_context",
    "render_for_lead",
    "send_campaign_batch",
]
