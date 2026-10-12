from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261012080000"
down_revision: Union[str, None] = "20261011193000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_edits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("original_span", sa.Text(), nullable=True),
        sa.Column("proposed_text", sa.Text(), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=True),
        sa.Column("requirement_id", sa.String(length=64), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_analyses.id"],
            name="fk_resume_edits_analysis_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_resume_edits_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_resume_edits_analysis_user_created",
        "resume_edits",
        ["analysis_id", "user_id", "created_at"],
    )

    op.create_table(
        "resume_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column(
            "applied_edit_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=2), nullable=True),
        sa.Column("ats_score", sa.Integer(), nullable=True),
        sa.Column("estimated_level", sa.String(length=10), nullable=True),
        sa.Column("job_fit_score", sa.Integer(), nullable=True),
        sa.Column("resume_alignment_score", sa.Integer(), nullable=True),
        sa.Column("application_readiness_score", sa.Integer(), nullable=True),
        sa.Column("rubric_version", sa.String(length=32), nullable=True),
        sa.Column(
            "requirement_matches",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "eligibility",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "blocked_by_requirement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "completeness_included",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_analyses.id"],
            name="fk_resume_versions_analysis_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_resume_versions_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "analysis_id",
            "version_number",
            name="uq_resume_versions_analysis_number",
        ),
    )
    op.create_index(
        "ix_resume_versions_analysis_user",
        "resume_versions",
        ["analysis_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_versions_analysis_user", table_name="resume_versions")
    op.drop_table("resume_versions")
    op.drop_index("ix_resume_edits_analysis_user_created", table_name="resume_edits")
    op.drop_table("resume_edits")
