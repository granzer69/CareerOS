from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    """Schema matching the exact JSON structure Claude must return."""

    overall_score: int = Field(..., ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"] = Field(...)
    ats_score: int = Field(..., ge=0, le=100)
    estimated_level: Literal["junior", "mid", "senior"] = Field(...)
    top_strengths: list[str] = Field(..., min_length=3, max_length=3)
    critical_weaknesses: list[str] = Field(..., min_length=3, max_length=3)
    keywords_missing: list[str] = Field(default_factory=list)
    sections: list[ResumeSectionSchema] = Field(...)

    model_config = {"extra": "forbid"}


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

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }
