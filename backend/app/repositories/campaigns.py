"""Campaign and campaign-recipient row helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.domain import CampaignRecipientStatus, CampaignStatus, MessageChannel
from app.models.campaign import Campaign, CampaignRecipient


async def get_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
) -> Campaign | None:
    """Load a campaign with its template, segment, and creator."""
    return await session.scalar(
        select(Campaign)
        .options(
            selectinload(Campaign.template),
            selectinload(Campaign.segment),
            selectinload(Campaign.created_by_user),
        )
        .where(Campaign.id == campaign_id)
    )


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
    """Insert a draft campaign."""
    campaign = Campaign(
        name=name.strip(),
        channel=channel,
        template_id=template_id,
        segment_id=segment_id,
        status=CampaignStatus.DRAFT,
        scheduled_at=scheduled_at,
        created_by=created_by,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get_recipient(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> CampaignRecipient | None:
    """Return one recipient row of a campaign."""
    return await session.scalar(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.lead_id == lead_id,
        )
    )


async def create_recipients(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    lead_ids: list[uuid.UUID],
) -> int:
    """Insert pending recipient rows for a launch snapshot."""
    rows = [
        CampaignRecipient(
            campaign_id=campaign_id,
            lead_id=lead_id,
            status=CampaignRecipientStatus.PENDING,
        )
        for lead_id in lead_ids
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def list_recipients(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    status: CampaignRecipientStatus | None = None,
) -> list[CampaignRecipient]:
    """Recipients in launch order."""
    statement = (
        select(CampaignRecipient)
        .where(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.created_at, CampaignRecipient.id)
    )
    if status is not None:
        statement = statement.where(CampaignRecipient.status == status)
    result = await session.execute(statement)
    return list(result.scalars())


async def update_recipient(
    session: AsyncSession,
    recipient: CampaignRecipient,
    *,
    status: CampaignRecipientStatus,
    reason: str | None = None,
    provider_message_id: str | None = None,
) -> CampaignRecipient:
    """Record a per-recipient send outcome."""
    recipient.status = status
    recipient.reason = reason
    recipient.provider_message_id = provider_message_id
    await session.flush()
    return recipient


async def status_breakdown(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
) -> dict[str, int]:
    """Recipient counts by status value."""
    rows = await session.execute(
        select(CampaignRecipient.status, func.count())
        .where(CampaignRecipient.campaign_id == campaign_id)
        .group_by(CampaignRecipient.status)
    )
    return {row[0].value: int(row[1]) for row in rows.all()}
