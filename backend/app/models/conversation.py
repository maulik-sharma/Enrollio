"""Conversations group every message for one lead on one channel."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import ConversationStatus, MessageChannel
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.message import Message


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One thread between Enrollio and a lead on a single channel.

    ``(lead_id, channel)`` is unique so concurrent inbound and outbound paths
    cannot create two threads for the same conversation. ``last_message_at`` is
    denormalised for inbox ordering and is maintained by the messaging service.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "lead_id",
            "channel",
            name="uq_conversations_lead_channel",
        ),
        Index("ix_conversations_last_message_at", "last_message_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[MessageChannel] = mapped_column(
        enum_column(MessageChannel, "message_channel"),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        enum_column(ConversationStatus, "conversation_status"),
        nullable=False,
        server_default=text(f"'{ConversationStatus.OPEN.value}'"),
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lead: Mapped[Lead] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
