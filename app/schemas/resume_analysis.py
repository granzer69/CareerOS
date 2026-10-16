from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.evidence import EligibilityItem, RequirementMatch
from app.schemas.jd_insights import JDInsightsRead


class ResumeSectionSchema(BaseModel):
    """Schema for an individual resume section evaluation."""

    name: Literal[
        "Work Experience",
        "Skills",
        "Education",
        "Projects",
        "Summary",
        "Formatting",
    ] = Field(...)
    score: int = Field(..., ge=0, le=100)
    status: Literal["strong", "needs_improvement", "weak", "missing"] = Field(...)
    feedback: str = Field(...)
    suggestions: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ResumeAnalysisResult(BaseModel):
    """Legacy presentation fields still returned on analysis reads."""

    overall_score: int = Field(..., ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"] = Field(...)
    ats_score: int = Field(..., ge=0, le=100)
    estimated_level: Literal["junior", "mid", "senior"] = Field(...)
    top_strengths: list[str] = Field(..., min_length=3, max_length=3)
    critical_weaknesses: list[str] = Field(..., min_length=3, max_length=3)
    keywords_missing: list[str] = Field(default_factory=list)
    sections: list[ResumeSectionSchema] = Field(...)

    model_config = {"extra": "forbid"}


class ResumeAnalysisSummary(BaseModel):
    """Safe list item for the authenticated owner's analysis history."""

    id: UUID
    file_name: str
    target_role: str
    overall_score: int
    grade: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class ResumeAnalysisRead(BaseModel):
    """Full response returned to the client after analysis."""

    id: UUID
    session_id: UUID
    file_name: str
    target_role: str
    overall_score: int
    grade: str
    ats_score: int
    estimated_level: str
    top_strengths: list[str]
    critical_weaknesses: list[str]
    keywords_missing: list[str]
    sections: list[ResumeSectionSchema]
    created_at: datetime
    job_description: str | None = None
    job_fit_score: int | None = None
    resume_alignment_score: int | None = None
    application_readiness_score: int | None = None
    rubric_version: str | None = None
    requirement_matches: list[RequirementMatch] = Field(default_factory=list)
    eligibility: list[EligibilityItem] = Field(default_factory=list)
    blocked_by_requirement: bool = False
    completeness_included: bool = False
    jd_insights: JDInsightsRead | None = None

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }
