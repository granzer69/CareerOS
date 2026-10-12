from __future__ import annotations

import hashlib
import re

from app.schemas.evidence import EvidenceState, ModelRequirement, RequirementMatch
from app.services.edit_grounding import short_skills

_TOKEN_RE = re.compile(r"[a-z0-9+#.]{3,}")
_STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "you",
    "our",
    "will",
    "have",
    "has",
    "are",
    "ability",
    "strong",
    "using",
    "from",
    "this",
    "that",
    "required",
    "preferred",
    "experience",
    "minimum",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokens(text: str) -> list[str]:
    found = [
        token
        for token in _TOKEN_RE.findall(_normalize(text))
        if token not in _STOPWORDS
    ]
    for skill in sorted(short_skills(text)):
        if skill not in found:
            found.append(skill)
    return found


def _token_in_haystack(token: str, haystack: str) -> bool:
    """Require a word boundary for short skills so 'go' does not match 'going'."""
    if token in {"go", "r", "c", "c++", "c#"} or len(token) <= 2:
        return re.search(rf"(?<![a-z0-9+]){re.escape(token)}(?![a-z0-9+#])", haystack) is not None
    return token in haystack


def _negated(requirement: str, resume_text: str) -> bool:
    haystack = _normalize(resume_text)
    phrases = [_normalize(requirement), *_tokens(requirement)]
    for phrase in phrases:
        if len(phrase) < 2:
            continue
        patterns = (
            f"no {phrase}",
            f"not {phrase}",
            f"not a {phrase}",
            f"without {phrase}",
            f"no experience with {phrase}",
            f"no experience in {phrase}",
        )
        if any(pattern in haystack for pattern in patterns):
            return True
    return False


def _best_span(tokens: list[str], resume_text: str) -> str | None:
    haystack = _normalize(resume_text)
    for token in tokens:
        index = haystack.find(token)
        if index >= 0:
            start = max(0, index - 40)
            end = min(len(haystack), index + len(token) + 40)
            return haystack[start:end].strip()
    return None


def match_requirement(requirement: ModelRequirement, resume_text: str) -> RequirementMatch:
    """Map one requirement to resume evidence using lexical overlap only."""
    req_id = "req-" + hashlib.sha256(requirement.text.encode("utf-8")).hexdigest()[:10]
    if requirement.importance == "contextual" and requirement.category == "context":
        return RequirementMatch(
            id=req_id,
            text=requirement.text,
            category=requirement.category,
            importance=requirement.importance,
            is_eligibility=requirement.is_eligibility,
            evidence_state="unknown",
            evidence_span=None,
            rationale="Ambiguous or boilerplate JD language; not treated as a missing skill.",
        )

    tokens = _tokens(requirement.text)
    if not tokens:
        return RequirementMatch(
            id=req_id,
            text=requirement.text,
            category=requirement.category,
            importance=requirement.importance,
            is_eligibility=requirement.is_eligibility,
            evidence_state="unknown",
            evidence_span=None,
            rationale="Requirement text is too generic to verify from the resume.",
        )

    haystack = _normalize(resume_text)
    hits = [token for token in tokens if _token_in_haystack(token, haystack)]
    if _negated(requirement.text, resume_text):
        return RequirementMatch(
            id=req_id,
            text=requirement.text,
            category=requirement.category,
            importance=requirement.importance,
            is_eligibility=requirement.is_eligibility,
            evidence_state="contradicted",
            evidence_span=_best_span(tokens, resume_text),
            rationale="Resume language conflicts with this requirement.",
        )

    ratio = len(hits) / len(tokens)
    if ratio >= 0.7:
        state: EvidenceState = "confirmed"
        rationale = "Supporting phrasing is present in the supplied resume."
    elif hits:
        state = "partial"
        rationale = "Related terms appear, but the requirement is not fully established."
    else:
        state = "not_found"
        rationale = "Not demonstrated in the supplied evidence."

    return RequirementMatch(
        id=req_id,
        text=requirement.text,
        category=requirement.category,
        importance=requirement.importance,
        is_eligibility=requirement.is_eligibility,
        evidence_state=state,
        evidence_span=_best_span(hits, resume_text) if hits else None,
        rationale=rationale,
    )


def match_requirements(
    requirements: list[ModelRequirement],
    resume_text: str,
) -> list[RequirementMatch]:
    """Map every extracted requirement onto resume evidence."""
    return [match_requirement(item, resume_text) for item in requirements]
