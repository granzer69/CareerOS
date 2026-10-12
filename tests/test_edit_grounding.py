from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.resume_edit import ModelEditBatch, ModelEditProposal
from app.services.edit_grounding import (
    apply_span_replacement,
    classify_proposal,
    missing_qualification_proposals,
)
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Preferred: Kubernetes\n"
)
SAMPLE_RESUME = "Python engineer with FastAPI experience at Acme."


def _matches() -> list:
    return match_requirements(extract_requirements(SAMPLE_JD), SAMPLE_RESUME)


def test_supported_rewrite_uses_identifiable_resume_span() -> None:
    """A rewrite of an existing span that adds no new facts is supported."""
    classified = classify_proposal(
        ModelEditProposal(
            original_span="Python engineer with FastAPI experience at Acme.",
            proposed_text="Python and FastAPI engineer at Acme.",
            requirement_id=None,
            rationale="Emphasize FastAPI.",
        ),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "supported_rewrite"
    assert classified.evidence_span is not None
    rewritten = apply_span_replacement(
        resume_text=SAMPLE_RESUME,
        original_span=classified.original_span or "",
        proposed_text=classified.proposed_text,
    )
    assert "Python and FastAPI engineer at Acme." in rewritten
    assert SAMPLE_RESUME != rewritten


def test_fabricated_metrics_are_unsupported() -> None:
    """Numbers that do not appear in the resume cannot be proposed as facts."""
    classified = classify_proposal(
        ModelEditProposal(
            original_span="Python engineer with FastAPI experience at Acme.",
            proposed_text="Python engineer who improved latency by 40% at Acme.",
            requirement_id=None,
            rationale="Add impact.",
        ),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "40%" in classified.rationale


def test_unsupported_skills_are_flagged() -> None:
    """JD skills that are not in the resume cannot be written in as qualifications."""
    classified = classify_proposal(
        ModelEditProposal(
            original_span="Python engineer with FastAPI experience at Acme.",
            proposed_text="Python, FastAPI, and Kubernetes engineer at Acme.",
            requirement_id=None,
            rationale="Add Kubernetes.",
        ),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "kubernetes" in classified.rationale.lower()


def test_missing_evidence_is_a_qualification_flag() -> None:
    """Mandatory not_found requirements become missing-evidence flags, not rewrites."""
    missing = missing_qualification_proposals(_matches())
    assert missing
    assert all(item.kind == "missing_qualification" for item in missing)
    assert any("kubernetes" in (item.proposed_text.lower()) for item in missing)


def test_model_edit_schema_rejects_numeric_scores() -> None:
    """Edit JSON that includes invented scores is rejected by schema."""
    with pytest.raises(ValidationError):
        ModelEditBatch.model_validate(
            {
                "proposals": [
                    {
                        "original_span": SAMPLE_RESUME,
                        "proposed_text": "Python and FastAPI engineer at Acme.",
                        "requirement_id": None,
                        "rationale": "clarity",
                    }
                ],
                "overall_score": 99,
            }
        )


def test_apply_span_replacement_requires_identifiable_source() -> None:
    """Replacements fail closed when the source span is not in the resume."""
    with pytest.raises(ValueError):
        apply_span_replacement(
            resume_text=SAMPLE_RESUME,
            original_span="This sentence is not on the resume.",
            proposed_text="Invented bullet.",
        )
