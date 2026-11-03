"""Provider webhook events for messages, deduplicated by provider event id."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import MessageEventType
from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.message import Message


class MessageEvent(UUIDPrimaryKeyMixin, Base):
    """One processed provider event.

    ``provider_event_id`` is unique so a repeated webhook delivery is rejected
    by the database instead of applying a second status change. Events are
    append-only and therefore have no ``updated_at``.
    """

    __tablename__ = "message_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_event_id",
            name="uq_message_events_provider_event_id",
        ),
        Index("ix_message_events_message_occurred_at", "message_id", "occurred_at"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[MessageEventType] = mapped_column(
        enum_column(MessageEventType, "message_event_type"),
        nullable=False,
    )
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    message: Mapped[Message] = relationship(back_populates="events")
