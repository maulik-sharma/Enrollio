"""Timeline event queries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ActorType
from app.models.timeline_event import TimelineEvent

MESSAGE_SENT = "message_sent"


async def count_message_sent(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    category: str,
    since: datetime,
) -> int:
    """Count ``message_sent`` events for a student/category inside a window."""
    statement = (
        select(func.count())
        .select_from(TimelineEvent)
        .where(
            TimelineEvent.student_id == student_id,
            TimelineEvent.event_type == MESSAGE_SENT,
            TimelineEvent.actor_type == ActorType.SYSTEM,
            TimelineEvent.payload["category"].astext == category,
            TimelineEvent.created_at >= since,
        )
    )
    value = await session.scalar(statement)
    return int(value or 0)


async def create_message_sent(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    lead_id: uuid.UUID,
    actor_type: ActorType,
    actor_id: uuid.UUID | None,
    payload: dict[str, object],
) -> TimelineEvent:
    """Append one ``message_sent`` timeline event."""
    event = TimelineEvent(
        student_id=student_id,
        lead_id=lead_id,
        event_type=MESSAGE_SENT,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
    )
    session.add(event)
    return event
