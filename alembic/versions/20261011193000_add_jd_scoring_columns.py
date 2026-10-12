from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261011193000"
down_revision: Union[str, None] = "20261011180000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resume_analyses", sa.Column("job_description", sa.Text(), nullable=True))
    op.add_column("resume_analyses", sa.Column("job_fit_score", sa.Integer(), nullable=True))
    op.add_column(
        "resume_analyses",
        sa.Column("resume_alignment_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "resume_analyses",
        sa.Column("application_readiness_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "resume_analyses",
        sa.Column("rubric_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "resume_analyses",
        sa.Column(
            "requirement_matches",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "resume_analyses",
        sa.Column(
            "eligibility",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "resume_analyses",
        sa.Column(
            "blocked_by_requirement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "resume_analyses",
        sa.Column(
            "completeness_included",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("resume_analyses", "completeness_included")
    op.drop_column("resume_analyses", "blocked_by_requirement")
    op.drop_column("resume_analyses", "eligibility")
    op.drop_column("resume_analyses", "requirement_matches")
    op.drop_column("resume_analyses", "rubric_version")
    op.drop_column("resume_analyses", "application_readiness_score")
    op.drop_column("resume_analyses", "resume_alignment_score")
    op.drop_column("resume_analyses", "job_fit_score")
    op.drop_column("resume_analyses", "job_description")
