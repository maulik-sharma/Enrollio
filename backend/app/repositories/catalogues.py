"""Catalogue lookups for programmes, campuses, and lead sources."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.lead_source import LeadSource
from app.models.programme import Programme


async def list_programmes(session: AsyncSession) -> list[Programme]:
    """Return active programmes in name order."""
    result = await session.execute(
        select(Programme).where(Programme.is_active.is_(True)).order_by(Programme.name)
    )
    return list(result.scalars())


async def list_campuses(session: AsyncSession) -> list[Campus]:
    """Return active campuses in name order."""
    result = await session.execute(
        select(Campus).where(Campus.is_active.is_(True)).order_by(Campus.name)
    )
    return list(result.scalars())


async def list_sources(session: AsyncSession) -> list[LeadSource]:
    """Return lead sources in name order."""
    result = await session.execute(select(LeadSource).order_by(LeadSource.name))
    return list(result.scalars())


async def get_programme(session: AsyncSession, value: str) -> Programme | None:
    """Match an active programme by case-insensitive name or code."""
    folded = value.casefold()
    return await session.scalar(
        select(Programme).where(
            Programme.is_active.is_(True),
            or_(
                func.lower(Programme.name) == folded,
                func.lower(Programme.code) == folded,
            ),
        )
    )


async def get_programme_by_id(session: AsyncSession, programme_id: uuid.UUID) -> Programme | None:
    """Return a programme by primary key."""
    return await session.get(Programme, programme_id)


async def get_campus_by_id(session: AsyncSession, campus_id: uuid.UUID) -> Campus | None:
    """Return a campus by primary key."""
    return await session.get(Campus, campus_id)


async def get_source_by_id(session: AsyncSession, source_id: uuid.UUID) -> LeadSource | None:
    """Return a lead source by primary key."""
    return await session.get(LeadSource, source_id)


async def get_campus(session: AsyncSession, value: str) -> Campus | None:
    """Match an active campus by case-insensitive name."""
    return await session.scalar(
        select(Campus).where(
            Campus.is_active.is_(True),
            func.lower(Campus.name) == value.casefold(),
        )
    )


async def get_source(session: AsyncSession, value: str) -> LeadSource | None:
    """Match a lead source by case-insensitive name."""
    return await session.scalar(
        select(LeadSource).where(func.lower(LeadSource.name) == value.casefold())
    )


async def get_or_create_source(session: AsyncSession, value: str) -> LeadSource:
    """Return the source or create it for a new import partner."""
    source = await get_source(session, value)
    if source is not None:
        return source

    source = LeadSource(name=value)
    session.add(source)
    await session.flush()
    return source
