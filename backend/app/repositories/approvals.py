"""Approval item helpers (FR-15)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ApprovalStatus
from app.models.approval_item import ApprovalItem


async def get(session: AsyncSession, item_id: uuid.UUID) -> ApprovalItem | None:
    """Return an approval item by primary key."""
    return await session.scalar(select(ApprovalItem).where(ApprovalItem.id == item_id))


async def list_pending(
    session: AsyncSession,
    *,
    lead_id: uuid.UUID | None = None,
    item_type: str | None = None,
) -> list[ApprovalItem]:
    """Return pending items, oldest first, optionally scoped to a lead/type."""
    statement = select(ApprovalItem).where(ApprovalItem.status == ApprovalStatus.PENDING)
    if lead_id is not None:
        statement = statement.where(ApprovalItem.lead_id == lead_id)
    if item_type is not None:
        statement = statement.where(ApprovalItem.item_type == item_type)
    statement = statement.order_by(ApprovalItem.created_at, ApprovalItem.id)
    result = await session.execute(statement)
    return list(result.scalars())


async def latest_pending(
    session: AsyncSession,
    *,
    lead_id: uuid.UUID,
    item_type: str,
) -> ApprovalItem | None:
    """Return the newest pending item for a lead/type, if any."""
    return await session.scalar(
        select(ApprovalItem)
        .where(
            ApprovalItem.lead_id == lead_id,
            ApprovalItem.item_type == item_type,
            ApprovalItem.status == ApprovalStatus.PENDING,
        )
        .order_by(ApprovalItem.created_at.desc(), ApprovalItem.id.desc())
        .limit(1)
    )


async def create(
    session: AsyncSession,
    *,
    item_type: str,
    lead_id: uuid.UUID | None,
    payload: dict[str, Any],
    draft_content: str | None = None,
    citations: list[Any] | None = None,
) -> ApprovalItem:
    """Insert one pending approval item."""
    item = ApprovalItem(
        item_type=item_type,
        lead_id=lead_id,
        payload=payload,
        draft_content=draft_content,
        citations=citations,
        status=ApprovalStatus.PENDING,
    )
    session.add(item)
    await session.flush()
    return item
