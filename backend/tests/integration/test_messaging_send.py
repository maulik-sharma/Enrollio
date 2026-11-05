"""Integration tests for the messaging entry point guards and happy path."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Environment, Settings
from app.core.domain import (
    ActorType,
    ApprovalStatus,
    ConsentCategory,
    ConsentChannel,
    EmailDirection,
    LifecycleStatus,
    MessageCategory,
    MessageChannel,
    MessageStatus,
    SendStatus,
)
from app.integrations.email.mock import MockEmailProvider
from app.integrations.whatsapp.base import WhatsAppNotImplemented
from app.models.approval_item import ApprovalItem
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.mock_email_message import MockEmailMessage
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
from app.repositories import approvals as approvals_repo
from app.repositories import timeline as timeline_repo
from app.services import consent as consent_service
from app.services import messaging
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]


def _settings(**overrides: Any) -> Settings:
    """Settings with the quiet window disabled unless a test overrides it."""
    base: dict[str, Any] = {
        "ENV": Environment.test,
        "JWT_SECRET": "test-secret",
        "QUIET_HOURS_START_HOUR": 9,
        "QUIET_HOURS_END_HOUR": 9,
        "_env_file": None,
        **overrides,
    }
    return Settings(**base)


@dataclass(frozen=True)
class _Seed:
    student_id: uuid.UUID
    lead_id: uuid.UUID


async def _student_and_lead(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str | None,
) -> _Seed:
    async with session_factory() as session:
        # The students table requires at least one contact channel.
        student = Student(
            first_name="Asha",
            last_name="Rao",
            email_normalised=email,
            phone_e164=None if email is not None else "+919876500010",
        )
        session.add(student)
        await session.flush()
        lead = Lead(
            student_id=student.id,
            admission_cycle="2026-fall",
            lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
        )
        session.add(lead)
        await session.commit()
        return _Seed(student_id=student.id, lead_id=lead.id)


def _provider(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> MockEmailProvider:
    return MockEmailProvider(db_session_factory, webhook_secret="secret")


async def _send(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    provider: MockEmailProvider,
    seed: _Seed,
    category: MessageCategory,
    *,
    subject: str = "Subject",
    text: str = "Hello",
    now: datetime | None = None,
) -> messaging.SendResult:
    async with session_factory() as session:
        lead = await session.get(Lead, seed.lead_id)
        assert lead is not None
        result = await messaging.send(
            session,
            settings,
            provider,
            lead=lead,
            channel=MessageChannel.EMAIL,
            category=category,
            content=messaging.MessageContent(subject=subject, text_body=text),
            actor=messaging.MessageActor(actor_type=ActorType.USER, actor_id=uuid.uuid4()),
            now=now,
        )
        await session.commit()
        return result


async def _outbound_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        rows = await session.execute(
            select(MockEmailMessage).where(MockEmailMessage.direction == EmailDirection.OUTBOUND)
        )
        return len(rows.scalars().all())


async def _grant_promotional(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    seed: _Seed,
) -> None:
    async with session_factory() as session:
        await consent_service.record_consent(
            session,
            settings,
            student_id=seed.student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.PROMOTIONAL,
            source="web_form",
            method="checkbox",
            granted=True,
        )


async def test_consent_refusal_never_reaches_the_provider(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")

    # Promotional requires an explicit grant: no record means blocked.
    blocked_default = await _send(
        db_session_factory,
        settings,
        _provider(db_session_factory),
        seed,
        MessageCategory.PROMOTIONAL,
    )
    assert blocked_default.status is SendStatus.BLOCKED
    assert blocked_default.reason == messaging.CONSENT_KEY

    # A revoked transactional record also blocks.
    async with db_session_factory() as session:
        await consent_service.record_consent(
            session,
            settings,
            student_id=seed.student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.TRANSACTIONAL,
            source="web_form",
            method="link",
            granted=False,
        )
    blocked = await _send(
        db_session_factory,
        settings,
        _provider(db_session_factory),
        seed,
        MessageCategory.TRANSACTIONAL,
    )
    assert blocked.status is SendStatus.BLOCKED
    assert blocked.reason == messaging.CONSENT_KEY
    assert await _outbound_count(db_session_factory) == 0


async def test_third_promotional_within_seven_days_blocked(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")
    await _grant_promotional(db_session_factory, settings, seed)
    provider = _provider(db_session_factory)

    async with db_session_factory() as session:
        for _ in range(2):
            session.add(
                TimelineEvent(
                    student_id=seed.student_id,
                    lead_id=seed.lead_id,
                    event_type="message_sent",
                    actor_type=ActorType.SYSTEM,
                    payload={"category": "promotional", "channel": "email"},
                )
            )
        await session.commit()

    result = await _send(db_session_factory, settings, provider, seed, MessageCategory.PROMOTIONAL)
    assert result.status is SendStatus.BLOCKED
    assert result.reason == messaging.PROMOTIONAL_FREQ_CAP_KEY
    assert await _outbound_count(db_session_factory) == 0

    # Age one event out of the window: the cap counts only the last 7 days.
    async with db_session_factory() as session:
        oldest_id = await session.scalar(
            select(TimelineEvent.id)
            .where(TimelineEvent.lead_id == seed.lead_id)
            .order_by(TimelineEvent.created_at)
            .limit(1)
        )
        assert oldest_id is not None
        await session.execute(
            update(TimelineEvent)
            .where(TimelineEvent.id == oldest_id)
            .values(created_at=datetime.now(UTC) - timedelta(days=8))
        )
        await session.commit()

    allowed = await _send(db_session_factory, settings, provider, seed, MessageCategory.PROMOTIONAL)
    assert allowed.status is SendStatus.SENT
    assert await _outbound_count(db_session_factory) == 1


async def test_sensitive_category_waits_for_an_approval(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")
    provider = _provider(db_session_factory)

    result = await _send(
        db_session_factory,
        settings,
        provider,
        seed,
        MessageCategory.SCHOLARSHIP,
        subject="Scholarship update",
    )
    assert result.status is SendStatus.PENDING_APPROVAL
    assert result.approval_item_id is not None
    assert await _outbound_count(db_session_factory) == 0

    async with db_session_factory() as session:
        items = list((await session.execute(select(ApprovalItem))).scalars())
        assert len(items) == 1
        item = items[0]
        assert item.status is ApprovalStatus.PENDING
        assert item.item_type == messaging.MESSAGE_SEND_APPROVAL_TYPE
        assert item.lead_id == seed.lead_id
        assert item.payload["category"] == "scholarship"
        assert item.payload["subject"] == "Scholarship update"
        assert item.draft_content is not None

    # A repeat send is blocked by the still-pending approval, not duplicated.
    repeat = await _send(
        db_session_factory,
        settings,
        provider,
        seed,
        MessageCategory.SCHOLARSHIP,
        subject="Scholarship follow-up",
    )
    assert repeat.status is SendStatus.PENDING_APPROVAL
    assert repeat.approval_item_id == result.approval_item_id
    async with db_session_factory() as session:
        assert len(list((await session.execute(select(ApprovalItem))).scalars())) == 1
        pending = await approvals_repo.latest_pending(
            session, lead_id=seed.lead_id, item_type=messaging.MESSAGE_SEND_APPROVAL_TYPE
        )
        assert pending is not None
        assert pending.id == result.approval_item_id
        assert pending.payload["subject"] == "Scholarship update"


async def test_quiet_hours_queue_without_a_provider_call(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings(QUIET_HOURS_START_HOUR=0, QUIET_HOURS_END_HOUR=23)
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")
    await _grant_promotional(db_session_factory, settings, seed)
    provider = _provider(db_session_factory)

    result = await _send(db_session_factory, settings, provider, seed, MessageCategory.PROMOTIONAL)
    assert result.status is SendStatus.QUEUED
    assert result.reason == messaging.QUIET_HOURS_KEY
    assert result.message_id is not None
    assert result.next_allowed_at is not None
    assert result.next_allowed_at.hour == 23
    assert await _outbound_count(db_session_factory) == 0

    async with db_session_factory() as session:
        message = await session.get(Message, result.message_id)
        assert message is not None
        assert message.status is MessageStatus.QUEUED
        assert message.provider_message_id is None
        conversation = await session.get(Conversation, result.conversation_id)
        assert conversation is not None
        assert conversation.last_message_at is None


async def test_happy_path_records_message_conversation_and_timeline(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")
    provider = _provider(db_session_factory)
    moment = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)

    result = await _send(
        db_session_factory,
        settings,
        provider,
        seed,
        MessageCategory.TRANSACTIONAL,
        now=moment,
    )
    assert result.status is SendStatus.SENT
    assert result.message_id is not None

    async with db_session_factory() as session:
        message = await session.get(Message, result.message_id)
        assert message is not None
        assert message.status is MessageStatus.SENT
        assert message.direction.value == "outbound"
        assert message.intent == "transactional"
        assert message.provider_message_id is not None

        conversation = await session.get(Conversation, message.conversation_id)
        assert conversation is not None
        assert conversation.channel.value == "email"
        assert conversation.last_message_at == moment

        events = list(
            (
                await session.execute(
                    select(TimelineEvent).where(
                        TimelineEvent.student_id == seed.student_id,
                        TimelineEvent.event_type == "message_sent",
                    )
                )
            ).scalars()
        )
        assert len(events) == 1
        assert events[0].payload["category"] == "transactional"
        assert events[0].payload["message_id"] == str(message.id)
        assert (
            await timeline_repo.count_message_sent(
                session,
                student_id=seed.student_id,
                category="promotional",
                since=moment - timedelta(days=7),
            )
            == 0
        )

    mocks = await _outbound_count(db_session_factory)
    assert mocks == 1


async def test_missing_recipient_address_blocks(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email=None)
    provider = _provider(db_session_factory)

    result = await _send(
        db_session_factory, settings, provider, seed, MessageCategory.TRANSACTIONAL
    )
    assert result.status is SendStatus.BLOCKED
    assert result.reason == messaging.MISSING_RECIPIENT_KEY
    assert await _outbound_count(db_session_factory) == 0


async def test_whatsapp_channel_raises_until_phase_2(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = _settings()
    seed = await _student_and_lead(db_session_factory, email="asha@example.com")

    async with db_session_factory() as session:
        lead = await session.get(Lead, seed.lead_id)
        assert lead is not None
        with pytest.raises(WhatsAppNotImplemented):
            await messaging.send(
                session,
                settings,
                _provider(db_session_factory),
                lead=lead,
                channel=MessageChannel.WHATSAPP,
                category=MessageCategory.TRANSACTIONAL,
                content=messaging.MessageContent(subject="Hi", text_body="Hello"),
                actor=messaging.MessageActor(actor_type=ActorType.USER, actor_id=uuid.uuid4()),
            )
