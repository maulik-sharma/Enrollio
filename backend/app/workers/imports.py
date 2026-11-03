"""Celery task that processes an uploaded lead import."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine
from app.integrations.storage.factory import build_storage
from app.services import imports as imports_service
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.imports.process_import")  # type: ignore[untyped-decorator]
def process_import(job_id: str) -> str:
    """Run the async import service in the worker process."""
    return asyncio.run(_process(uuid.UUID(job_id)))


async def _process(job_id: uuid.UUID) -> str:
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = build_storage(settings)
    try:
        async with session_factory() as session:
            job = await imports_service.process_import_job(
                session,
                settings,
                storage,
                job_id,
            )
            return job.status.value if job is not None else "missing"
    finally:
        await engine.dispose()
