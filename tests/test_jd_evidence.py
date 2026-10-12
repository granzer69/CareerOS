from __future__ import annotations

import hashlib

import pytest

from pydantic import ValidationError

from app.schemas.evidence import ModelExtraction, ModelRequirement
from app.services.evidence_matcher import match_requirement, match_requirements
from app.services.jd_extraction import extract_requirements, merge_requirements, split_jd_units


def test_empty_job_description_yields_no_requirements() -> None:
    """Whitespace-only JDs do not invent requirements."""
    assert split_jd_units("   \n") == []
    assert extract_requirements("   \n") == []
    assert extract_requirements("") == []


def test_boilerplate_is_unknown_not_missing_skill() -> None:
    """Culture/EEO lines are contextual unknown, not failed mandatory skills."""
    jd = (
        "We are an equal opportunity employer with a fun team culture.\n"
        "Required: Python\n"
    )
    requirements = extract_requirements(jd)
    matches = match_requirements(requirements, "Python engineer at Acme.")
    boilerplate = [item for item in matches if "equal opportunity" in item.text.lower()]
    python = [item for item in matches if "python" in item.text.lower() and item.category == "skill"]
    assert boilerplate
    assert all(item.evidence_state == "unknown" for item in boilerplate)
    assert all(item.importance == "contextual" for item in boilerplate)
    assert python
    assert python[0].evidence_state == "confirmed"


def test_requirement_ids_are_stable_sha256_prefixes() -> None:
    """Requirement ids are req- plus the first 10 hex chars of sha256(text)."""
    requirement = ModelRequirement(
        text="Required: Python",
        importance="mandatory",
        category="skill",
    )
    match = match_requirement(requirement, "Python engineer")
    expected = "req-" + hashlib.sha256(requirement.text.encode("utf-8")).hexdigest()[:10]
    assert match.id == expected
    assert match_requirement(requirement, "Unrelated resume").id == expected


def test_match_states_cover_confirmed_partial_not_found_and_contradicted() -> None:
    """Lexical overlap and negation map onto the four concrete evidence states."""
    python = ModelRequirement(text="Required: Python", importance="mandatory", category="skill")
    fastapi = ModelRequirement(text="Required: FastAPI and Docker", importance="mandatory", category="skill")
    kube = ModelRequirement(text="Required: Kubernetes", importance="mandatory", category="skill")
    auth = ModelRequirement(
        text="US work authorization required",
        importance="mandatory",
        category="experience",
        is_eligibility=True,
    )
    resume = (
        "Python and FastAPI engineer at Acme. "
        "no us work authorization required"
    )
    assert match_requirement(python, resume).evidence_state == "confirmed"
    assert match_requirement(fastapi, resume).evidence_state == "partial"
    assert match_requirement(kube, resume).evidence_state == "not_found"
    assert match_requirement(auth, resume).evidence_state == "contradicted"


def test_short_skills_go_r_cpp_are_confirmed() -> None:
    """Go, R, and C++ are not dropped by the 3+ character matcher tokenizer."""
    resume = "Python engineer at Acme. Used C++ and Go. Worked with R for reporting."
    for text in ("Required: Go", "Required: R", "Required: C++"):
        requirement = ModelRequirement(text=text, importance="mandatory", category="skill")
        assert match_requirement(requirement, resume).evidence_state == "confirmed"


def test_negated_skill_phrase_is_contradicted() -> None:
    """'No Kubernetes experience' contradicts a Kubernetes requirement."""
    requirement = ModelRequirement(text="Required: Kubernetes", importance="mandatory", category="skill")
    match = match_requirement(requirement, "Python engineer at Acme. No Kubernetes experience.")
    assert match.evidence_state == "contradicted"


def test_merge_adds_modeled_requirements_without_duplicate_phrasing() -> None:
    """Model requirements union with deterministic ones; near-duplicate phrasing is skipped."""
    deterministic = extract_requirements("Required: Python\nRequired: FastAPI\n")
    modeled = [
        ModelRequirement(text="Required: Python", importance="mandatory", category="skill"),
        ModelRequirement(text="Experience with PostgreSQL", importance="preferred", category="skill"),
    ]
    merged = merge_requirements(deterministic=deterministic, modeled=modeled)
    texts = [item.text.lower() for item in merged]
    assert texts.count("required: python") == 1
    assert any("postgresql" in text for text in texts)


def test_model_extraction_rejects_numeric_scores() -> None:
    """Extraction schema forbids overall_score and other invented metrics."""
    payload = {
        "requirements": [
            {
                "text": "Required: Python",
                "importance": "mandatory",
                "category": "skill",
                "is_eligibility": False,
            }
        ],
        "estimated_level": "mid",
        "overall_score": 72,
    }
    with pytest.raises(ValidationError):
        ModelExtraction.model_validate(payload)
