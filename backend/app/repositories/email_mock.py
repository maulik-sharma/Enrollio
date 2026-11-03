"""Queries for messages captured by the mock email provider."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_email_message import MockEmailMessage


async def add(session: AsyncSession, message: MockEmailMessage) -> MockEmailMessage:
    """Stage a mock message; the caller owns the commit."""
    session.add(message)
    await session.flush()
    return message


async def get_by_provider_id(
    session: AsyncSession, provider_message_id: str
) -> MockEmailMessage | None:
    """Return the message with this provider id, if it exists."""
    return await session.scalar(
        select(MockEmailMessage).where(MockEmailMessage.provider_message_id == provider_message_id)
    )


async def list_for_address(session: AsyncSession, address: str) -> list[MockEmailMessage]:
    """Return messages sent to an address, oldest first."""
    result = await session.execute(
        select(MockEmailMessage)
        .where(MockEmailMessage.to_address == address)
        .order_by(MockEmailMessage.created_at)
    )
    return list(result.scalars())
