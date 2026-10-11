from __future__ import annotations

from app.schemas.evidence import RequirementMatch
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements
from app.services.scoring import (
    RUBRIC_VERSION,
    application_readiness_score,
    grade_from_score,
    job_fit_score,
    resume_alignment_score,
    score_application,
)

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Preferred: Kubernetes\n"
)
SAMPLE_RESUME = "Python engineer with FastAPI experience at Acme."


def _match(
    *,
    text: str,
    state: str,
    category: str = "skill",
    importance: str = "mandatory",
    is_eligibility: bool = False,
) -> RequirementMatch:
    return RequirementMatch(
        id=f"req-{text}",
        text=text,
        category=category,  # type: ignore[arg-type]
        importance=importance,  # type: ignore[arg-type]
        is_eligibility=is_eligibility,
        evidence_state=state,  # type: ignore[arg-type]
        evidence_span=None,
        rationale="test",
    )


def test_job_fit_uses_confirmed_and_not_found_states() -> None:
    """Confirmed skills score 100; a missing preferred skill pulls job-fit below 100."""
    matches = [
        _match(text="Python", state="confirmed"),
        _match(text="FastAPI", state="confirmed"),
        _match(text="Kubernetes", state="not_found", importance="preferred"),
    ]
    assert job_fit_score(matches) == 75


def test_unknown_evidence_is_excluded_from_job_fit() -> None:
    """Unknown items are skipped rather than treated as failed coverage."""
    unknown_only = [_match(text="Culture fit", state="unknown", category="context", importance="contextual")]
    assert job_fit_score(unknown_only) == 0

    mixed = unknown_only + [_match(text="Python", state="confirmed")]
    assert job_fit_score(mixed) == 100


def test_completeness_omitted_renormalizes_readiness_weights() -> None:
    """When eligibility is not checkable, readiness uses 0.60/0.95 and 0.35/0.95."""
    omitted = application_readiness_score(
        job_fit=75,
        resume_alignment=48,
        completeness=None,
        completeness_included=False,
    )
    included_zero = application_readiness_score(
        job_fit=75,
        resume_alignment=48,
        completeness=0,
        completeness_included=True,
    )
    assert omitted == 65
    assert included_zero == 62


def test_grade_boundaries() -> None:
    """Letter grades follow the 90/80/70/60 cutoffs."""
    assert grade_from_score(90) == "A"
    assert grade_from_score(89) == "B"
    assert grade_from_score(80) == "B"
    assert grade_from_score(79) == "C"
    assert grade_from_score(70) == "C"
    assert grade_from_score(69) == "D"
    assert grade_from_score(60) == "D"
    assert grade_from_score(59) == "F"


def test_keyword_stuffing_caps_terminology_coverage() -> None:
    """Repeated tokens cap ats_score/keyword coverage at 40 even when requirements match."""
    stuffed = ("python " * 20) + "fastapi kubernetes"
    matches = [
        _match(text="Python", state="confirmed"),
        _match(text="FastAPI", state="confirmed"),
        _match(text="Kubernetes", state="confirmed"),
    ]
    _alignment, ats = resume_alignment_score(matches, stuffed)
    assert ats == 40


def test_eligibility_does_not_change_job_fit() -> None:
    """Eligibility blockers are tracked separately and do not enter job-fit weights."""
    skill = [_match(text="Python", state="confirmed")]
    with_eligibility = skill + [
        _match(
            text="US work authorization required",
            state="contradicted",
            category="experience",
            is_eligibility=True,
        )
    ]
    assert job_fit_score(skill) == job_fit_score(with_eligibility)
    scored = score_application(
        matches=with_eligibility,
        resume_text="Python engineer. no us work authorization required",
        estimated_level_hint=None,
    )
    assert scored.blocked_by_requirement is True
    assert scored.completeness_included is True
    assert scored.eligibility[0].status == "confirmed_not_met"


def test_sample_jd_resume_readiness_baseline() -> None:
    """Lock rubric v1.0.0 numbers for the canonical Python/FastAPI JD and resume."""
    matches = match_requirements(extract_requirements(SAMPLE_JD), SAMPLE_RESUME)
    scored = score_application(
        matches=matches,
        resume_text=SAMPLE_RESUME,
        estimated_level_hint="mid",
    )
    assert scored.rubric_version == RUBRIC_VERSION
    assert scored.job_fit_score == 75
    assert scored.resume_alignment_score == 50
    assert scored.ats_score == 100
    assert scored.application_readiness_score == 66
    assert scored.grade == "D"
    assert scored.estimated_level == "mid"
    assert scored.completeness_included is False
    assert scored.blocked_by_requirement is False


def test_empty_matches_score_zero_without_crashing() -> None:
    """An empty evidence list yields zero job-fit and a padded presentation contract."""
    scored = score_application(matches=[], resume_text="", estimated_level_hint=None)
    assert scored.job_fit_score == 0
    assert scored.resume_alignment_score == 8
    assert scored.application_readiness_score == 3
    assert len(scored.top_strengths) == 3
    assert len(scored.critical_weaknesses) == 3
    assert scored.eligibility[0].status == "not_applicable"
