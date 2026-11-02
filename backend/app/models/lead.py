"""Lead model: one enquiry for a student, programme, and admission cycle."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import LifecycleStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.campus import Campus
    from app.models.lead_source import LeadSource
    from app.models.programme import Programme
    from app.models.student import Student
    from app.models.timeline_event import TimelineEvent
    from app.models.user import User


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Enquiry-specific data and lifecycle state for one student.

    The unique constraint on ``(student_id, programme_id, admission_cycle)`` is
    the database-level guarantee behind FR-02: re-importing the same enquiry
    cannot create a second lead.
    """

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "programme_id",
            "admission_cycle",
            name="uq_leads_student_programme_cycle",
        ),
        Index("ix_leads_assigned_counsellor_id", "assigned_counsellor_id"),
        Index("ix_leads_lifecycle_status", "lifecycle_status"),
        Index("ix_leads_student_id", "student_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    programme_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("programmes.id", ondelete="SET NULL"),
        nullable=True,
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    admission_cycle: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        enum_column(LifecycleStatus, "lifecycle_status"),
        nullable=False,
        server_default=text(f"'{LifecycleStatus.NEW_ENQUIRY.value}'"),
    )
    assigned_counsellor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_import_row: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    student: Mapped[Student] = relationship(back_populates="leads")
    programme: Mapped[Programme | None] = relationship(back_populates="leads")
    campus: Mapped[Campus | None] = relationship(back_populates="leads")
    source: Mapped[LeadSource | None] = relationship(back_populates="leads")
    assigned_counsellor: Mapped[User | None] = relationship()
    timeline_events: Mapped[list[TimelineEvent]] = relationship(back_populates="lead")
