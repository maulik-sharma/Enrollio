"""Segment endpoints: create, validate, and preview lead filters (M3.5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, require_permission
from app.core.permissions import PermissionName
from app.schemas.campaigns import (
    SegmentCreate,
    SegmentPreview,
    SegmentPreviewItem,
    SegmentRead,
)
from app.services import segments as segments_service
from app.services.segments import SegmentFilterError

router = APIRouter(
    prefix="/api/segments",
    tags=["segments"],
    dependencies=[Depends(require_permission(PermissionName.CAMPAIGNS_MANAGE))],
)


@router.post("", response_model=SegmentRead, status_code=status.HTTP_201_CREATED)
async def create_segment(
    payload: SegmentCreate,
    session: SessionDep,
) -> SegmentRead:
    """Validate and save a named segment filter."""
    try:
        segment = await segments_service.save_segment(
            session,
            name=payload.name,
            filter_definition=payload.filter_definition,
        )
    except SegmentFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    await session.commit()
    return SegmentRead.model_validate(segment)


@router.post("/{segment_id}/preview", response_model=SegmentPreview)
async def preview_segment(
    segment_id: uuid.UUID,
    session: SessionDep,
    limit: int = Query(default=segments_service.SAMPLE_LIMIT, ge=1, le=50),
) -> SegmentPreview:
    """Evaluate the saved filter: total matches plus a sample of leads."""
    segment = await segments_service.get_segment(session, segment_id)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found",
        )
    try:
        total = await segments_service.count_matching(session, segment.filter_definition)
        sample = await segments_service.sample_matching(
            session,
            segment.filter_definition,
            limit=limit,
        )
    except SegmentFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    return SegmentPreview(
        total=total,
        sample=[
            SegmentPreviewItem(
                lead_id=lead.id,
                first_name=lead.student.first_name,
                last_name=lead.student.last_name,
                email=lead.student.email_normalised,
                lifecycle_status=lead.lifecycle_status.value,
            )
            for lead in sample
        ],
    )
