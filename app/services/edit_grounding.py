from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.evidence import RequirementMatch
from app.schemas.resume_edit import EditKind, ModelEditProposal

_TOKEN_RE = re.compile(r"[a-z0-9+#.]{3,}")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
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
    "supply",
    "evidence",
}


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for span matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def tokens(text: str) -> list[str]:
    """Lexical tokens used for grounding checks."""
    return [
        token
        for token in _TOKEN_RE.findall(normalize(text))
        if token not in _STOPWORDS
    ]


def numbers(text: str) -> set[str]:
    """Digit sequences (including percents) treated as factual metrics."""
    return {match.group(0).lower() for match in _NUMBER_RE.finditer(text)}


def find_span(resume_text: str, span: str) -> str | None:
    """Return the resume slice matching span, case-insensitive, or None."""
    if not span.strip():
        return None
    exact = resume_text.find(span)
    if exact >= 0:
        return resume_text[exact : exact + len(span)]
    lowered = resume_text.lower()
    needle = span.lower()
    index = lowered.find(needle)
    if index < 0:
        return None
    return resume_text[index : index + len(span)]


def apply_span_replacement(*, resume_text: str, original_span: str, proposed_text: str) -> str:
    """Replace one identifiable span. Raises ValueError if the span is missing."""
    found = find_span(resume_text, original_span)
    if found is None:
        raise ValueError("original_span is not present in the resume")
    index = resume_text.find(found)
    return resume_text[:index] + proposed_text + resume_text[index + len(found) :]


def _forbidden_tokens(matches: list[RequirementMatch], resume_text: str) -> set[str]:
    resume_tokens = set(tokens(resume_text))
    forbidden: set[str] = set()
    for match in matches:
        if match.evidence_state not in {"not_found", "contradicted"}:
            continue
        for token in tokens(match.text):
            if token not in resume_tokens:
                forbidden.add(token)
    return forbidden


def _match_by_id(matches: list[RequirementMatch], requirement_id: str | None) -> RequirementMatch | None:
    if not requirement_id:
        return None
    for match in matches:
        if match.id == requirement_id:
            return match
    return None


@dataclass(frozen=True)
class ClassifiedProposal:
    kind: EditKind
    original_span: str | None
    proposed_text: str
    evidence_span: str | None
    requirement_id: str | None
    rationale: str


def classify_proposal(
    proposal: ModelEditProposal,
    *,
    resume_text: str,
    matches: list[RequirementMatch],
) -> ClassifiedProposal:
    """
    Map a model proposal onto supported / missing / unsupported using resume evidence.

    The model never has the last word: fabricated metrics and JD-only skills are unsupported.
    """
    original = proposal.original_span.strip()
    proposed = proposal.proposed_text.strip()
    found = find_span(resume_text, original)
    extra_numbers = numbers(proposed) - numbers(resume_text)
    if extra_numbers:
        return ClassifiedProposal(
            kind="unsupported",
            original_span=original,
            proposed_text=proposed,
            evidence_span=found,
            requirement_id=proposal.requirement_id,
            rationale="Fabricated metric(s) are not present in the resume: "
            + ", ".join(sorted(extra_numbers)),
        )

    stolen = [token for token in tokens(proposed) if token in _forbidden_tokens(matches, resume_text)]
    if stolen:
        unique = ", ".join(sorted(set(stolen)))
        return ClassifiedProposal(
            kind="unsupported",
            original_span=original,
            proposed_text=proposed,
            evidence_span=found,
            requirement_id=proposal.requirement_id,
            rationale=f"Unsupported skill(s) are not demonstrated in the resume: {unique}",
        )

    linked = _match_by_id(matches, proposal.requirement_id)
    if linked is not None and linked.evidence_state == "not_found" and found is None:
        return ClassifiedProposal(
            kind="missing_qualification",
            original_span=None,
            proposed_text=proposed,
            evidence_span=None,
            requirement_id=linked.id,
            rationale="This qualification is not in the resume. The candidate must supply evidence.",
        )

    if found is None:
        return ClassifiedProposal(
            kind="unsupported",
            original_span=original,
            proposed_text=proposed,
            evidence_span=None,
            requirement_id=proposal.requirement_id,
            rationale="original_span is not identifiable in the supplied resume.",
        )

    return ClassifiedProposal(
        kind="supported_rewrite",
        original_span=found,
        proposed_text=proposed,
        evidence_span=found,
        requirement_id=proposal.requirement_id,
        rationale=proposal.rationale,
    )


def missing_qualification_proposals(matches: list[RequirementMatch]) -> list[ClassifiedProposal]:
    """Deterministic flags for mandatory requirements with no resume evidence."""
    proposals: list[ClassifiedProposal] = []
    seen: set[str] = set()
    for match in matches:
        if match.evidence_state != "not_found":
            continue
        if match.importance == "contextual":
            continue
        if match.id in seen:
            continue
        seen.add(match.id)
        proposals.append(
            ClassifiedProposal(
                kind="missing_qualification",
                original_span=None,
                proposed_text=f"Supply evidence for: {match.text}",
                evidence_span=None,
                requirement_id=match.id,
                rationale="Not demonstrated in the supplied resume. Do not add this claim without evidence.",
            )
        )
    return proposals[:20]
