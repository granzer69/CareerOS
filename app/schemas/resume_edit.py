from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.evidence import EligibilityItem, RequirementMatch

EditKind = Literal["supported_rewrite", "missing_qualification", "unsupported"]
EditStatus = Literal["pending", "accepted", "rejected"]


class ModelEditProposal(BaseModel):
    """One model-proposed span rewrite. Scores and invented facts are not accepted."""

    original_span: str = Field(..., min_length=1, max_length=1000)
    proposed_text: str = Field(..., min_length=1, max_length=1000)
    requirement_id: str | None = None
    rationale: str = Field(..., min_length=1, max_length=500)

    model_config = {"extra": "forbid"}


class ModelEditBatch(BaseModel):
    """Local-model edit payload. Numeric scores are forbidden."""

    proposals: list[ModelEditProposal] = Field(default_factory=list, max_length=20)

    model_config = {"extra": "forbid"}


class ResumeEditRead(BaseModel):
    """Reviewable edit suggestion. Original analysis resume_text is never mutated."""

    id: UUID
    analysis_id: UUID
    kind: EditKind
    status: EditStatus
    original_span: str | None = None
    proposed_text: str
    evidence_span: str | None = None
    requirement_id: str | None = None
    rationale: str
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class ResumeVersionSummary(BaseModel):
    """Owner-scoped list item for an accepted resume version."""

    id: UUID
    analysis_id: UUID
    version_number: int
    overall_score: int | None = None
    grade: str | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class ResumeVersionRead(BaseModel):
    """Accepted working copy with rubric scores recomputed from the same JD."""

    id: UUID
    analysis_id: UUID
    version_number: int
    resume_text: str
    applied_edit_ids: list[UUID] = Field(default_factory=list)
    overall_score: int | None = None
    grade: str | None = None
    ats_score: int | None = None
    estimated_level: str | None = None
    job_fit_score: int | None = None
    resume_alignment_score: int | None = None
    application_readiness_score: int | None = None
    rubric_version: str | None = None
    requirement_matches: list[RequirementMatch] = Field(default_factory=list)
    eligibility: list[EligibilityItem] = Field(default_factory=list)
    blocked_by_requirement: bool = False
    completeness_included: bool = False
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }
