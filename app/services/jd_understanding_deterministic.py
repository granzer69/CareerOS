from __future__ import annotations

import re

from app.schemas.jd_insights import JDUnderstanding
from app.services.jd_extraction import split_jd_units

_BULLET_START = re.compile(r"^[\s>*\-\u2022\u00b7\d]+")
_WORK_AUTH = re.compile(
    r"(authorized to work|work authorization|visa sponsorship|clearance)",
    re.IGNORECASE,
)
_GENERIC_OBJECTIVE = re.compile(
    r"^(team player|fast[- ]paced|detail[- ]oriented|self[- ]starter|go[- ]getter)\b",
    re.IGNORECASE,
)


def _first_paragraph(job_description: str) -> str:
    for raw_line in job_description.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        about = re.match(r"^about(?:\s+the\s+role)?\s*:\s*(.+)$", line, re.IGNORECASE)
        if about and len(about.group(1)) >= 30:
            return about.group(1)[:500]
    for block in re.split(r"\n\s*\n", job_description.strip()):
        line = " ".join(block.split())
        if len(line) >= 40 and not _BULLET_START.match(line):
            if "—" in line and len(line) < 80:
                continue
            return line[:500]
    return ""


_SECTION_ONLY = re.compile(
    r"^(responsibilities|requirements|nice to have|about|qualifications)\s*:?\s*$",
    re.IGNORECASE,
)


def _bullet_lines(job_description: str) -> list[str]:
    lines: list[str] = []
    for raw_line in job_description.splitlines():
        cleaned = " ".join(raw_line.split()).strip()
        if len(cleaned) < 12 or len(cleaned) > 220:
            continue
        if _SECTION_ONLY.match(cleaned):
            continue
        if _WORK_AUTH.search(cleaned):
            continue
        if not (_BULLET_START.match(cleaned) or re.match(r"^\d+[\).\]:]", cleaned)):
            continue
        text = re.sub(r"^[\s>*\-\u2022\u00b7]+", "", cleaned).strip()
        text = re.sub(r"^\d+[\).\]:]\s+", "", text)
        if len(text) >= 12 and not _GENERIC_OBJECTIVE.match(text):
            lines.append(text)
    if lines:
        return lines
    for unit in split_jd_units(job_description):
        cleaned = " ".join(unit.split()).strip()
        if len(cleaned) < 12 or len(cleaned) > 220:
            continue
        if _WORK_AUTH.search(cleaned) or _SECTION_ONLY.match(cleaned):
            continue
        if cleaned.lower().count("required:") and cleaned.lower().count("preferred:"):
            continue
        if not _GENERIC_OBJECTIVE.match(cleaned):
            lines.append(cleaned)
    return lines


def deterministic_jd_understanding(
    *,
    target_role: str,
    job_description: str,
) -> JDUnderstanding:
    """
    Build JD objectives from posted bullets when the local model is weak or unavailable.

    Objectives are copied from responsibility/requirement lines, not invented skills.
    """
    paragraph = _first_paragraph(job_description)
    bullets = _bullet_lines(job_description)
    objectives = bullets[:6]
    if not objectives and paragraph:
        objectives = [paragraph[:180]]

    role_summary = paragraph or (
        f"{target_role.strip()} role focused on the responsibilities and requirements in the posting."
    )
    success: list[str] = []
    for unit in split_jd_units(job_description):
        cleaned = " ".join(unit.split()).strip()
        if _WORK_AUTH.search(cleaned):
            success.append(cleaned[:220])

    level = "junior"
    if re.search(r"\b(senior|staff|principal|lead)\b", job_description, re.IGNORECASE):
        level = "senior"
    elif re.search(r"\b2\+\s*years|\b3\+\s*years|\bmid[- ]level\b", job_description, re.IGNORECASE):
        level = "mid"

    return JDUnderstanding(
        role_summary=role_summary[:1200],
        objectives=objectives if objectives else [role_summary[:180]],
        success_criteria=success,
        estimated_level=level,
    )


def merge_jd_understanding(
    modeled: JDUnderstanding,
    *,
    target_role: str,
    job_description: str,
) -> JDUnderstanding:
    """
    Combine model inference with deterministic bullets so objectives stay grounded in the JD.
    """
    baseline = deterministic_jd_understanding(
        target_role=target_role,
        job_description=job_description,
    )
    merged_objectives: list[str] = []
    seen: set[str] = set()
    for item in modeled.objectives + baseline.objectives:
        key = re.sub(r"\s+", " ", item.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        merged_objectives.append(item.strip())
    merged_objectives = merged_objectives[:8]

    summary = modeled.role_summary.strip()
    if len(summary) < 40:
        summary = baseline.role_summary

    success = list(dict.fromkeys(modeled.success_criteria + baseline.success_criteria))[:12]
    level = modeled.estimated_level or baseline.estimated_level

    return JDUnderstanding(
        role_summary=summary[:1200],
        objectives=merged_objectives,
        success_criteria=success,
        estimated_level=level,
    )
