"""Lead import pipeline: jobs, mapping templates, row results, lead provenance.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_templates",
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
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
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_mapping_templates_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mapping_templates")),
        sa.UniqueConstraint("source_name", name="uq_mapping_templates_source_name"),
    )
    op.create_table(
        "import_jobs",
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "uploaded",
                "processing",
                "completed",
                "failed",
                name="import_job_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'uploaded'"),
            nullable=False,
        ),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("merged_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
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
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_import_jobs_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"], unique=False)
    op.create_index(
        "ix_import_jobs_uploaded_by_id", "import_jobs", ["uploaded_by_id"], unique=False
    )

    op.add_column(
        "students",
        sa.Column("academic_score", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column("students", sa.Column("graduation_year", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_students_academic_score_range"),
        "students",
        "academic_score IS NULL OR (academic_score >= 0 AND academic_score <= 100)",
    )
    op.create_check_constraint(
        op.f("ck_students_graduation_year_range"),
        "students",
        "graduation_year IS NULL OR (graduation_year >= 1900 AND graduation_year <= 2100)",
    )

    op.add_column("leads", sa.Column("import_job_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_leads_import_job_id_import_jobs"),
        "leads",
        "import_jobs",
        ["import_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leads_import_job_id", "leads", ["import_job_id"], unique=False)

    op.create_table(
        "import_row_results",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "merged",
                "rejected",
                "duplicate",
                name="import_row_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_row_results_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_import_row_results_lead_id_leads"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_import_row_results_student_id_students"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_row_results")),
        sa.UniqueConstraint("import_job_id", "row_number", name="uq_import_row_results_job_row"),
    )
    op.create_index(
        "ix_import_row_results_job_status",
        "import_row_results",
        ["import_job_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_import_row_results_job_status", table_name="import_row_results")
    op.drop_table("import_row_results")

    op.drop_index("ix_leads_import_job_id", table_name="leads")
    op.drop_constraint(
        op.f("fk_leads_import_job_id_import_jobs"),
        "leads",
        type_="foreignkey",
    )
    op.drop_column("leads", "import_job_id")

    op.drop_constraint(op.f("ck_students_graduation_year_range"), "students", type_="check")
    op.drop_constraint(op.f("ck_students_academic_score_range"), "students", type_="check")
    op.drop_column("students", "graduation_year")
    op.drop_column("students", "academic_score")

    op.drop_index("ix_import_jobs_uploaded_by_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_table("mapping_templates")
