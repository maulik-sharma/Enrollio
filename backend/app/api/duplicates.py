"""Duplicate-candidate review endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep, require_permission
from app.core.domain import DuplicateCandidateStatus, DuplicateResolution
from app.core.permissions import PermissionName
from app.schemas.duplicates import DuplicateCandidateRead, DuplicateResolveRequest
from app.services import duplicates as duplicates_service
from app.services.duplicates import DuplicateAlreadyResolved, DuplicateCandidateNotFound

router = APIRouter(
    prefix="/api/duplicates",
    tags=["duplicates"],
    dependencies=[Depends(require_permission(PermissionName.LEADS_VIEW_ALL))],
)

_ACTIONS = {
    "merge": DuplicateResolution.MERGED,
    "keep_separate": DuplicateResolution.KEPT_SEPARATE,
    "reject": DuplicateResolution.REJECTED,
}


@router.get("", response_model=list[DuplicateCandidateRead])
async def list_duplicates(
    session: SessionDep,
    status_filter: DuplicateCandidateStatus | None = Query(
        default=DuplicateCandidateStatus.PENDING,
        alias="status",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[DuplicateCandidateRead]:
    """Return possible duplicates awaiting review by default."""
    candidates = await duplicates_service.list_candidates(
        session,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [DuplicateCandidateRead.model_validate(candidate) for candidate in candidates]


@router.post("/{candidate_id}/resolve", response_model=DuplicateCandidateRead)
async def resolve_duplicate(
    candidate_id: uuid.UUID,
    payload: DuplicateResolveRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> DuplicateCandidateRead:
    """Merge, keep separate, or reject a flagged duplicate."""
    try:
        candidate = await duplicates_service.resolve_candidate(
            session,
            candidate_id=candidate_id,
            resolution=_ACTIONS[payload.action],
            resolved_by_id=user.id,
        )
    except DuplicateCandidateNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Duplicate candidate not found",
        ) from exc
    except DuplicateAlreadyResolved as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This duplicate candidate is already resolved",
        ) from exc
    return DuplicateCandidateRead.model_validate(candidate)
