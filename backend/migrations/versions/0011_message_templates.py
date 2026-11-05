"""Message templates: reusable templated messaging copy (M3.4).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_templates",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "email",
                "whatsapp",
                "sms",
                name="message_channel",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "transactional",
                "promotional",
                "scholarship",
                "fee",
                "admission_offer",
                "deadline_change",
                name="message_category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                name="template_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_templates")),
        sa.UniqueConstraint("name", "version", name="uq_message_templates_name_version"),
    )
    op.create_index(
        "ix_message_templates_channel_category_status",
        "message_templates",
        ["channel", "category", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_message_templates_channel_category_status", table_name="message_templates")
    op.drop_table("message_templates")
