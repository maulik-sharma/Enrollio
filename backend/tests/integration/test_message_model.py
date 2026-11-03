"""Conversation/message schema, uniqueness, cascades, and event idempotency.

These tests exercise M3.2 at the database level: the schema must reject a
repeated provider event before any second status change can be applied.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import (
    ConversationStatus,
    MessageChannel,
    MessageDirection,
    MessageEventType,
    MessageStatus,
)
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.message_event import MessageEvent
from app.models.student import Student
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]


async def _lead(session: AsyncSession, marker: str) -> Lead:
    student = Student(
        first_name="Message",
        last_name=marker,
        email_normalised=f"{marker.lower()}@enrollio.dev",
    )
    session.add(student)
    await session.flush()
    lead = Lead(student_id=student.id, admission_cycle="2026-fall")
    session.add(lead)
    await session.flush()
    return lead


async def _conversation(
    session: AsyncSession,
    lead: Lead,
    channel: MessageChannel = MessageChannel.EMAIL,
) -> Conversation:
    conversation = Conversation(lead_id=lead.id, channel=channel)
    session.add(conversation)
    await session.flush()
    return conversation


async def _message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    provider_message_id: str | None = None,
    direction: MessageDirection = MessageDirection.OUTBOUND,
    status: MessageStatus = MessageStatus.SENT,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        direction=direction,
        channel=conversation.channel,
        content_text="Hello from the message test",
        provider_message_id=provider_message_id,
        status=status,
    )
    session.add(message)
    await session.flush()
    return message


async def test_conversation_defaults_and_lead_channel_uniqueness(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        lead = await _lead(session, "Conversation")
        conversation = await _conversation(session, lead)
        await session.commit()
        conversation_id = conversation.id
        lead_id = lead.id

    async with db_session_factory() as session:
        stored = await session.get(Conversation, conversation_id)
        assert stored is not None
        assert stored.status is ConversationStatus.OPEN
        assert stored.last_message_at is None

        session.add(Conversation(lead_id=lead_id, channel=MessageChannel.EMAIL))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with db_session_factory() as session:
        session.add(Conversation(lead_id=lead_id, channel=MessageChannel.WHATSAPP))
        await session.commit()


async def test_provider_message_id_is_unique_within_a_channel(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        lead = await _lead(session, "Provider")
        email = await _conversation(session, lead, MessageChannel.EMAIL)
        whatsapp = await _conversation(session, lead, MessageChannel.WHATSAPP)
        await _message(session, email, provider_message_id="shared-1")
        # The same provider id is allowed on a different channel: provider ids
        # are scoped to their channel rather than globally.
        await _message(session, whatsapp, provider_message_id="shared-1")
        await session.commit()
        email_id = email.id

    async with db_session_factory() as session:
        session.add(
            Message(
                conversation_id=email_id,
                direction=MessageDirection.OUTBOUND,
                channel=MessageChannel.EMAIL,
                content_text="Duplicate provider id",
                provider_message_id="shared-1",
                status=MessageStatus.SENT,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_duplicate_provider_event_is_rejected_without_a_second_status_change(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    occurred_at = datetime.now(UTC)

    async with db_session_factory() as session:
        lead = await _lead(session, "Event")
        conversation = await _conversation(session, lead)
        message = await _message(
            session,
            conversation,
            provider_message_id="message-1",
            status=MessageStatus.SENT,
        )
        session.add(
            MessageEvent(
                message_id=message.id,
                event_type=MessageEventType.DELIVERED,
                provider_event_id="event-1",
                occurred_at=occurred_at,
            )
        )
        message.status = MessageStatus.DELIVERED
        await session.commit()
        message_id = message.id

    async with db_session_factory() as session:
        stored = await session.get(Message, message_id)
        assert stored is not None
        assert stored.status is MessageStatus.DELIVERED

        session.add(
            MessageEvent(
                message_id=message_id,
                event_type=MessageEventType.OPENED,
                provider_event_id="event-1",
                occurred_at=occurred_at,
            )
        )
        stored.status = MessageStatus.OPENED
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with db_session_factory() as session:
        stored = await session.get(Message, message_id)
        event_count = await session.scalar(
            select(func.count())
            .select_from(MessageEvent)
            .where(MessageEvent.message_id == message_id)
        )

    assert stored is not None
    assert stored.status is MessageStatus.DELIVERED
    assert event_count == 1


async def test_deleting_a_lead_cascades_conversations_messages_and_events(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        lead = await _lead(session, "Cascade")
        conversation = await _conversation(session, lead)
        message = await _message(session, conversation, provider_message_id="message-2")
        session.add(
            MessageEvent(
                message_id=message.id,
                event_type=MessageEventType.DELIVERED,
                provider_event_id="event-2",
                occurred_at=datetime.now(UTC),
            )
        )
        await session.commit()
        lead_id = lead.id

    async with db_session_factory() as session:
        await session.execute(delete(Lead).where(Lead.id == lead_id))
        await session.commit()

    async with db_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert await session.scalar(select(func.count()).select_from(Message)) == 0
        assert await session.scalar(select(func.count()).select_from(MessageEvent)) == 0


async def test_orm_deleting_a_lead_also_removes_the_conversation_tree(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        lead = await _lead(session, "OrmCascade")
        conversation = await _conversation(session, lead)
        message = await _message(session, conversation, provider_message_id="message-3")
        session.add(
            MessageEvent(
                message_id=message.id,
                event_type=MessageEventType.DELIVERED,
                provider_event_id="event-3",
                occurred_at=datetime.now(UTC),
            )
        )
        await session.commit()
        lead_id = lead.id

    async with db_session_factory() as session:
        stored = await session.get(Lead, lead_id)
        assert stored is not None
        await session.delete(stored)
        await session.commit()

    async with db_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert await session.scalar(select(func.count()).select_from(Message)) == 0
        assert await session.scalar(select(func.count()).select_from(MessageEvent)) == 0
