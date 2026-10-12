from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.evidence import RequirementMatch
from app.schemas.resume_edit import ModelEditBatch, ModelEditProposal
from app.services.edit_grounding import (
    apply_span_at,
    classify_proposal,
    content_hash,
    locate_span,
    missing_qualification_proposals,
    resolve_span_conflicts,
)
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Required: Go\n"
    "Preferred: Kubernetes\n"
)
SAMPLE_RESUME = "Python engineer with FastAPI experience at Acme."
PARAPHRASE = "Python and FastAPI engineer at Acme."


def _matches() -> list:
    return match_requirements(extract_requirements(SAMPLE_JD), SAMPLE_RESUME)


def _proposal(original: str, proposed: str) -> ModelEditProposal:
    return ModelEditProposal(
        original_span=original,
        proposed_text=proposed,
        requirement_id=None,
        rationale="test",
    )


def test_supported_paraphrase_preserves_attested_facts() -> None:
    """A meaning-preserving rewrite of a unique span is supported."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, PARAPHRASE),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "supported_rewrite"
    assert classified.span_start == 0
    assert classified.span_end == len(SAMPLE_RESUME)
    rewritten = apply_span_at(
        resume_text=SAMPLE_RESUME,
        start=classified.span_start or 0,
        end=classified.span_end or 0,
        expected_span=classified.original_span or "",
        proposed_text=classified.proposed_text,
    )
    assert rewritten == PARAPHRASE


def test_invented_employer_is_unsupported() -> None:
    """Employers that are not on the resume cannot be classified as supported."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python engineer with FastAPI experience at Google."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "google" in classified.rationale.lower()


def test_invented_job_title_is_unsupported() -> None:
    """Title upgrades that are not on the resume are unsupported."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Senior Python engineer with FastAPI experience at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "senior" in classified.rationale.lower()


def test_invented_responsibility_is_unsupported() -> None:
    """New achievements or responsibilities are not silently treated as rewrites."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python engineer who processed payments at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "payment" in classified.rationale.lower()


def test_fabricated_metric_is_unsupported() -> None:
    """Numbers that do not appear in the resume cannot be proposed as facts."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python engineer who improved latency by 40% at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    assert "40%" in classified.rationale


def test_unsupported_short_skill_names() -> None:
    """Short skills such as Go, R, and C++ are not ignored by the tokenizer."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python, FastAPI, Go, R, and C++ engineer at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "unsupported"
    lowered = classified.rationale.lower()
    assert "go" in lowered
    assert "c++" in lowered or "r" in lowered


def test_ambiguous_intensifier_needs_evidence() -> None:
    """Unverifiable intensifiers are needs_evidence, never supported."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Expert Python engineer with FastAPI experience at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "needs_evidence"
    assert "expert" in classified.rationale.lower()


def test_missing_evidence_is_a_qualification_flag() -> None:
    """Not-found requirements become missing-evidence flags, not rewrites."""
    missing = missing_qualification_proposals(_matches())
    assert missing
    assert all(item.kind == "missing_qualification" for item in missing)
    texts = " ".join(item.proposed_text.lower() for item in missing)
    assert "kubernetes" in texts


def test_duplicate_and_overlapping_spans_are_conflicted() -> None:
    """A batch cannot apply two supported rewrites to the same or overlapping span."""
    first = classify_proposal(
        _proposal(SAMPLE_RESUME, PARAPHRASE),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    second = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python FastAPI engineer at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    resolved = resolve_span_conflicts([first, second])
    assert resolved[0].kind == "supported_rewrite"
    assert resolved[1].kind == "unsupported"
    assert "span" in resolved[1].rationale.lower()


def test_ambiguous_span_refuses_first_occurrence() -> None:
    """Repeated spans are not applied at the first match."""
    resume = "Python at Acme. Python at Acme."
    located = locate_span(resume, "Python at Acme.")
    assert located.status == "ambiguous"
    classified = classify_proposal(
        _proposal("Python at Acme.", "Python at Acme."),
        resume_text=resume,
        matches=[],
    )
    assert classified.kind == "needs_evidence"


def test_stale_offset_apply_fails() -> None:
    """Offset replacement fails closed when the bound slice no longer matches."""
    with pytest.raises(ValueError):
        apply_span_at(
            resume_text=PARAPHRASE,
            start=0,
            end=len(SAMPLE_RESUME),
            expected_span=SAMPLE_RESUME,
            proposed_text="x",
        )


def test_content_hash_changes_with_text() -> None:
    """Version binding uses a hash of the exact source snapshot."""
    assert content_hash(SAMPLE_RESUME) != content_hash(PARAPHRASE)


def test_sentence_final_employer_period_matches_attested_noun() -> None:
    """A trailing period on an attested employer is not treated as a new company."""
    resume = "Junior engineer at Globex from 2019. Built FastAPI services."
    classified = classify_proposal(
        _proposal("Junior engineer at Globex from 2019.", "Junior engineer at Globex."),
        resume_text=resume,
        matches=[],
    )
    assert classified.kind == "supported_rewrite"


def test_sentence_final_period_does_not_invent_tokens() -> None:
    """Moving a word away from a sentence-final period is still a supported paraphrase."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "Python engineer at Acme with FastAPI experience."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "supported_rewrite"


def test_as_function_word_is_not_an_invented_claim() -> None:
    """The function word 'as' does not make a meaning-preserving rewrite unsupported."""
    classified = classify_proposal(
        _proposal(SAMPLE_RESUME, "As a Python engineer with FastAPI experience at Acme."),
        resume_text=SAMPLE_RESUME,
        matches=_matches(),
    )
    assert classified.kind == "supported_rewrite"


def test_negated_skill_is_not_positive_evidence() -> None:
    """Tokens that appear only inside negated clauses cannot support a rewrite."""
    resume = "Python engineer at Acme. No Kubernetes experience. Not a Go developer."
    classified = classify_proposal(
        _proposal("Python engineer at Acme.", "Python engineer with Kubernetes experience at Acme."),
        resume_text=resume,
        matches=[],
    )
    assert classified.kind == "unsupported"


def test_unbound_missing_requirement_is_a_qualification_flag() -> None:
    """A not-found requirement with no unique span is missing_qualification, not a rewrite."""
    classified = classify_proposal(
        ModelEditProposal(
            original_span="Kubernetes production clusters",
            proposed_text="Kubernetes production clusters",
            requirement_id="req-k8s",
            rationale="test",
        ),
        resume_text=SAMPLE_RESUME,
        matches=[
            RequirementMatch(
                id="req-k8s",
                text="Kubernetes",
                category="skill",
                importance="preferred",
                evidence_state="not_found",
                rationale="Not demonstrated.",
            )
        ],
    )
    assert classified.kind == "missing_qualification"


def test_model_edit_schema_rejects_numeric_scores() -> None:
    """Edit JSON that includes invented scores is rejected by schema."""
    with pytest.raises(ValidationError):
        ModelEditBatch.model_validate(
            {
                "proposals": [
                    {
                        "original_span": SAMPLE_RESUME,
                        "proposed_text": PARAPHRASE,
                        "requirement_id": None,
                        "rationale": "clarity",
                    }
                ],
                "overall_score": 99,
            }
        )
