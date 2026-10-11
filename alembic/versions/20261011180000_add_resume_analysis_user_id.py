from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261011180000"
down_revision: Union[str, None] = "20260314220000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_analyses",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_resume_analyses_user_id",
        "resume_analyses",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_resume_analyses_user_id_created_at",
        "resume_analyses",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_analyses_user_id_created_at", table_name="resume_analyses")
    op.drop_constraint("fk_resume_analyses_user_id", "resume_analyses", type_="foreignkey")
    op.drop_column("resume_analyses", "user_id")
