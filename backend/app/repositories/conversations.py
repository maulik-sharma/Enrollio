"""Conversation thread helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import MessageChannel
from app.models.conversation import Conversation


async def get(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    """Return a conversation by primary key."""
    return await session.scalar(select(Conversation).where(Conversation.id == conversation_id))


async def find(
    session: AsyncSession, *, lead_id: uuid.UUID, channel: MessageChannel
) -> Conversation | None:
    """Return the single thread for a lead/channel pair."""
    return await session.scalar(
        select(Conversation).where(
            Conversation.lead_id == lead_id,
            Conversation.channel == channel,
        )
    )


async def get_or_create(
    session: AsyncSession,
    *,
    lead_id: uuid.UUID,
    channel: MessageChannel,
) -> Conversation:
    """Return the thread for a lead/channel, creating it when missing.

    The unique constraint on ``(lead_id, channel)`` is the concurrency guard;
    a flush-time IntegrityError re-selects the winning row.
    """
    existing = await find(session, lead_id=lead_id, channel=channel)
    if existing is not None:
        return existing

    conversation = Conversation(lead_id=lead_id, channel=channel)
    session.add(conversation)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raced = await find(session, lead_id=lead_id, channel=channel)
        if raced is None:
            raise
        return raced
    return conversation


async def touch_last_message_at(
    session: AsyncSession,
    conversation: Conversation,
    *,
    at: datetime,
) -> None:
    """Record that a message entered the thread at ``at``."""
    conversation.last_message_at = at
    await session.flush()
