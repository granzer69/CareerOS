from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ExperienceLevelEnum


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    target_role: Mapped[str] = mapped_column(String, nullable=False)
    experience_level: Mapped[ExperienceLevelEnum] = mapped_column(
        SAEnum(
            ExperienceLevelEnum,
            name="experience_level_enum",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

