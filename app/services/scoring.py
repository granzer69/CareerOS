from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.schemas.evidence import EligibilityItem, RequirementMatch

RUBRIC_VERSION = "v1.0.0"

JOB_FIT_WEIGHTS: dict[str, float] = {
    "skill": 0.30,
    "experience": 0.25,
    "project": 0.20,
    "preferred": 0.10,
    "context": 0.15,
}

ALIGNMENT_WEIGHTS: dict[str, float] = {
    "relevance": 0.25,
    "clarity": 0.20,
    "evidence_strength": 0.20,
    "keyword_coverage": 0.15,
    "structure": 0.10,
    "consistency": 0.10,
}

READINESS_JOB_FIT = 0.60
READINESS_ALIGNMENT = 0.35
READINESS_COMPLETENESS = 0.05

STATE_VALUE: dict[str, float] = {
    "confirmed": 1.0,
    "partial": 0.5,
    "not_found": 0.0,
    "contradicted": 0.0,
}

_ACTION_VERBS = (
    "led",
    "built",
    "designed",
    "implemented",
    "developed",
    "created",
    "owned",
    "improved",
    "launched",
)
_SECTION_HINTS = {
    "Work Experience": ("experience", "employment", "work history"),
    "Skills": ("skills", "technologies"),
    "Education": ("education", "university", "bachelor", "master"),
    "Projects": ("projects", "portfolio"),
    "Summary": ("summary", "profile", "objective"),
}


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _bucket(match: RequirementMatch) -> str | None:
    if match.is_eligibility:
        return None
    if match.importance == "preferred":
        return "preferred"
    return match.category


def _weighted_mean(values: dict[str, float], weights: dict[str, float]) -> float:
    present = {key: weights[key] for key in values if key in weights}
    total = sum(present.values())
    if total <= 0:
        return 0.0
    return sum(values[key] * present[key] for key in present) / total


def job_fit_score(matches: list[RequirementMatch]) -> int:
    """Compute job-fit from evidence states. Unknown items are excluded, not failed."""
    buckets: dict[str, list[float]] = {key: [] for key in JOB_FIT_WEIGHTS}
    for match in matches:
        bucket = _bucket(match)
        if bucket is None or match.evidence_state == "unknown":
            continue
        buckets[bucket].append(STATE_VALUE[match.evidence_state])
    values = {
        key: (sum(scores) / len(scores)) * 100
        for key, scores in buckets.items()
        if scores
    }
    return _clamp(_weighted_mean(values, JOB_FIT_WEIGHTS))


def _alignment_components(matches: list[RequirementMatch], resume_text: str) -> dict[str, float]:
    lowered = resume_text.lower()
    substantive = [
        match
        for match in matches
        if not match.is_eligibility and match.evidence_state != "unknown"
    ]
    mandatory = [match for match in substantive if match.importance == "mandatory"]
    confirmed_or_partial = [
        match
        for match in mandatory
        if match.evidence_state in {"confirmed", "partial"}
    ]
    relevance = (
        (len(confirmed_or_partial) / len(mandatory)) * 100 if mandatory else 0.0
    )

    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    verb_lines = sum(1 for line in lines if any(verb in line.lower() for verb in _ACTION_VERBS))
    clarity = min(100.0, (verb_lines / max(len(lines), 1)) * 200)

    digits = len(re.findall(r"\d", resume_text))
    evidence_strength = min(100.0, digits * 5)

    confirmed = [match for match in mandatory if match.evidence_state == "confirmed"]
    keyword_coverage = (len(confirmed) / len(mandatory)) * 100 if mandatory else 0.0
    token_counts = Counter(re.findall(r"[a-z0-9+#.]{3,}", lowered))
    if token_counts and max(token_counts.values()) >= 8:
        keyword_coverage = min(keyword_coverage, 40.0)

    present_sections = sum(
        1
        for hints in _SECTION_HINTS.values()
        if any(hint in lowered for hint in hints)
    )
    structure = (present_sections / len(_SECTION_HINTS)) * 100

    contradicted = any(match.evidence_state == "contradicted" for match in matches)
    consistency = 40.0 if contradicted else 80.0

    return {
        "relevance": relevance,
        "clarity": clarity,
        "evidence_strength": evidence_strength,
        "keyword_coverage": keyword_coverage,
        "structure": structure,
        "consistency": consistency,
    }


def resume_alignment_score(matches: list[RequirementMatch], resume_text: str) -> tuple[int, int]:
    """Return (alignment score, terminology-coverage score used as ats_score)."""
    components = _alignment_components(matches, resume_text)
    alignment = _clamp(_weighted_mean(components, ALIGNMENT_WEIGHTS))
    return alignment, _clamp(components["keyword_coverage"])


def eligibility_items(matches: list[RequirementMatch]) -> list[EligibilityItem]:
    """Track eligibility constraints separately from the weighted score."""
    items: list[EligibilityItem] = []
    for match in matches:
        if not match.is_eligibility:
            continue
        if match.evidence_state == "confirmed":
            status = "confirmed_met"
            rationale = "The resume supports this stated requirement."
        elif match.evidence_state == "contradicted":
            status = "confirmed_not_met"
            rationale = "The resume conflicts with this stated requirement."
        else:
            status = "unknown"
            rationale = "Not enough information to determine eligibility."
        items.append(
            EligibilityItem(text=match.text, status=status, rationale=rationale)
        )
    if not items:
        items.append(
            EligibilityItem(
                text="No explicit eligibility constraints were extracted.",
                status="not_applicable",
                rationale="Completeness is omitted from readiness and remaining weights are renormalized.",
            )
        )
    return items


def application_completeness(items: list[EligibilityItem]) -> tuple[int | None, bool]:
    """
    Completeness is included only when checkable eligibility exists.

    Otherwise the caller must renormalize readiness instead of assuming 100.
    """
    checkable = [item for item in items if item.status != "not_applicable"]
    if not checkable:
        return None, False
    met = sum(1 for item in checkable if item.status == "confirmed_met")
    return _clamp((met / len(checkable)) * 100), True


def application_readiness_score(
    *,
    job_fit: int,
    resume_alignment: int,
    completeness: int | None,
    completeness_included: bool,
) -> int:
    """Composite readiness. Missing completeness renormalizes job-fit and alignment."""
    if completeness_included and completeness is not None:
        return _clamp(
            READINESS_JOB_FIT * job_fit
            + READINESS_ALIGNMENT * resume_alignment
            + READINESS_COMPLETENESS * completeness
        )
    total = READINESS_JOB_FIT + READINESS_ALIGNMENT
    return _clamp(
        (READINESS_JOB_FIT / total) * job_fit
        + (READINESS_ALIGNMENT / total) * resume_alignment
    )


def grade_from_score(score: int) -> str:
    """Map a 0-100 score onto a letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def estimated_level_from_resume(resume_text: str, modeled: str | None) -> str:
    """Prefer a schema-valid model hint; otherwise use a years heuristic."""
    if modeled in {"junior", "mid", "senior"}:
        return modeled
    years = [int(value) for value in re.findall(r"(\d+)\+?\s+years", resume_text.lower())]
    if years and max(years) >= 8:
        return "senior"
    if years and max(years) >= 3:
        return "mid"
    return "junior"


def presentation_fields(
    matches: list[RequirementMatch],
) -> tuple[list[str], list[str], list[str]]:
    """Derive strengths, weaknesses, and missing keywords from evidence states."""
    confirmed = [
        match.text for match in matches if match.evidence_state == "confirmed" and not match.is_eligibility
    ]
    missing = [
        match.text
        for match in matches
        if match.evidence_state == "not_found"
        and match.importance == "mandatory"
        and not match.is_eligibility
    ]
    strengths = (confirmed + ["Relevant experience is present in the resume"] * 3)[:3]
    weaknesses = (
        missing
        + ["Limited demonstrated coverage of the job description"] * 3
    )[:3]
    return strengths, weaknesses, missing[:12]


@dataclass(frozen=True)
class ScoredApplication:
    """Deterministic rubric output. Numeric scores never come from the model."""

    job_fit_score: int
    resume_alignment_score: int
    application_readiness_score: int
    ats_score: int
    grade: str
    estimated_level: str
    top_strengths: list[str]
    critical_weaknesses: list[str]
    keywords_missing: list[str]
    sections: list[dict[str, object]]
    requirement_matches: list[RequirementMatch]
    eligibility: list[EligibilityItem]
    blocked_by_requirement: bool
    completeness_included: bool
    rubric_version: str


def score_application(
    *,
    matches: list[RequirementMatch],
    resume_text: str,
    estimated_level_hint: str | None,
) -> ScoredApplication:
    """Compute versioned scores from evidence matches. The model never supplies these numbers."""
    job_fit = job_fit_score(matches)
    alignment, ats = resume_alignment_score(matches, resume_text)
    eligibility = eligibility_items(matches)
    completeness, included = application_completeness(eligibility)
    readiness = application_readiness_score(
        job_fit=job_fit,
        resume_alignment=alignment,
        completeness=completeness,
        completeness_included=included,
    )
    strengths, weaknesses, missing = presentation_fields(matches)
    blocked = any(item.status == "confirmed_not_met" for item in eligibility)
    return ScoredApplication(
        job_fit_score=job_fit,
        resume_alignment_score=alignment,
        application_readiness_score=readiness,
        ats_score=ats,
        grade=grade_from_score(readiness),
        estimated_level=estimated_level_from_resume(resume_text, estimated_level_hint),
        top_strengths=strengths,
        critical_weaknesses=weaknesses,
        keywords_missing=missing,
        sections=section_feedback(resume_text),
        requirement_matches=matches,
        eligibility=eligibility,
        blocked_by_requirement=blocked,
        completeness_included=included,
        rubric_version=RUBRIC_VERSION,
    )


def section_feedback(resume_text: str) -> list[dict[str, object]]:
    """Build the existing section contract from resume structure, not from LLM scores."""
    lowered = resume_text.lower()
    sections: list[dict[str, object]] = []
    for name, hints in _SECTION_HINTS.items():
        present = any(hint in lowered for hint in hints)
        sections.append(
            {
                "name": name,
                "score": 80 if present else 20,
                "status": "strong" if present else "missing",
                "feedback": (
                    "Section appears in the resume."
                    if present
                    else "Section is not clearly labeled in the supplied resume."
                ),
                "suggestions": [] if present else [f"Add a visible {name} section."],
            }
        )
    sections.append(
        {
            "name": "Formatting",
            "score": 70,
            "status": "needs_improvement",
            "feedback": "Formatting is scored from structure only in this rubric version.",
            "suggestions": ["Keep consistent bullets and section headings."],
        }
    )
    return sections
