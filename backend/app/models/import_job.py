"""Import jobs, reusable column mappings, and per-row results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.domain import ImportJobStatus, ImportRowStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.student import Student
    from app.models.user import User


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded CSV/XLSX file and its processing state."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_status", "status"),
        Index("ix_import_jobs_uploaded_by_id", "uploaded_by_id"),
    )

    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        enum_column(ImportJobStatus, "import_job_status"),
        nullable=False,
        server_default=text(f"'{ImportJobStatus.UPLOADED.value}'"),
    )
    headers: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    mapping: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    merged_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_by: Mapped[User | None] = relationship()
    rows: Mapped[list[ImportRowResult]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    leads: Mapped[list[Lead]] = relationship(back_populates="import_job")


class MappingTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved source-column to system-field mapping, keyed by source name."""

    __tablename__ = "mapping_templates"
    __table_args__ = (UniqueConstraint("source_name", name="uq_mapping_templates_source_name"),)

    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mapping: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[User | None] = relationship()


class ImportRowResult(UUIDPrimaryKeyMixin, Base):
    """The outcome of validating and applying one row."""

    __tablename__ = "import_row_results"
    __table_args__ = (
        UniqueConstraint("import_job_id", "row_number", name="uq_import_row_results_job_row"),
        Index("ix_import_row_results_job_status", "import_job_id", "status"),
    )

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ImportRowStatus] = mapped_column(
        enum_column(ImportRowStatus, "import_row_status"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_row: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    job: Mapped[ImportJob] = relationship(back_populates="rows")
    student: Mapped[Student | None] = relationship()
    lead: Mapped[Lead | None] = relationship()
