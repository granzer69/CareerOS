from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceBucket(BaseModel):
    """Count of requirement matches in one evidence state."""

    state: str
    count: int = Field(..., ge=0)

    model_config = {"extra": "forbid"}


class ScorePoint(BaseModel):
    """One owned analysis, oldest-first for trend charts. Omits resume text."""

    id: UUID
    created_at: datetime
    file_name: str
    target_role: str
    overall_score: int | None = None
    job_fit_score: int | None = None
    resume_alignment_score: int | None = None
    application_readiness_score: int | None = None
    rubric_version: str | None = None
    blocked_by_requirement: bool = False

    model_config = {"extra": "forbid"}


class RoleBreakdown(BaseModel):
    """Evidence mix for one target_role in the caller's history."""

    target_role: str
    analysis_count: int = Field(..., ge=0)
    avg_readiness: float | None = None
    confirmed: int = Field(..., ge=0)
    not_found: int = Field(..., ge=0)
    contradicted: int = Field(..., ge=0)

    model_config = {"extra": "forbid"}


class TermCount(BaseModel):
    """A missing-terminology string and how often it appeared."""

    term: str
    count: int = Field(..., ge=1)

    model_config = {"extra": "forbid"}


class AnalyticsRead(BaseModel):
    """Owner-scoped analytics. Not a hiring probability or cross-user benchmark."""

    analysis_count: int = Field(..., ge=0)
    requirement_count: int = Field(..., ge=0)
    blocked_count: int = Field(..., ge=0)
    mandatory_gap_count: int = Field(..., ge=0)
    latest_created_at: datetime | None = None
    rubric_versions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceBucket]
    scores: list[ScorePoint]
    roles: list[RoleBreakdown]
    missing_terminology: list[TermCount] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
