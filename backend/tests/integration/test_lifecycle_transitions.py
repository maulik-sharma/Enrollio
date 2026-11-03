"""Lifecycle transitions persist state and write one timeline event each."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import ActorType, LifecycleStatus
from app.models.lead import Lead
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
from app.repositories import users as users_repo
from app.services.lifecycle import (
    FUNNEL,
    InvalidLifecycleTransition,
    LeadNotFound,
    TransitionActor,
    TransitionNotPermitted,
    transition,
)
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]

MANAGER = "manager@enrollio.dev"


async def _manager(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransitionActor:
    async with session_factory() as session:
        user = await users_repo.get_by_email(session, MANAGER)
        assert user is not None
        loaded = await users_repo.get_with_permissions(session, user.id)
        assert loaded is not None
        return TransitionActor.from_user(loaded)


async def _lead(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: LifecycleStatus = LifecycleStatus.NEW_ENQUIRY,
) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        student = Student(
            first_name="Lifecycle",
            last_name="Tester",
            email_normalised=f"lifecycle-{status.value}@example.com",
        )
        session.add(student)
        await session.flush()
        lead = Lead(
            student_id=student.id,
            admission_cycle="2026-fall",
            lifecycle_status=status,
        )
        session.add(lead)
        await session.commit()
        return lead.id, student.id


async def test_each_funnel_transition_writes_exactly_one_timeline_event(
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    actor = await _manager(db_session_factory)
    lead_id, _ = await _lead(db_session_factory)

    for target in FUNNEL[1:]:
        async with db_session_factory() as session:
            lead = await transition(
                session,
                lead_id,
                target,
                actor,
                f"Move to {target.value}",
            )
            assert lead.lifecycle_status is target

    async with db_session_factory() as session:
        stored = await session.get(Lead, lead_id)
        assert stored is not None
        assert stored.lifecycle_status is LifecycleStatus.CONVERTED
        events = (
            (
                await session.execute(
                    select(TimelineEvent)
                    .where(TimelineEvent.lead_id == lead_id)
                    .order_by(TimelineEvent.created_at, TimelineEvent.id)
                )
            )
            .scalars()
            .all()
        )

    assert len(events) == len(FUNNEL) - 1
    assert [event.payload["to_state"] for event in events] == [state.value for state in FUNNEL[1:]]
    assert all(event.event_type == "lifecycle_transition" for event in events)
    assert all(event.actor_type is ActorType.USER for event in events)
    assert all(event.payload["reason"] for event in events)


async def test_invalid_transition_does_not_change_state_or_write_an_event(
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    actor = await _manager(db_session_factory)
    lead_id, _ = await _lead(db_session_factory)

    async with db_session_factory() as session:
        try:
            await transition(
                session,
                lead_id,
                LifecycleStatus.QUALIFIED,
                actor,
                "Skip ahead",
            )
        except InvalidLifecycleTransition:
            pass
        else:
            raise AssertionError("NEW_ENQUIRY -> QUALIFIED must be rejected")

    async with db_session_factory() as session:
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        assert lead.lifecycle_status is LifecycleStatus.NEW_ENQUIRY
        event_count = (
            await session.execute(
                select(func.count())
                .select_from(TimelineEvent)
                .where(TimelineEvent.lead_id == lead_id)
            )
        ).scalar_one()
    assert event_count == 0


async def test_agent_cannot_convert_and_manager_can_reopen(
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    actor = await _manager(db_session_factory)
    lead_id, _ = await _lead(db_session_factory, status=LifecycleStatus.ADMISSION_OFFERED)

    async with db_session_factory() as session:
        try:
            await transition(
                session,
                lead_id,
                LifecycleStatus.CONVERTED,
                TransitionActor.agent(),
                "Agent conversion",
            )
        except TransitionNotPermitted:
            pass
        else:
            raise AssertionError("An agent must not convert a lead")

    async with db_session_factory() as session:
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        assert lead.lifecycle_status is LifecycleStatus.ADMISSION_OFFERED

    async with db_session_factory() as session:
        lead = await transition(
            session,
            lead_id,
            LifecycleStatus.CONVERTED,
            actor,
            "Manager conversion",
        )
        assert lead.lifecycle_status is LifecycleStatus.CONVERTED

    async with db_session_factory() as session:
        try:
            await transition(
                session,
                lead_id,
                LifecycleStatus.NEW_ENQUIRY,
                TransitionActor.system(),
                "System reopen",
            )
        except TransitionNotPermitted:
            pass
        else:
            raise AssertionError("Only a manager can reopen a terminal lead")

    async with db_session_factory() as session:
        lead = await transition(
            session,
            lead_id,
            LifecycleStatus.NEW_ENQUIRY,
            actor,
            "Reopen after conversion",
        )
        assert lead.lifecycle_status is LifecycleStatus.NEW_ENQUIRY

    async with db_session_factory() as session:
        try:
            await transition(
                session,
                uuid.uuid4(),
                LifecycleStatus.CONTACTED,
                actor,
                "Unknown lead",
            )
        except LeadNotFound:
            pass
        else:
            raise AssertionError("Unknown lead ids must fail")
