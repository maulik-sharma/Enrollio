"""Duplicate-candidate request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.domain import (
    DuplicateCandidateStatus,
    DuplicateMatchReason,
    DuplicateResolution,
)


class DuplicateResolveRequest(BaseModel):
    """Manual decision for a possible duplicate."""

    action: Literal["merge", "keep_separate", "reject"]


class DuplicateCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    candidate_student_id: uuid.UUID | None
    conflicting_student_id: uuid.UUID | None
    import_job_id: uuid.UUID | None
    row_number: int | None
    reason: DuplicateMatchReason
    status: DuplicateCandidateStatus
    resolution: DuplicateResolution | None
    resolved_by_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
