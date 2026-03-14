from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonColumn


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        unique=True,
        default=uuid4,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(2), nullable=False)
    ats_score: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_level: Mapped[str] = mapped_column(String(10), nullable=False)
    top_strengths: Mapped[list[str]] = mapped_column(JsonColumn, nullable=False)
    critical_weaknesses: Mapped[list[str]] = mapped_column(JsonColumn, nullable=False)
    keywords_missing: Mapped[list[str]] = mapped_column(JsonColumn, nullable=False)
    sections: Mapped[list[dict]] = mapped_column(JsonColumn, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
