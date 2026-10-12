from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonColumn


class ResumeEdit(Base):
    __tablename__ = "resume_edits"
    __table_args__ = (
        Index("ix_resume_edits_analysis_user_created", "analysis_id", "user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    original_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("analysis_id", "version_number", name="uq_resume_versions_analysis_number"),
        Index("ix_resume_versions_analysis_user", "analysis_id", "user_id"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resume_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    applied_edit_ids: Mapped[list[str]] = mapped_column(
        JsonColumn,
        nullable=False,
        default=list,
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    job_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume_alignment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requirement_matches: Mapped[list[dict]] = mapped_column(
        JsonColumn,
        nullable=False,
        default=list,
    )
    eligibility: Mapped[list[dict]] = mapped_column(
        JsonColumn,
        nullable=False,
        default=list,
    )
    blocked_by_requirement: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    completeness_included: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
