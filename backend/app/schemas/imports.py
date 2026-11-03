"""Import job request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain import ImportJobStatus


class ImportMappingRequest(BaseModel):
    """Source column -> system field. Multiple sources may not map to one field."""

    mapping: dict[str, str] = Field(min_length=1)


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_name: str
    original_filename: str
    file_type: str
    status: ImportJobStatus
    headers: list[str]
    mapping: dict[str, str] | None
    total_rows: int
    created_count: int
    merged_count: int
    rejected_count: int
    duplicate_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MappingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_name: str
    mapping: dict[str, str]
    updated_at: datetime
