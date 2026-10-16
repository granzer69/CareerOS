"""Tests for multi-stage JD understanding and semantic evidence matching."""

import json

import pytest

from app.ai.jd_pipeline import (
    match_requirements_hybrid,
    match_requirements_with_model,
    understand_jd_with_model,
)
from app.schemas.evidence import ModelRequirement
from app.schemas.jd_insights import JDUnderstanding


class _StubAdapter:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        self.calls += 1
        if not self._responses:
            raise RuntimeError("no stub response")
        return self._responses.pop(0)


SAMPLE_JD = """
Software Engineer Intern
Required: Python, REST APIs, teamwork.
Preferred: React experience.
"""

SAMPLE_RESUME = "Built Python REST services for campus events. React dashboard for 2k users."


@pytest.mark.asyncio
async def test_understand_jd_parses_objectives() -> None:
    """JD understanding stage returns structured objectives JSON."""
    payload = {
        "role_summary": "Intern builds backend APIs for student products.",
        "objectives": ["Ship Python services", "Collaborate with product"],
        "success_criteria": ["Deliver REST endpoints"],
        "estimated_level": "junior",
    }
    adapter = _StubAdapter([json.dumps(payload)])
    result = await understand_jd_with_model(
        target_role="Intern",
        job_description=SAMPLE_JD,
        adapter=adapter,
    )
    assert len(result.objectives) >= 2
    assert "Ship Python services" in result.objectives
    assert result.estimated_level == "junior"


@pytest.mark.asyncio
async def test_semantic_match_uses_model_states() -> None:
    """Evidence stage maps model judgments onto requirements."""
    understanding = JDUnderstanding(
        role_summary="Backend intern role.",
        objectives=["Build APIs"],
        success_criteria=[],
        estimated_level="junior",
    )
    requirements = [
        ModelRequirement(
            text="Python",
            importance="mandatory",
            category="skill",
            is_eligibility=False,
        ),
        ModelRequirement(
            text="React experience",
            importance="preferred",
            category="skill",
            is_eligibility=False,
        ),
    ]
    evidence_payload = {
        "matches": [
            {
                "requirement_index": 0,
                "evidence_state": "confirmed",
                "evidence_span": "python rest services",
                "rationale": "Resume describes Python API work.",
            },
            {
                "requirement_index": 1,
                "evidence_state": "confirmed",
                "evidence_span": "react dashboard",
                "rationale": "Resume lists a React dashboard project.",
            },
        ]
    }
    adapter = _StubAdapter([json.dumps(evidence_payload)])
    matches = await match_requirements_with_model(
        requirements=requirements,
        resume_text=SAMPLE_RESUME,
        job_description=SAMPLE_JD,
        understanding=understanding,
        adapter=adapter,
    )
    assert matches[0].evidence_state == "confirmed"
    assert matches[1].evidence_state == "confirmed"
    assert "react" in (matches[1].evidence_span or "").lower()


@pytest.mark.asyncio
async def test_hybrid_falls_back_without_understanding() -> None:
    """Without JD understanding, hybrid matching stays lexical."""
    requirements = [
        ModelRequirement(
            text="Python",
            importance="mandatory",
            category="skill",
            is_eligibility=False,
        ),
    ]
    matches, method = await match_requirements_hybrid(
        requirements=requirements,
        resume_text=SAMPLE_RESUME,
        job_description=SAMPLE_JD,
        understanding=None,
    )
    assert method == "lexical_fallback"
    assert matches[0].evidence_state == "confirmed"
