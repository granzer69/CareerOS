from __future__ import annotations

import re

from app.schemas.evidence import ModelRequirement, RequirementCategory, RequirementImportance

_BULLET_RE = re.compile(r"^[\s>*\-\u2022\u00b7]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

_MANDATORY_MARKERS = (
    "required",
    "must have",
    "must be",
    "need to",
    "needs to",
    "minimum",
    "at least",
)
_PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "plus",
    "bonus",
    "a plus",
)
_ELIGIBILITY_MARKERS = (
    "work authorization",
    "authorized to work",
    "citizenship",
    "security clearance",
    "clearance",
    "professional license",
    "visa",
    "years of experience",
    "year of experience",
)
_BOILERPLATE_MARKERS = (
    "equal opportunity",
    "eeo",
    "we are an",
    "we're a",
    "about us",
    "our mission",
    "benefits include",
    "competitive salary",
    "fun team",
    "fast-paced",
    "culture",
)
_SKILL_MARKERS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "aws",
    "react",
    "fastapi",
    "django",
    "kubernetes",
    "docker",
    "postgres",
    "experience with",
    "proficient",
    "knowledge of",
)
_EXPERIENCE_MARKERS = (
    "years",
    "responsible for",
    "led ",
    "manage",
    "ownership",
    "stakeholder",
)
_PROJECT_MARKERS = ("project", "portfolio", "built ", "shipped")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def split_jd_units(job_description: str) -> list[str]:
    """Split a JD into bullet/line/sentence units for requirement extraction."""
    units: list[str] = []
    for raw_line in job_description.splitlines():
        line = _strip_bullet(raw_line)
        if not line:
            continue
        if len(line) > 180:
            units.extend(part.strip() for part in _SENTENCE_RE.split(line) if part.strip())
        else:
            units.append(line)
    if not units:
        collapsed = _normalize(job_description)
        if collapsed:
            units.append(collapsed)
    return units


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _importance(text: str) -> RequirementImportance:
    if _has_marker(text, _PREFERRED_MARKERS):
        return "preferred"
    if _has_marker(text, _MANDATORY_MARKERS):
        return "mandatory"
    return "mandatory"


def _category(text: str) -> RequirementCategory:
    if _has_marker(text, _PROJECT_MARKERS):
        return "project"
    if _has_marker(text, _EXPERIENCE_MARKERS):
        return "experience"
    if _has_marker(text, _SKILL_MARKERS):
        return "skill"
    return "context"


def _is_eligibility(text: str) -> bool:
    return _has_marker(text, _ELIGIBILITY_MARKERS)


def _is_boilerplate(text: str) -> bool:
    return _has_marker(text, _BOILERPLATE_MARKERS)


def extract_requirements(job_description: str) -> list[ModelRequirement]:
    """
    Deterministically extract JD requirements.

    Boilerplate/culture lines are kept as contextual so they can be scored as
    unknown rather than as missing skills.
    """
    requirements: list[ModelRequirement] = []
    seen: set[str] = set()
    for index, unit in enumerate(split_jd_units(job_description)):
        cleaned = _normalize(unit)
        if len(cleaned) < 8:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        if _is_boilerplate(cleaned):
            requirements.append(
                ModelRequirement(
                    text=cleaned[:500],
                    importance="contextual",
                    category="context",
                    is_eligibility=False,
                )
            )
            continue
        requirements.append(
            ModelRequirement(
                text=cleaned[:500],
                importance=_importance(cleaned),
                category=_category(cleaned),
                is_eligibility=_is_eligibility(cleaned),
            )
        )
        if index > 40:
            break
    return requirements


def derive_target_role(*, target_role: str, job_description: str) -> str:
    """Use the provided title, or the first JD line, as the stored target role."""
    trimmed = target_role.strip()
    if trimmed:
        return trimmed[:200]
    units = split_jd_units(job_description)
    if units:
        return units[0][:200]
    return "Unspecified role"


def merge_requirements(
    *,
    deterministic: list[ModelRequirement],
    modeled: list[ModelRequirement],
) -> list[ModelRequirement]:
    """Union deterministic and model requirements without duplicate phrasing."""
    merged = list(deterministic)
    seen = {item.text.lower() for item in merged}
    for item in modeled:
        key = item.text.lower()
        if key in seen:
            continue
        if any(key in existing or existing in key for existing in seen):
            continue
        seen.add(key)
        merged.append(item)
    return merged
