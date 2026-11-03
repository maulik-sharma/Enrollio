"""Student model: the person behind one or more leads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.consent_record import ConsentRecord
    from app.models.lead import Lead
    from app.models.timeline_event import TimelineEvent


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Identity and contact details; enquiry-specific data lives on leads.

    ``email_normalised`` and ``phone_e164`` are the duplicate-detection keys
    (FR-02). Either may be missing, but not both, and each is unique when
    present. Values are normalised by the importer (M2.2) before they reach the
    database.
    """

    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint(
            "email_normalised IS NOT NULL OR phone_e164 IS NOT NULL",
            name="contact_present",
        ),
        CheckConstraint("email_normalised = lower(email_normalised)", name="email_lowercase"),
        CheckConstraint(
            "academic_score IS NULL OR (academic_score >= 0 AND academic_score <= 100)",
            name="academic_score_range",
        ),
        CheckConstraint(
            "graduation_year IS NULL OR (graduation_year >= 1900 AND graduation_year <= 2100)",
            name="graduation_year_range",
        ),
        Index(
            "uq_students_email_normalised",
            "email_normalised",
            unique=True,
            postgresql_where=text("email_normalised IS NOT NULL"),
        ),
        Index(
            "uq_students_phone_e164",
            "phone_e164",
            unique=True,
            postgresql_where=text("phone_e164 IS NOT NULL"),
        ),
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    email_normalised: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    academic_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    leads: Mapped[list[Lead]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    consent_records: Mapped[list[ConsentRecord]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        """Display name assembled from the two name parts."""
        return f"{self.first_name} {self.last_name}".strip()
