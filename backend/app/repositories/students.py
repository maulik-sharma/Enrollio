"""Student identity lookups used by deduplication and import."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student


async def get_by_email(session: AsyncSession, email: str) -> Student | None:
    """Return the student with the normalised email, or None."""
    return await session.scalar(select(Student).where(Student.email_normalised == email))


async def get_by_phone(session: AsyncSession, phone: str) -> Student | None:
    """Return the student with the E.164 phone number, or None."""
    return await session.scalar(select(Student).where(Student.phone_e164 == phone))


async def get(session: AsyncSession, student_id: uuid.UUID) -> Student | None:
    """Return a student by primary key."""
    return await session.get(Student, student_id)


async def find_by_name(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
) -> Student | None:
    """Return the oldest student with the same case-insensitive name."""
    return await session.scalar(
        select(Student)
        .where(
            func.lower(Student.first_name) == first_name.lower(),
            func.lower(Student.last_name) == last_name.lower(),
        )
        .order_by(Student.created_at, Student.id)
        .limit(1)
    )
