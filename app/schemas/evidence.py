from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceState = Literal["confirmed", "partial", "not_found", "contradicted", "unknown"]
RequirementImportance = Literal["mandatory", "preferred", "contextual"]
RequirementCategory = Literal["skill", "experience", "project", "context"]
EligibilityStatus = Literal[
    "confirmed_met",
    "confirmed_not_met",
    "unknown",
    "not_applicable",
]


class RequirementMatch(BaseModel):
    """One JD requirement mapped to resume evidence."""

    id: str
    text: str
    category: RequirementCategory
    importance: RequirementImportance
    is_eligibility: bool = False
    evidence_state: EvidenceState
    evidence_span: str | None = None
    rationale: str

    model_config = {"extra": "forbid"}


class EligibilityItem(BaseModel):
    """A mandatory constraint tracked separately from weighted scores."""

    text: str
    status: EligibilityStatus
    rationale: str

    model_config = {"extra": "forbid"}


class ModelRequirement(BaseModel):
    """Structured requirement extracted by the local model. Scores are not accepted."""

    text: str = Field(..., min_length=3, max_length=500)
    importance: RequirementImportance
    category: RequirementCategory
    is_eligibility: bool = False

    model_config = {"extra": "forbid"}


class ModelExtraction(BaseModel):
    """Local-model extraction payload. Numeric scores are forbidden."""

    requirements: list[ModelRequirement] = Field(default_factory=list)
    estimated_level: Literal["junior", "mid", "senior"] | None = None

    model_config = {"extra": "forbid"}
