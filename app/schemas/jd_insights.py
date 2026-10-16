from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JDUnderstanding(BaseModel):
    """Structured reading of a job description before requirement scoring."""

    role_summary: str = Field(..., min_length=10, max_length=1200)
    objectives: list[str] = Field(..., min_length=1, max_length=8)
    success_criteria: list[str] = Field(default_factory=list, max_length=12)
    estimated_level: Literal["junior", "mid", "senior"] | None = None

    model_config = {"extra": "forbid"}


class JDInsightsRead(BaseModel):
    """Persisted JD understanding shown on analysis detail."""

    role_summary: str
    objectives: list[str]
    success_criteria: list[str] = Field(default_factory=list)
    evidence_method: Literal["semantic_model", "lexical_fallback"] = "semantic_model"

    model_config = {"extra": "forbid"}


class EvidenceMatchItem(BaseModel):
    """One requirement's semantic evidence judgment from the local model."""

    requirement_index: int = Field(..., ge=0)
    evidence_state: Literal["confirmed", "partial", "not_found", "contradicted", "unknown"]
    evidence_span: str | None = Field(default=None, max_length=500)
    rationale: str = Field(..., min_length=3, max_length=500)

    model_config = {"extra": "forbid"}


class EvidenceBatchResult(BaseModel):
    """Batch output for evidence matching."""

    matches: list[EvidenceMatchItem]

    model_config = {"extra": "forbid"}
