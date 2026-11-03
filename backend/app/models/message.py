"""Messages: one outbound send or inbound reply inside a conversation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import MessageChannel, MessageDirection, MessageStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_event import MessageEvent


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single message, normalised across providers.

    ``provider_message_id`` is unique within a channel, not globally: providers
    own their id namespace, and a missing id (a draft or a failed send) is NULL.
    ``created_by_agent_action_id`` is deliberately not a foreign key; agent runs
    do not have a table until a later milestone.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "provider_message_id",
            name="uq_messages_channel_provider_message_id",
        ),
        Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),
        Index("ix_messages_intent", "intent"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        enum_column(MessageDirection, "message_direction"),
        nullable=False,
    )
    channel: Mapped[MessageChannel] = mapped_column(
        enum_column(MessageChannel, "message_channel"),
        nullable=False,
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageStatus] = mapped_column(
        enum_column(MessageStatus, "message_status"),
        nullable=False,
        server_default=text(f"'{MessageStatus.QUEUED.value}'"),
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_agent_action_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    events: Mapped[list[MessageEvent]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )
