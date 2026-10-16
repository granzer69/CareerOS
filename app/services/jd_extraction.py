from __future__ import annotations

import re

from app.schemas.evidence import ModelRequirement, RequirementCategory, RequirementImportance

_BULLET_RE = re.compile(r"^[\s>*\-\u2022\u00b7]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBERED_RE = re.compile(r"^\s*(?:\d+[\).\]:]|[ivx]+[\).\]:])\s+", re.IGNORECASE)
_COLON_LIST_RE = re.compile(r"^([^:]{2,80}):\s*(.+)$")
_SEMICOLON_SPLIT_RE = re.compile(r"\s*;\s+")

_SECTION_RE = re.compile(
    r"^(?P<label>(?:required|requirements?|qualifications?|must[- ]haves?|minimum\s+qualifications?|"
    r"preferred|nice[- ]to[- ]have|bonus|optional|responsibilities|what you(?:'|')ll do|"
    r"what we(?:'|')re looking for|about the role|key skills|skills|technologies|"
    r"minimum|basic qualifications|preferred qualifications))[\s:]*$",
    re.IGNORECASE,
)

_MANDATORY_SECTION_LABELS = (
    "required",
    "requirement",
    "requirements",
    "qualification",
    "qualifications",
    "must-have",
    "must haves",
    "must have",
    "minimum",
    "minimum qualifications",
    "basic qualifications",
    "responsibilities",
    "what you'll do",
    "what you will do",
    "key skills",
    "skills",
    "technologies",
)
_PREFERRED_SECTION_LABELS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "optional",
    "preferred qualifications",
)

_MANDATORY_MARKERS = (
    "required",
    "must have",
    "must be",
    "need to",
    "needs to",
    "minimum",
    "at least",
    "mandatory",
)
_PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "plus",
    "bonus",
    "a plus",
    "ideally",
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
    "eligible to work",
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
    "stipend",
    "ppo ",
    "perks",
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
    "familiarity with",
    "competitive programming",
    "rest api",
    "agile",
    "git",
)
_EXPERIENCE_MARKERS = (
    "years",
    "responsible for",
    "led ",
    "manage",
    "ownership",
    "stakeholder",
    "intern",
    "co-op",
    "new grad",
)
_PROJECT_MARKERS = ("project", "portfolio", "built ", "shipped")

_MAX_REQUIREMENTS = 80
_MIN_UNIT_CHARS = 4


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _section_importance(label: str) -> RequirementImportance | None:
    """Map a section heading to default importance for lines under it."""
    lowered = _normalize(label).lower().rstrip(":")
    if any(lowered == item or lowered.startswith(item) for item in _PREFERRED_SECTION_LABELS):
        return "preferred"
    if any(lowered == item or lowered.startswith(item) for item in _MANDATORY_SECTION_LABELS):
        return "mandatory"
    return None


def _expand_colon_and_list_clauses(unit: str) -> list[str]:
    """
    Turn 'Skills: Python, Java, Docker' into separate requirement lines.

    Each part keeps the label prefix so evidence matching stays grounded in JD wording.
    """
    cleaned = _normalize(unit)
    match = _COLON_LIST_RE.match(cleaned)
    if not match:
        return [cleaned]
    label, tail = match.group(1).strip(), match.group(2).strip()
    if not tail:
        return [cleaned]
    if "," not in tail and ";" not in tail and " and " not in tail.lower():
        return [cleaned]
    parts = re.split(r",| and ", tail, flags=re.IGNORECASE)
    parts = [part.strip(" .") for part in parts if part.strip(" .")]
    if len(parts) <= 1:
        return [cleaned]
    return [f"{label}: {part}" for part in parts if len(part) >= 2]


def _expand_semicolon_clauses(unit: str) -> list[str]:
    """Split long lines on semicolons when each clause looks like its own requirement."""
    cleaned = _normalize(unit)
    if ";" not in cleaned:
        return [cleaned]
    parts = _SEMICOLON_SPLIT_RE.split(cleaned)
    if len(parts) <= 1:
        return [cleaned]
    return [part for part in parts if len(part) >= _MIN_UNIT_CHARS]


def split_jd_units(job_description: str) -> list[str]:
    """Split a JD into bullet/line/sentence units for requirement extraction."""
    units: list[str] = []
    for raw_line in job_description.splitlines():
        line = _strip_bullet(_NUMBERED_RE.sub("", raw_line))
        if not line:
            continue
        if len(line) > 220:
            units.extend(part.strip() for part in _SENTENCE_RE.split(line) if part.strip())
        else:
            units.append(line)
    if not units:
        collapsed = _normalize(job_description)
        if collapsed:
            units.append(collapsed)
    expanded: list[str] = []
    for unit in units:
        for semicolon_part in _expand_semicolon_clauses(unit):
            expanded.extend(_expand_colon_and_list_clauses(semicolon_part))
    return expanded


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _importance(text: str, section_default: RequirementImportance | None) -> RequirementImportance:
    if _has_marker(text, _PREFERRED_MARKERS):
        return "preferred"
    if _has_marker(text, _MANDATORY_MARKERS):
        return "mandatory"
    if section_default is not None:
        return section_default
    if _has_marker(text, _SKILL_MARKERS) or _has_marker(text, _EXPERIENCE_MARKERS):
        return "mandatory"
    return "contextual"


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

    Section headings (Requirements, Nice to have, etc.) set default importance for
    following lines. Colon/comma skill lists and numbered bullets are expanded so
    each scored row maps to JD text.
    """
    requirements: list[ModelRequirement] = []
    seen: set[str] = set()
    section_default: RequirementImportance | None = None

    for unit in split_jd_units(job_description):
        cleaned = _normalize(unit)
        if len(cleaned) < _MIN_UNIT_CHARS:
            continue

        section_match = _SECTION_RE.match(cleaned)
        if section_match and len(cleaned) < 64:
            section_default = _section_importance(section_match.group("label"))
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
                importance=_importance(cleaned, section_default),
                category=_category(cleaned),
                is_eligibility=_is_eligibility(cleaned),
            )
        )
        if len(requirements) >= _MAX_REQUIREMENTS:
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
    """Union deterministic and model requirements; deterministic rows are authoritative."""
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
