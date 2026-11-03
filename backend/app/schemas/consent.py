"""Consent request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain import ConsentCategory, ConsentChannel


class ConsentRecordRequest(BaseModel):
    """A staff-recorded consent grant or revocation."""

    channel: ConsentChannel
    category: ConsentCategory
    granted: bool = True
    source: str = Field(default="staff", min_length=1, max_length=100)
    method: str = Field(default="manual_entry", min_length=1, max_length=100)


class ConsentRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    channel: ConsentChannel
    category: ConsentCategory
    granted: bool
    source: str
    method: str
    recorded_at: datetime
