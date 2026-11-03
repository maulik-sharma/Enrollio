"""Resolve name-only and conflicting-contact duplicates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import (
    DuplicateCandidateStatus,
    DuplicateResolution,
)
from app.models.consent_record import ConsentRecord
from app.models.duplicate_candidate import DuplicateCandidate
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
from app.repositories import duplicates as duplicates_repo
from app.repositories import leads as leads_repo
from app.repositories import students as students_repo


class DuplicateCandidateNotFound(Exception):
    """No candidate has the requested id."""


class DuplicateAlreadyResolved(Exception):
    """The candidate was already reviewed."""


@dataclass(frozen=True)
class _ContactSnapshot:
    email: str | None
    phone: str | None
    academic_score: Decimal | None
    graduation_year: int | None
    last_name: str


async def list_candidates(
    session: AsyncSession,
    *,
    status: DuplicateCandidateStatus | None = DuplicateCandidateStatus.PENDING,
    limit: int = 50,
    offset: int = 0,
) -> list[DuplicateCandidate]:
    """Return candidates awaiting review by default."""
    return await duplicates_repo.list_candidates(
        session,
        status=status,
        limit=limit,
        offset=offset,
    )


async def resolve_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    resolution: DuplicateResolution,
    resolved_by_id: uuid.UUID | None,
) -> DuplicateCandidate:
    """Merge, keep separate, or reject a flagged duplicate."""
    candidate = await duplicates_repo.get_candidate(session, candidate_id)
    if candidate is None:
        raise DuplicateCandidateNotFound
    if candidate.status is DuplicateCandidateStatus.RESOLVED:
        raise DuplicateAlreadyResolved

    if resolution is DuplicateResolution.MERGED:
        await _merge(candidate, session)
    elif resolution is DuplicateResolution.REJECTED and candidate.candidate_student_id is not None:
        await _delete_created_candidate(candidate, session)

    candidate.status = DuplicateCandidateStatus.RESOLVED
    candidate.resolution = resolution
    candidate.resolved_by_id = resolved_by_id
    candidate.resolved_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(candidate)
    return candidate


async def _merge(candidate: DuplicateCandidate, session: AsyncSession) -> None:
    if candidate.candidate_student_id is not None:
        source_id = candidate.candidate_student_id
        candidate.candidate_student_id = None
    elif candidate.conflicting_student_id is not None:
        source_id = candidate.conflicting_student_id
        candidate.conflicting_student_id = None
    else:
        return

    source = await students_repo.get(session, source_id)
    target = await students_repo.get(session, candidate.student_id)
    if source is None or target is None:
        return

    contact = _ContactSnapshot(
        email=source.email_normalised,
        phone=source.phone_e164,
        academic_score=source.academic_score,
        graduation_year=source.graduation_year,
        last_name=source.last_name,
    )
    await _move_leads(session, source=source, target=target)
    await session.execute(
        update(ConsentRecord)
        .where(ConsentRecord.student_id == source.id)
        .values(student_id=target.id)
    )
    await session.execute(
        update(TimelineEvent)
        .where(TimelineEvent.student_id == source.id)
        .values(student_id=target.id)
    )
    await session.delete(source)
    await session.flush()
    _fill_empty(target, contact)
    await session.flush()


async def _delete_created_candidate(
    candidate: DuplicateCandidate,
    session: AsyncSession,
) -> None:
    student_id = candidate.candidate_student_id
    if student_id is None:
        return
    candidate.candidate_student_id = None
    student = await students_repo.get(session, student_id)
    if student is not None:
        await session.delete(student)
        await session.flush()


async def _move_leads(
    session: AsyncSession,
    *,
    source: Student,
    target: Student,
) -> None:
    for lead in await leads_repo.list_for_student(session, source.id):
        existing = await leads_repo.find_for_enquiry(
            session,
            student_id=target.id,
            programme_id=lead.programme_id,
            admission_cycle=lead.admission_cycle,
        )
        if existing is not None:
            await session.delete(lead)
        else:
            lead.student_id = target.id
    await session.flush()


def _fill_empty(target: Student, contact: _ContactSnapshot) -> None:
    if target.email_normalised is None and contact.email is not None:
        target.email_normalised = contact.email
    if target.phone_e164 is None and contact.phone is not None:
        target.phone_e164 = contact.phone
    if target.academic_score is None and contact.academic_score is not None:
        target.academic_score = contact.academic_score
    if target.graduation_year is None and contact.graduation_year is not None:
        target.graduation_year = contact.graduation_year
    if not target.last_name and contact.last_name:
        target.last_name = contact.last_name
