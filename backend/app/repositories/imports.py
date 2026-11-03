"""Import job, mapping-template, and row-result queries."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ImportRowStatus
from app.models.import_job import ImportJob, ImportRowResult, MappingTemplate


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> ImportJob | None:
    """Return one import job."""
    return await session.get(ImportJob, job_id)


async def list_jobs(session: AsyncSession, *, limit: int, offset: int) -> list[ImportJob]:
    """Return import history, newest first."""
    result = await session.execute(
        select(ImportJob).order_by(ImportJob.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars())


async def get_mapping_template(session: AsyncSession, source_name: str) -> MappingTemplate | None:
    """Return the saved mapping for a source name."""
    return await session.scalar(
        select(MappingTemplate).where(MappingTemplate.source_name == source_name)
    )


async def upsert_mapping_template(
    session: AsyncSession,
    *,
    source_name: str,
    mapping: dict[str, str],
    created_by_id: uuid.UUID | None,
) -> MappingTemplate:
    """Create or replace the reusable mapping for ``source_name``."""
    statement = pg_insert(MappingTemplate).values(
        source_name=source_name,
        mapping=mapping,
        created_by_id=created_by_id,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[MappingTemplate.source_name],
            set_={
                "mapping": statement.excluded.mapping,
                "created_by_id": statement.excluded.created_by_id,
                "updated_at": func.now(),
            },
        )
    )
    template = await get_mapping_template(session, source_name)
    if template is None:
        raise RuntimeError("Mapping template upsert did not return a row")
    return template


async def get_errors(session: AsyncSession, job_id: uuid.UUID) -> list[ImportRowResult]:
    """Return rejected rows ordered by their original row number."""
    result = await session.execute(
        select(ImportRowResult)
        .where(
            ImportRowResult.import_job_id == job_id,
            ImportRowResult.status == ImportRowStatus.REJECTED,
        )
        .order_by(ImportRowResult.row_number)
    )
    return list(result.scalars())
