"""Approval items: pending human decisions required before sensitive sends."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import ApprovalStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.lead import Lead


class ApprovalItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One item waiting for a decision (FR-15).

    ``type`` distinguishes message approvals from later agent-draft approvals;
    ``draft_content`` holds the proposed text and ``payload`` holds structured
    metadata. ``decided_by`` is not a foreign key so system-generated ids stay
    acceptable until the approval flow (M4.7) lands.
    """

    __tablename__ = "approval_items"
    __table_args__ = (
        Index("ix_approval_items_lead_status", "lead_id", "status"),
        Index("ix_approval_items_status_created_at", "status", "created_at"),
    )

    item_type: Mapped[str] = mapped_column("type", String(64), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        enum_column(ApprovalStatus, "approval_status"),
        nullable=False,
        server_default=text(f"'{ApprovalStatus.PENDING.value}'"),
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead: Mapped[Lead | None] = relationship(back_populates="approval_items")
