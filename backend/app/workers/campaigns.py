"""Celery task that sends one campaign's recipient batch."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_engine
from app.services import campaigns as campaigns_service
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.campaigns.send_campaign_batch_task")  # type: ignore[untyped-decorator]
def send_campaign_batch_task(campaign_id: str) -> str:
    """Run the async campaign batch sender in the worker process."""
    return asyncio.run(_send(uuid.UUID(campaign_id)))


async def _send(campaign_id: uuid.UUID) -> str:
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await campaigns_service.send_campaign_batch(session_factory, settings, campaign_id)
        return "done"
    finally:
        await engine.dispose()
