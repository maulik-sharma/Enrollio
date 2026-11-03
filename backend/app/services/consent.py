"""Consent records, send checks, and promotional opt-out handling (FR-04)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.domain import ConsentCategory, ConsentChannel, LifecycleStatus
from app.models.consent_record import ConsentRecord
from app.repositories import consent as consent_repo
from app.repositories import leads as leads_repo
from app.repositories import students as students_repo
from app.services.lifecycle import TransitionActor, transition

PROMOTIONAL_OPT_OUT_REASON = "Promotional consent revoked"


class StudentNotFound(Exception):
    """No student has the requested id."""


def consent_allows(record: ConsentRecord | None, category: ConsentCategory) -> bool:
    """Apply the latest record; missing promotional consent is a block.

    Transactional messages (confirmations and reminders) are allowed until a
    student explicitly revokes that category. Promotional messages require an
    explicit granted record, matching PRD guardrail 1.
    """
    if record is None:
        return category is ConsentCategory.TRANSACTIONAL
    return record.granted


async def can_send(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    channel: ConsentChannel,
    category: ConsentCategory,
) -> bool:
    """Return whether a student may receive this channel/category now."""
    record = await consent_repo.latest(
        session,
        student_id=student_id,
        channel=channel,
        category=category,
    )
    return consent_allows(record, category)


async def record_consent(
    session: AsyncSession,
    settings: Settings,
    *,
    student_id: uuid.UUID,
    channel: ConsentChannel,
    category: ConsentCategory,
    source: str,
    method: str,
    granted: bool = True,
    commit: bool = True,
) -> ConsentRecord:
    """Append a grant or revocation and close promotional leads when needed."""
    student = await students_repo.get(session, student_id)
    if student is None:
        raise StudentNotFound

    record = ConsentRecord(
        student_id=student_id,
        channel=channel,
        category=category,
        granted=granted,
        source=source.strip(),
        method=method.strip(),
    )
    session.add(record)
    await session.flush()

    if (
        not granted
        and category is ConsentCategory.PROMOTIONAL
        and settings.CONSENT_PROMOTIONAL_OPT_OUT_LIFECYCLE
        and not await _has_granted_promotional_consent(session, student_id)
    ):
        await _close_active_leads(session, student_id)

    if commit:
        await session.commit()
        await session.refresh(record)
    return record


async def revoke_consent(
    session: AsyncSession,
    settings: Settings,
    *,
    student_id: uuid.UUID,
    channel: ConsentChannel,
    category: ConsentCategory,
    source: str,
    method: str,
) -> ConsentRecord:
    """Append a revocation; promotional opt-out may close active leads."""
    return await record_consent(
        session,
        settings,
        student_id=student_id,
        channel=channel,
        category=category,
        source=source,
        method=method,
        granted=False,
    )


async def consent_summary(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
) -> list[ConsentRecord]:
    """Return the latest decision per channel/category, in stable order."""
    records = await consent_repo.list_for_student(session, student_id=student_id)
    latest: dict[tuple[ConsentChannel, ConsentCategory], ConsentRecord] = {}
    for record in records:
        latest[(record.channel, record.category)] = record
    return [latest[key] for key in sorted(latest, key=lambda item: (item[0].value, item[1].value))]


async def _has_granted_promotional_consent(
    session: AsyncSession,
    student_id: uuid.UUID,
) -> bool:
    records = await consent_repo.list_for_student(
        session,
        student_id=student_id,
        category=ConsentCategory.PROMOTIONAL,
    )
    latest_by_channel: dict[ConsentChannel, bool] = {}
    for record in records:
        latest_by_channel[record.channel] = record.granted
    return any(latest_by_channel.values())


async def _close_active_leads(session: AsyncSession, student_id: uuid.UUID) -> None:
    terminal = {
        LifecycleStatus.LOST,
        LifecycleStatus.DISQUALIFIED,
        LifecycleStatus.UNRESPONSIVE,
        LifecycleStatus.OPTED_OUT,
        LifecycleStatus.CONVERTED,
    }
    for lead in await leads_repo.list_for_student(session, student_id):
        if lead.lifecycle_status in terminal:
            continue
        await transition(
            session,
            lead.id,
            LifecycleStatus.OPTED_OUT,
            TransitionActor.system(),
            PROMOTIONAL_OPT_OUT_REASON,
        )
