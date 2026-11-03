"""Database-backed captures for the mock email provider (M3.1).

The real message/conversation tables arrive in M3.2. Until then, the mock
provider stores what it would have handed to a vendor so downstream tests can
assert sends, inbound replies, and delivery events without making network calls.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.domain import EmailDirection
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column


class MockEmailMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One outbound send or inbound reply captured by the mock provider."""

    __tablename__ = "mock_email_messages"
    __table_args__ = (
        UniqueConstraint(
            "provider_message_id",
            name="uq_mock_email_messages_provider_message_id",
        ),
        Index("ix_mock_email_messages_direction", "direction"),
        Index("ix_mock_email_messages_in_reply_to", "in_reply_to"),
    )

    direction: Mapped[EmailDirection] = mapped_column(
        enum_column(EmailDirection, "email_direction"),
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'sent'"),
    )
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
