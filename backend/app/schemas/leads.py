"""Lead CRUD, detail, and pagination schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain import LifecycleStatus
from app.schemas.consent import ConsentRecordRead


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email_normalised: str | None
    phone_e164: str | None
    date_of_birth: date | None
    academic_score: Decimal | None
    graduation_year: int | None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    programme_id: uuid.UUID | None
    campus_id: uuid.UUID | None
    source_id: uuid.UUID | None
    admission_cycle: str
    lifecycle_status: LifecycleStatus
    assigned_counsellor_id: uuid.UUID | None
    import_job_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class LeadCreateRead(LeadRead):
    duplicate_detected: bool


class LeadListRead(BaseModel):
    items: list[LeadRead]
    next_cursor: str | None


class LeadDetailRead(BaseModel):
    lead: LeadRead
    student: StudentRead
    consent_summary: list[ConsentRecordRead]
    assessments: list[dict[str, object]] = Field(default_factory=list)


class LeadCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str | None = None
    phone: str | None = None
    programme_id: uuid.UUID | None = None
    campus_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    admission_cycle: str | None = Field(default=None, max_length=32)
    academic_score: Decimal | None = Field(default=None, ge=0, le=100)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    assigned_counsellor_id: uuid.UUID | None = None


class LeadUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    academic_score: Decimal | None = Field(default=None, ge=0, le=100)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    programme_id: uuid.UUID | None = None
    campus_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    admission_cycle: str | None = Field(default=None, max_length=32)
    assigned_counsellor_id: uuid.UUID | None = None
