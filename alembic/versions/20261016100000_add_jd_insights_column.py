"""Add jd_insights JSON column for multi-stage JD understanding."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261016100000"
down_revision = "20261012120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_analyses",
        sa.Column("jd_insights", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("resume_analyses", "jd_insights")
