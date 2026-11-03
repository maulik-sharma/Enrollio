"""Lead lookup helpers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.domain import LifecycleStatus
from app.models.lead import Lead
from app.models.student import Student


async def get(session: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    """Return a lead by primary key with display relationships loaded."""
    return await session.scalar(
        select(Lead)
        .options(
            selectinload(Lead.student),
            selectinload(Lead.programme),
            selectinload(Lead.campus),
            selectinload(Lead.source),
            selectinload(Lead.assigned_counsellor),
        )
        .where(Lead.id == lead_id)
    )


async def find_for_enquiry(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    programme_id: uuid.UUID | None,
    admission_cycle: str,
) -> Lead | None:
    """Find the lead for a student/programme/cycle tuple.

    PostgreSQL treats NULLs as distinct in unique constraints, so the
    application lookup handles the optional programme explicitly.
    """
    programme_condition = (
        Lead.programme_id.is_(None) if programme_id is None else Lead.programme_id == programme_id
    )
    return await session.scalar(
        select(Lead).where(
            Lead.student_id == student_id,
            programme_condition,
            Lead.admission_cycle == admission_cycle,
        )
    )


async def list_for_student(session: AsyncSession, student_id: uuid.UUID) -> list[Lead]:
    """Return every lead belonging to a student."""
    result = await session.execute(
        select(Lead).where(Lead.student_id == student_id).order_by(Lead.created_at, Lead.id)
    )
    return list(result.scalars())


async def list_page(
    session: AsyncSession,
    *,
    scoped_counsellor_id: uuid.UUID | None,
    search: str | None = None,
    lifecycle_status: LifecycleStatus | None = None,
    programme_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    campus_id: uuid.UUID | None = None,
    assigned_counsellor_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_field: Literal["created_at", "updated_at"] = "created_at",
    descending: bool = True,
    after: tuple[datetime, uuid.UUID] | None = None,
    limit: int = 25,
) -> list[Lead]:
    """Return a stable page of leads, scoped and filtered."""
    statement = select(Lead).options(
        selectinload(Lead.student),
        selectinload(Lead.programme),
        selectinload(Lead.campus),
        selectinload(Lead.source),
        selectinload(Lead.assigned_counsellor),
    )

    if scoped_counsellor_id is not None:
        statement = statement.where(Lead.assigned_counsellor_id == scoped_counsellor_id)
    if search is not None and search.strip():
        pattern = _like_pattern(search)
        statement = statement.join(Student, Student.id == Lead.student_id).where(
            or_(
                Student.first_name.ilike(pattern, escape="\\"),
                Student.last_name.ilike(pattern, escape="\\"),
                Student.email_normalised.ilike(pattern, escape="\\"),
                Student.phone_e164.ilike(pattern, escape="\\"),
                func.concat_ws(" ", Student.first_name, Student.last_name).ilike(
                    pattern, escape="\\"
                ),
            )
        )
    if lifecycle_status is not None:
        statement = statement.where(Lead.lifecycle_status == lifecycle_status)
    if programme_id is not None:
        statement = statement.where(Lead.programme_id == programme_id)
    if source_id is not None:
        statement = statement.where(Lead.source_id == source_id)
    if campus_id is not None:
        statement = statement.where(Lead.campus_id == campus_id)
    if assigned_counsellor_id is not None:
        statement = statement.where(Lead.assigned_counsellor_id == assigned_counsellor_id)
    if created_from is not None:
        statement = statement.where(Lead.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(Lead.created_at <= created_to)

    column = Lead.created_at if sort_field == "created_at" else Lead.updated_at
    if after is not None:
        cursor_value, cursor_id = after
        if descending:
            statement = statement.where(
                (column < cursor_value) | ((column == cursor_value) & (Lead.id < cursor_id))
            )
        else:
            statement = statement.where(
                (column > cursor_value) | ((column == cursor_value) & (Lead.id > cursor_id))
            )

    order = column.desc() if descending else column.asc()
    tie = Lead.id.desc() if descending else Lead.id.asc()
    result = await session.execute(statement.order_by(order, tie).limit(limit))
    return list(result.scalars())


def _like_pattern(value: str) -> str:
    """Build a contains pattern with LIKE metacharacters escaped."""
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
