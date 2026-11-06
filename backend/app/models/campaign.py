"""Bulk campaigns and their per-recipient outcomes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import (
    ApprovalStatus,
    CampaignRecipientStatus,
    CampaignStatus,
    MessageChannel,
)
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.message_template import MessageTemplate
    from app.models.segment import Segment
    from app.models.user import User


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One bulk send from a segment through a template (FR-09).

    ``approval_status`` is NULL until a launch crosses the config-launch-size
    threshold; launching a large campaign stores a pending ``approval_items``
    row (type ``campaign_launch``) and refuses to send until the queue (M4.6)
    decides.
    """

    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_status", "status"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(
        enum_column(MessageChannel, "message_channel"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("message_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        enum_column(CampaignStatus, "campaign_status"),
        nullable=False,
        server_default=text(f"'{CampaignStatus.DRAFT.value}'"),
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_status: Mapped[ApprovalStatus | None] = mapped_column(
        enum_column(ApprovalStatus, "approval_status"),
        nullable=True,
    )

    template: Mapped[MessageTemplate] = relationship()
    segment: Mapped[Segment] = relationship()
    created_by_user: Mapped[User | None] = relationship()
    recipients: Mapped[list[CampaignRecipient]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class CampaignRecipient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One lead inside one campaign, recorded at launch.

    Rows are written when the campaign launches (a segment snapshot), so
    later segment edits never change who receives a running campaign. The
    ``(campaign_id, lead_id)`` pair is unique and status/reason describe the
    send outcome, including render failures (``missing_field``) and guard
    refusals copied from the messaging entry point.
    """

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_recipients_campaign_lead"),
        Index("ix_campaign_recipients_campaign_status", "campaign_id", "status"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[CampaignRecipientStatus] = mapped_column(
        enum_column(CampaignRecipientStatus, "campaign_recipient_status"),
        nullable=False,
        server_default=text(f"'{CampaignRecipientStatus.PENDING.value}'"),
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    campaign: Mapped[Campaign] = relationship(back_populates="recipients")
    lead: Mapped[Lead] = relationship()
