from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field

AnalysisJobStatus = Literal["pending", "running", "completed", "failed"]

from app.schemas.resume_analysis import ResumeAnalysisRead


class AnalysisJobRead(BaseModel):
    """Status of a background resume analysis. Poll until status is terminal."""

    id: UUID
    status: AnalysisJobStatus
    created_at: datetime
    updated_at: datetime
    analysis: ResumeAnalysisRead | None = None
    error_code: str | None = None
    error_detail: str | None = None

    model_config = {"extra": "forbid"}
