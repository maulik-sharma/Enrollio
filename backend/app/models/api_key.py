"""Hashed API keys for partner lead ingestion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead_source import LeadSource


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A source-scoped key; only the SHA-256 hash is persisted."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("uq_api_keys_key_hash", "key_hash", unique=True),
        Index("ix_api_keys_key_prefix", "key_prefix"),
        Index("ix_api_keys_source_id", "source_id"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    source: Mapped[LeadSource] = relationship()
