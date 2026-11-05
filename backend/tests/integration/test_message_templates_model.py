"""Integration tests for the `message_templates` storage (M3.4)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import MessageCategory, MessageChannel, TemplateStatus
from app.models.message_template import MessageTemplate
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]


def _template(**overrides: object) -> MessageTemplate:
    values: dict[str, object] = {
        "name": "Open house invite",
        "channel": MessageChannel.EMAIL,
        "category": MessageCategory.PROMOTIONAL,
        "subject": "Open house {{campus}}",
        "body": "Hi {{first_name}}, join us at {{campus}}.",
    }
    values.update(overrides)
    return MessageTemplate(**values)


async def test_template_defaults_and_round_trip(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(_template())
        await session.commit()

    async with db_session_factory() as session:
        row = await session.scalar(select(MessageTemplate))
        assert row is not None
        assert row.version == 1
        assert row.status is TemplateStatus.DRAFT
        assert row.channel is MessageChannel.EMAIL
        assert row.category is MessageCategory.PROMOTIONAL
        assert row.subject == "Open house {{campus}}"


async def test_same_name_new_version_is_allowed_but_duplicate_version_rejected(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(_template())
        session.add(_template(name="Open house invite", version=2))
        await session.flush()
        with pytest.raises(DBAPIError):
            session.add(_template(name="Open house invite", version=2))
            await session.flush()


async def test_database_check_constraints_reject_unknown_values(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import text

    async with db_session_factory() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text(
                    "INSERT INTO message_templates"
                    " (name, channel, category, subject, body, status)"
                    " VALUES ('bad', 'email', 'promotional', 's', 'b', 'rejected')"
                )
            )
        await session.rollback()

        with pytest.raises(DBAPIError):
            await session.execute(
                text(
                    "INSERT INTO message_templates"
                    " (name, channel, category, subject, body, status)"
                    " VALUES ('bad2', 'pigeon_post', 'promotional', 's', 'b', 'draft')"
                )
            )


async def test_two_templates_can_share_a_subject(
    clean_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        session.add(_template())
        session.add(_template(name="Open house reminder"))
        await session.commit()
        rows = list((await session.execute(select(MessageTemplate))).scalars())
        assert len(rows) == 2
        assert rows[0].id != rows[1].id
