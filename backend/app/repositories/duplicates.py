"""Duplicate-candidate queries and persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import (
    DuplicateCandidateStatus,
    DuplicateMatchReason,
)
from app.models.duplicate_candidate import DuplicateCandidate


async def create_candidate(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    reason: DuplicateMatchReason,
    candidate_student_id: uuid.UUID | None = None,
    conflicting_student_id: uuid.UUID | None = None,
    import_job_id: uuid.UUID | None = None,
    row_number: int | None = None,
    raw_row: dict[str, Any] | None = None,
) -> DuplicateCandidate:
    """Persist a possible duplicate for manual review."""
    candidate = DuplicateCandidate(
        student_id=student_id,
        candidate_student_id=candidate_student_id,
        conflicting_student_id=conflicting_student_id,
        import_job_id=import_job_id,
        row_number=row_number,
        reason=reason,
        raw_row=raw_row,
    )
    session.add(candidate)
    await session.flush()
    return candidate


async def get_candidate(
    session: AsyncSession, candidate_id: uuid.UUID
) -> DuplicateCandidate | None:
    """Return one candidate by id."""
    return await session.get(DuplicateCandidate, candidate_id)


async def list_candidates(
    session: AsyncSession,
    *,
    status: DuplicateCandidateStatus | None,
    limit: int,
    offset: int,
) -> list[DuplicateCandidate]:
    """Return candidates, newest first, optionally filtered by status."""
    statement = select(DuplicateCandidate).order_by(DuplicateCandidate.created_at.desc())
    if status is not None:
        statement = statement.where(DuplicateCandidate.status == status)
    result = await session.execute(statement.limit(limit).offset(offset))
    return list(result.scalars())
