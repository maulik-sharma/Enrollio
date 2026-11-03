"""Schemas for source-scoped partner API keys and lead ingestion."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.domain import ImportRowStatus


class ApiKeyCreateRequest(BaseModel):
    """Create a key for exactly one lead source."""

    name: str = Field(min_length=1, max_length=100)
    source_id: uuid.UUID | None = None
    source: str | None = Field(default=None, min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyCreatedRead(BaseModel):
    """One-time response containing the plaintext key."""

    id: uuid.UUID
    name: str
    source_id: uuid.UUID
    key_prefix: str
    key: str
    api_key: str
    expires_at: datetime | None
    created_at: datetime


class IngestRecordRead(BaseModel):
    """Outcome of one record in a partner batch."""

    index: int
    row_number: int
    status: ImportRowStatus
    student_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    reason: str | None = None
    message: str | None = None


class IngestBatchRead(BaseModel):
    """Per-record outcomes and summary counts for one accepted batch."""

    total: int
    created: int
    merged: int
    duplicate: int
    rejected: int
    results: list[IngestRecordRead]
