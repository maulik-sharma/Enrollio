"""Lead uniqueness and defaults at the database level (M2.1)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import LifecycleStatus
from app.models.lead import Lead
from app.models.programme import Programme
from app.models.student import Student
from tests.conftest import requires_postgres

pytestmark = pytest.mark.integration


async def _programme(session: AsyncSession) -> Programme:
    programme = Programme(name=f"B.Tech Computer Science {uuid.uuid4().hex[:6]}")
    session.add(programme)
    await session.flush()
    return programme


async def _student(session: AsyncSession, marker: str) -> Student:
    student = Student(
        first_name="Test",
        last_name=marker,
        email_normalised=f"{marker.lower()}@enrollio.dev",
    )
    session.add(student)
    await session.flush()
    return student


@requires_postgres
async def test_duplicate_lead_for_same_student_programme_cycle_is_rejected(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        programme = await _programme(session)
        student = await _student(session, "Duplicate")
        session.add(
            Lead(
                student_id=student.id,
                programme_id=programme.id,
                admission_cycle="2026-fall",
            )
        )
        await session.commit()

    async with db_session_factory() as session:
        session.add(
            Lead(
                student_id=student.id,
                programme_id=programme.id,
                admission_cycle="2026-fall",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@requires_postgres
async def test_new_cycle_or_programme_creates_a_separate_lead(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        programme = await _programme(session)
        other_programme = await _programme(session)
        student = await _student(session, "Repeat")
        session.add_all(
            [
                Lead(
                    student_id=student.id,
                    programme_id=programme.id,
                    admission_cycle="2026-fall",
                ),
                Lead(
                    student_id=student.id,
                    programme_id=programme.id,
                    admission_cycle="2027-spring",
                ),
                Lead(
                    student_id=student.id,
                    programme_id=other_programme.id,
                    admission_cycle="2026-fall",
                ),
            ]
        )
        await session.commit()

    async with db_session_factory() as session:
        cycles = set(
            (
                await session.execute(
                    select(Lead.admission_cycle).where(Lead.student_id == student.id)
                )
            ).scalars()
        )
        count = len(
            (await session.execute(select(Lead).where(Lead.student_id == student.id)))
            .scalars()
            .all()
        )

    assert cycles == {"2026-fall", "2027-spring"}
    assert count == 3


@requires_postgres
async def test_new_lead_defaults_to_new_enquiry_and_keeps_the_raw_row(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    raw = {"Full Name": "Asha Rao", "Email": "asha@enrollio.dev", "Score": "85%"}

    async with db_session_factory() as session:
        programme = await _programme(session)
        student = await _student(session, "Defaults")
        lead = Lead(
            student_id=student.id,
            programme_id=programme.id,
            admission_cycle="2026-fall",
            raw_import_row=raw,
        )
        session.add(lead)
        await session.commit()
        lead_id = lead.id

    async with db_session_factory() as session:
        stored = await session.get(Lead, lead_id)

    assert stored is not None
    assert stored.lifecycle_status is LifecycleStatus.NEW_ENQUIRY
    assert stored.raw_import_row == raw
    assert stored.assigned_counsellor_id is None
