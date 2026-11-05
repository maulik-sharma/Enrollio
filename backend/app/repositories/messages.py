"""Message row helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import MessageChannel, MessageDirection, MessageStatus
from app.models.message import Message


async def get(session: AsyncSession, message_id: uuid.UUID) -> Message | None:
    """Return a message by primary key."""
    return await session.scalar(select(Message).where(Message.id == message_id))


async def create(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    direction: MessageDirection,
    channel: MessageChannel,
    status: MessageStatus,
    content_text: str | None = None,
    content_html: str | None = None,
    provider_message_id: str | None = None,
    intent: str | None = None,
    created_by_agent_action_id: uuid.UUID | None = None,
) -> Message:
    """Insert one message row."""
    message = Message(
        conversation_id=conversation_id,
        direction=direction,
        channel=channel,
        status=status,
        content_text=content_text,
        content_html=content_html,
        provider_message_id=provider_message_id,
        intent=intent,
        created_by_agent_action_id=created_by_agent_action_id,
    )
    session.add(message)
    await session.flush()
    return message
