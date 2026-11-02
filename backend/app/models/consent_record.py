"""Consent records: the audit trail behind FR-04 decisions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import ConsentCategory, ConsentChannel
from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.student import Student


class ConsentRecord(UUIDPrimaryKeyMixin, Base):
    """One grant or revocation for a student, channel, and category.

    Rows are append-only: the current decision is the latest row for the triple.
    This keeps source, method, and timestamp for every change (AC4.4).
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        Index(
            "ix_consent_records_student_channel_category",
            "student_id",
            "channel",
            "category",
            "recorded_at",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[ConsentChannel] = mapped_column(
        enum_column(ConsentChannel, "consent_channel"),
        nullable=False,
    )
    category: Mapped[ConsentCategory] = mapped_column(
        enum_column(ConsentCategory, "consent_category"),
        nullable=False,
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    method: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    student: Mapped[Student] = relationship(back_populates="consent_records")
