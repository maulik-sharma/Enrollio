"""Segment and campaign request/response schemas (M3.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain import ApprovalStatus, CampaignStatus


class SegmentCreate(BaseModel):
    """A named filter definition; unknown fields/operators are a 400."""

    name: str = Field(min_length=1, max_length=120)
    filter_definition: dict[str, Any]
    # ``all`` is validated (field/op whitelist) by the segment service so the
    # raw JSON passes through untouched.


class SegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    filter_definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SegmentPreviewItem(BaseModel):
    """One sampled lead for a segment preview."""

    lead_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str | None
    lifecycle_status: str


class SegmentPreview(BaseModel):
    total: int
    sample: list[SegmentPreviewItem]


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    channel: str = Field(pattern="^(email|whatsapp|sms)$")
    template_id: uuid.UUID
    segment_id: uuid.UUID
    scheduled_at: datetime | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    channel: str
    template_id: uuid.UUID
    segment_id: uuid.UUID
    status: CampaignStatus
    scheduled_at: datetime | None
    approval_status: ApprovalStatus | None
    created_at: datetime
    updated_at: datetime


class CampaignLaunchResult(BaseModel):
    status: CampaignStatus
    approval_status: ApprovalStatus | None
    recipients_created: int
    dispatch: str | None
    approval_threshold: int


class CampaignReportItem(BaseModel):
    """Per-status recipient counts with a reason breakdown."""

    total: int
    by_status: dict[str, int] = Field(
        description="Counts by recipient status value (sent/blocked/...)",
    )
    reasons: dict[str, int]


class CampaignPreviewItem(BaseModel):
    """The rendered template for one sampled lead."""

    lead_id: uuid.UUID
    subject: str
    text_body: str
    html_body: str


class CampaignPreview(BaseModel):
    campaign_id: uuid.UUID
    sample: list[CampaignPreviewItem]
