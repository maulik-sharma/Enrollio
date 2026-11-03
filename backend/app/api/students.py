"""Student consent endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, SettingsDep, require_permission
from app.core.domain import ConsentCategory, ConsentChannel
from app.core.permissions import PermissionName
from app.schemas.consent import ConsentRecordRead, ConsentRecordRequest
from app.services import consent as consent_service
from app.services.consent import StudentNotFound

router = APIRouter(
    prefix="/api/students",
    tags=["students"],
    dependencies=[Depends(require_permission(PermissionName.LEADS_VIEW_ALL))],
)


@router.post(
    "/{student_id}/consent",
    response_model=ConsentRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_consent(
    student_id: uuid.UUID,
    payload: ConsentRecordRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ConsentRecordRead:
    """Append a consent grant or revocation for a student."""
    try:
        record = await consent_service.record_consent(
            session,
            settings,
            student_id=student_id,
            channel=payload.channel,
            category=payload.category,
            source=payload.source,
            method=payload.method,
            granted=payload.granted,
        )
    except StudentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        ) from exc
    return ConsentRecordRead.model_validate(record)


@router.delete("/{student_id}/consent/{channel}/{category}", response_model=ConsentRecordRead)
async def revoke_consent(
    student_id: uuid.UUID,
    channel: ConsentChannel,
    category: ConsentCategory,
    session: SessionDep,
    settings: SettingsDep,
    source: str = Query(default="staff", min_length=1, max_length=100),
    method: str = Query(default="manual_entry", min_length=1, max_length=100),
) -> ConsentRecordRead:
    """Append a revocation for a student/channel/category."""
    try:
        record = await consent_service.revoke_consent(
            session,
            settings,
            student_id=student_id,
            channel=channel,
            category=category,
            source=source,
            method=method,
        )
    except StudentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        ) from exc
    return ConsentRecordRead.model_validate(record)
