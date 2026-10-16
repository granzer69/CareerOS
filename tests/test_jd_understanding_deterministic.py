"""Deterministic JD understanding from posting bullets."""

from app.services.jd_understanding_deterministic import (
    deterministic_jd_understanding,
    merge_jd_understanding,
)
from app.schemas.jd_insights import JDUnderstanding

SAMPLE = """
About: Build hiring tools for students.
Responsibilities:
- Ship Python/FastAPI services
- Mentor interns
Must be authorized to work in the US without sponsorship.
"""


def test_deterministic_objectives_include_responsibility_bullets() -> None:
    """Responsibility lines become objectives grounded in the JD."""
    result = deterministic_jd_understanding(
        target_role="Engineer",
        job_description=SAMPLE,
    )
    joined = " ".join(result.objectives).lower()
    assert "python" in joined
    assert "mentor" in joined
    assert any("authorized" in item.lower() for item in result.success_criteria)


def test_merge_adds_missing_bullets_from_jd() -> None:
    """Model objectives are enriched with deterministic bullets from the posting."""
    modeled = JDUnderstanding(
        role_summary="Short summary text.",
        objectives=["Work with the team"],
        success_criteria=[],
        estimated_level="mid",
    )
    merged = merge_jd_understanding(
        modeled,
        target_role="Engineer",
        job_description=SAMPLE,
    )
    joined = " ".join(merged.objectives).lower()
    assert "python" in joined
    assert len(merged.role_summary) > 10
