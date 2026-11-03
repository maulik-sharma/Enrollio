"""Database captures for the mock email provider.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_email_messages",
        sa.Column(
            "direction",
            sa.Enum(
                "outbound",
                "inbound",
                name="email_direction",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("to_name", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'sent'"), nullable=False),
        sa.Column("in_reply_to", sa.String(length=255), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mock_email_messages")),
        sa.UniqueConstraint(
            "provider_message_id",
            name=op.f("uq_mock_email_messages_provider_message_id"),
        ),
    )
    op.create_index(
        "ix_mock_email_messages_direction",
        "mock_email_messages",
        ["direction"],
        unique=False,
    )
    op.create_index(
        "ix_mock_email_messages_in_reply_to",
        "mock_email_messages",
        ["in_reply_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mock_email_messages_in_reply_to", table_name="mock_email_messages")
    op.drop_index("ix_mock_email_messages_direction", table_name="mock_email_messages")
    op.drop_table("mock_email_messages")
