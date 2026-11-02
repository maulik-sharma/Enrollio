"""Timeline events: the append-only activity log for a student or lead."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import ActorType
from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.student import Student


class TimelineEvent(UUIDPrimaryKeyMixin, Base):
    """Something that happened, shown on the student/lead timeline.

    ``actor_id`` is deliberately not a foreign key: it can point at a user, an
    agent run, or a system process. Events are never updated, so there is no
    ``updated_at``.
    """

    __tablename__ = "timeline_events"
    __table_args__ = (Index("ix_timeline_events_student_created_at", "student_id", "created_at"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(
        enum_column(ActorType, "actor_type"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    student: Mapped[Student] = relationship(back_populates="timeline_events")
    lead: Mapped[Lead | None] = relationship(back_populates="timeline_events")
