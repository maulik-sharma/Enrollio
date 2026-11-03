"""Consent-record lookups."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ConsentCategory, ConsentChannel
from app.models.consent_record import ConsentRecord


async def latest(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    channel: ConsentChannel,
    category: ConsentCategory,
) -> ConsentRecord | None:
    """Return the newest decision for a student/channel/category."""
    return await session.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.student_id == student_id,
            ConsentRecord.channel == channel,
            ConsentRecord.category == category,
        )
        .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc())
        .limit(1)
    )


async def list_for_student(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    category: ConsentCategory | None = None,
) -> list[ConsentRecord]:
    """Return a student's consent history, newest first."""
    statement = select(ConsentRecord).where(ConsentRecord.student_id == student_id)
    if category is not None:
        statement = statement.where(ConsentRecord.category == category)
    result = await session.execute(statement.order_by(ConsentRecord.recorded_at, ConsentRecord.id))
    return list(result.scalars())
