from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261012120000"
down_revision: Union[str, None] = "20261012080000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=sa.text("''")),
    )

    op.create_table(
        "resume_edit_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_version_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_analyses.id"],
            name="fk_resume_edit_batches_analysis_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_resume_edit_batches_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["resume_versions.id"],
            name="fk_resume_edit_batches_source_version_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_resume_edit_batches_analysis_user_created",
        "resume_edit_batches",
        ["analysis_id", "user_id", "created_at"],
    )

    op.add_column(
        "resume_edits",
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "resume_edits",
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "resume_edits",
        sa.Column("source_version_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "resume_edits",
        sa.Column(
            "source_content_hash",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.add_column("resume_edits", sa.Column("span_start", sa.Integer(), nullable=True))
    op.add_column("resume_edits", sa.Column("span_end", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_resume_edits_batch_id",
        "resume_edits",
        "resume_edit_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_resume_edits_source_version_id",
        "resume_edits",
        "resume_versions",
        ["source_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_resume_edits_batch_id", "resume_edits", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_resume_edits_batch_id", table_name="resume_edits")
    op.drop_constraint("fk_resume_edits_source_version_id", "resume_edits", type_="foreignkey")
    op.drop_constraint("fk_resume_edits_batch_id", "resume_edits", type_="foreignkey")
    op.drop_column("resume_edits", "span_end")
    op.drop_column("resume_edits", "span_start")
    op.drop_column("resume_edits", "source_content_hash")
    op.drop_column("resume_edits", "source_version_number")
    op.drop_column("resume_edits", "source_version_id")
    op.drop_column("resume_edits", "batch_id")
    op.drop_index(
        "ix_resume_edit_batches_analysis_user_created",
        table_name="resume_edit_batches",
    )
    op.drop_table("resume_edit_batches")
    op.drop_column("resume_versions", "content_hash")
