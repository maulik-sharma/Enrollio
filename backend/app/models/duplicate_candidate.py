"""Possible duplicate students flagged during import for manual review."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import (
    DuplicateCandidateStatus,
    DuplicateMatchReason,
    DuplicateResolution,
)
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.import_job import ImportJob
    from app.models.student import Student
    from app.models.user import User


class DuplicateCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student pair that may be the same person.

    ``student_id`` is the existing contact match (or the older contact for a
    conflicting email/phone pair). ``candidate_student_id`` is the newly created
    student for a name-only match. ``conflicting_student_id`` is the other
    existing student when the incoming email and phone point at different rows.
    """

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        Index("ix_duplicate_candidates_status", "status"),
        Index("ix_duplicate_candidates_student_id", "student_id"),
        Index("ix_duplicate_candidates_import_job_id", "import_job_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
    )
    conflicting_student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[DuplicateMatchReason] = mapped_column(
        enum_column(DuplicateMatchReason, "duplicate_match_reason"),
        nullable=False,
    )
    status: Mapped[DuplicateCandidateStatus] = mapped_column(
        enum_column(DuplicateCandidateStatus, "duplicate_candidate_status"),
        nullable=False,
        server_default=text(f"'{DuplicateCandidateStatus.PENDING.value}'"),
    )
    resolution: Mapped[DuplicateResolution | None] = mapped_column(
        enum_column(DuplicateResolution, "duplicate_resolution"),
        nullable=True,
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_row: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    student: Mapped[Student] = relationship(foreign_keys=[student_id])
    candidate_student: Mapped[Student | None] = relationship(foreign_keys=[candidate_student_id])
    conflicting_student: Mapped[Student | None] = relationship(
        foreign_keys=[conflicting_student_id]
    )
    import_job: Mapped[ImportJob | None] = relationship()
    resolved_by: Mapped[User | None] = relationship()
