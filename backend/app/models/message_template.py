"""Reusable message templates with `{{placeholder}}` subjects and bodies."""

from __future__ import annotations

from sqlalchemy import Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.domain import MessageCategory, MessageChannel, TemplateStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column


class MessageTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One versioned template for a channel/category pair.

    Subject and body may reference `{{first_name}}`, `{{programme}}`, and the
    other render placeholders; unknown or missing values are a render error
    rather than a partial send. `(name, version)` is unique so a revised
    template is a new row, and only `approved` templates are sendable;
    campaigns (M3.5) pick approved rows.
    """

    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_message_templates_name_version"),
        Index("ix_message_templates_channel_category_status", "channel", "category", "status"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(
        enum_column(MessageChannel, "message_channel"),
        nullable=False,
    )
    category: Mapped[MessageCategory] = mapped_column(
        enum_column(MessageCategory, "message_category"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    status: Mapped[TemplateStatus] = mapped_column(
        enum_column(TemplateStatus, "template_status"),
        nullable=False,
        server_default=text(f"'{TemplateStatus.DRAFT.value}'"),
    )
