"""Duplicate candidates for manual review.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_candidates",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_student_id", sa.Uuid(), nullable=True),
        sa.Column("conflicting_student_id", sa.Uuid(), nullable=True),
        sa.Column("import_job_id", sa.Uuid(), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column(
            "reason",
            sa.Enum(
                "name_only",
                "conflicting_contact",
                name="duplicate_match_reason",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "resolved",
                name="duplicate_candidate_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "resolution",
            sa.Enum(
                "merged",
                "kept_separate",
                "rejected",
                name="duplicate_resolution",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("resolved_by_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["candidate_student_id"],
            ["students.id"],
            name=op.f("fk_duplicate_candidates_candidate_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conflicting_student_id"],
            ["students.id"],
            name=op.f("fk_duplicate_candidates_conflicting_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_duplicate_candidates_import_job_id_import_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_id"],
            ["users.id"],
            name=op.f("fk_duplicate_candidates_resolved_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_duplicate_candidates_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_candidates")),
    )
    op.create_index(
        "ix_duplicate_candidates_status",
        "duplicate_candidates",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_candidates_student_id",
        "duplicate_candidates",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_candidates_import_job_id",
        "duplicate_candidates",
        ["import_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_duplicate_candidates_import_job_id", table_name="duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_student_id", table_name="duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_status", table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")
