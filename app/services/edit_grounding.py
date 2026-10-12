from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from app.schemas.evidence import RequirementMatch
from app.schemas.resume_edit import EditKind, ModelEditProposal

SpanStatus = Literal["missing", "ambiguous", "unique"]

_TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?(?:\s*%|\s*k\b|\s*m\b|\s*b\b)?", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_NEGATED_CLAUSE_RE = re.compile(
    r"(?i)\b(?:no|not a|not an|without|never|not)\b[^.!?\n]*"
)
_SHORT_SKILL_RE = re.compile(
    r"(?i)(?<![a-z0-9+])(c\+\+|c#|\.net|k8s|aws|gcp|sql|golang|(?<![a-z])go(?![a-z])|(?<![a-z])r(?![a-z])|(?<![a-z])c(?![a-z+#]))(?![a-z0-9+#])"
)
_PROPER_NOUN_RE = re.compile(r"\b(?:at|from|for|with)\s+([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*)")
_CAPITALIZED_RE = re.compile(r"\b[A-Z][A-Za-z0-9&.\-]{1,}\b")

_GLUE = {
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "is",
    "to",
    "of",
    "in",
    "on",
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
    "was",
    "were",
    "ability",
    "strong",
    "using",
    "used",
    "use",
    "from",
    "this",
    "that",
    "who",
    "via",
    "into",
    "onto",
    "over",
    "across",
    "including",
    "include",
    "based",
    "role",
    "team",
    "work",
    "working",
    "worked",
    "plus",
    "also",
    "both",
    "their",
    "its",
    "his",
    "her",
    "application",
    "applications",
    "system",
    "systems",
    "service",
    "services",
    "project",
    "projects",
    "software",
    "technical",
    "professional",
    "summary",
    "profile",
    "position",
    "required",
    "preferred",
    "experience",
    "minimum",
    "supply",
    "evidence",
    "candidate",
}

_TITLE_TOKENS = {
    "senior",
    "junior",
    "staff",
    "principal",
    "director",
    "manager",
    "intern",
    "lead",
    "head",
    "chief",
    "founder",
    "vp",
    "vice",
    "president",
    "architect",
}

_INTENSIFIERS = {
    "expert",
    "expertise",
    "native",
    "fluent",
    "exceptional",
    "outstanding",
    "extensive",
    "proven",
    "world-class",
    "worldclass",
    "unmatched",
    "ninja",
    "guru",
    "10x",
    "seasoned",
    "accomplished",
}

_OWNERSHIP_VERBS = {
    "owned",
    "led",
    "managed",
    "architected",
    "founded",
    "directed",
    "spearheaded",
    "pioneered",
}

_MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}

_MIN_SPAN_LENGTH = 8


def content_hash(text: str) -> str:
    """Stable SHA-256 of resume text used to bind edits to a source version."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for comparison."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _strip_token_punctuation(token: str) -> str:
    """Drop sentence-final dots so 'Acme.' and 'Acme' attest the same token.

    Leading-dot skills such as .net are preserved. Internal dots (node.js) stay.
    """
    if token.startswith("."):
        return token
    return token.strip(".")


def tokens(text: str) -> list[str]:
    """Lexical tokens, including 2-character tokens needed for short skills."""
    found: list[str] = []
    for raw in _TOKEN_RE.findall(normalize(text)):
        token = _strip_token_punctuation(raw)
        if len(token) >= 2 and token not in _GLUE:
            found.append(token)
    return found


def positive_evidence_text(resume_text: str) -> str:
    """Remove negated clauses so their tokens are not treated as positive evidence."""
    return _NEGATED_CLAUSE_RE.sub(" ", resume_text)


def numbers(text: str) -> set[str]:
    """Digit sequences, percents, and abbreviated magnitudes treated as metrics."""
    found: set[str] = set()
    for match in _NUMBER_RE.finditer(text):
        found.add(re.sub(r"\s+", "", match.group(0).lower()))
    return found


def short_skills(text: str) -> set[str]:
    """Extract short technical skills that a 3+ char tokenizer would miss."""
    found: set[str] = set()
    for match in _SHORT_SKILL_RE.finditer(text):
        found.add(match.group(1).lower())
    lowered = f" {normalize(text)} "
    for skill in ("c++", "c#", ".net", "go", "golang", "k8s", "aws", "gcp", "sql"):
        if f" {skill} " in lowered or lowered.strip() == skill:
            found.add(skill)
    if re.search(r"(?<![a-z])r(?![a-z])", normalize(text)):
        found.add("r")
    if re.search(r"(?<![a-z])c(?![a-z+#])", normalize(text)):
        found.add("c")
    return found


def _normalize_noun(text: str) -> str:
    """Lowercase a proper noun and drop sentence-final periods."""
    return normalize(text).strip(".")


def _proper_nouns(text: str) -> set[str]:
    found: set[str] = set()
    for match in _PROPER_NOUN_RE.finditer(text):
        noun = _normalize_noun(match.group(1))
        if noun:
            found.add(noun)
    words = text.split()
    for index, word in enumerate(words):
        if index == 0:
            continue
        cleaned = re.sub(r"[^A-Za-z0-9&.+\-#]", "", word).strip(".")
        if _CAPITALIZED_RE.fullmatch(cleaned) and _normalize_noun(cleaned) not in _GLUE:
            found.add(_normalize_noun(cleaned))
    return found


def _title_tokens(text: str) -> set[str]:
    return {token for token in tokens(text) if token in _TITLE_TOKENS}


def _months(text: str) -> set[str]:
    return {token for token in tokens(text) if token in _MONTHS}


def _years(text: str) -> set[str]:
    return {match.group(0) for match in _YEAR_RE.finditer(text)}


def _intensifiers(text: str) -> set[str]:
    lowered = normalize(text)
    return {word for word in _INTENSIFIERS if word in lowered.split() or word in lowered}


def _ownership_verbs(text: str) -> set[str]:
    return {token for token in tokens(text) if token in _OWNERSHIP_VERBS}


@dataclass(frozen=True)
class SpanLocation:
    status: SpanStatus
    start: int | None = None
    end: int | None = None
    exact: str | None = None


def _find_all(haystack: str, needle: str) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return hits
        hits.append(index)
        start = index + 1


def locate_span(resume_text: str, span: str) -> SpanLocation:
    """Locate span in resume text. Ambiguous if more than one occurrence."""
    stripped = span.strip()
    if not stripped:
        return SpanLocation(status="missing")
    exact_hits = _find_all(resume_text, stripped)
    if len(exact_hits) == 1:
        start = exact_hits[0]
        return SpanLocation(
            status="unique",
            start=start,
            end=start + len(stripped),
            exact=resume_text[start : start + len(stripped)],
        )
    if len(exact_hits) > 1:
        return SpanLocation(status="ambiguous")
    lowered_hits = _find_all(resume_text.lower(), stripped.lower())
    if len(lowered_hits) == 1:
        start = lowered_hits[0]
        exact = resume_text[start : start + len(stripped)]
        return SpanLocation(status="unique", start=start, end=start + len(stripped), exact=exact)
    if len(lowered_hits) > 1:
        return SpanLocation(status="ambiguous")
    return SpanLocation(status="missing")


def ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    """True if two half-open [start, end) ranges overlap."""
    return left[0] < right[1] and right[0] < left[1]


def apply_span_at(
    *,
    resume_text: str,
    start: int,
    end: int,
    expected_span: str,
    proposed_text: str,
) -> str:
    """Replace exactly the bound [start, end) slice. Raises ValueError if stale or ambiguous."""
    if start < 0 or end > len(resume_text) or start >= end:
        raise ValueError("span offsets are not valid")
    actual = resume_text[start:end]
    if actual != expected_span:
        raise ValueError("span no longer matches the bound source version")
    return resume_text[:start] + proposed_text + resume_text[end:]


@dataclass(frozen=True)
class ClassifiedProposal:
    kind: EditKind
    original_span: str | None
    proposed_text: str
    evidence_span: str | None
    requirement_id: str | None
    rationale: str
    span_start: int | None = None
    span_end: int | None = None


def _unsupported(
    *,
    original: str | None,
    proposed: str,
    found: str | None,
    requirement_id: str | None,
    rationale: str,
    start: int | None = None,
    end: int | None = None,
) -> ClassifiedProposal:
    return ClassifiedProposal(
        kind="unsupported",
        original_span=original,
        proposed_text=proposed,
        evidence_span=found,
        requirement_id=requirement_id,
        rationale=rationale,
        span_start=start,
        span_end=end,
    )


def _needs_evidence(
    *,
    original: str | None,
    proposed: str,
    found: str | None,
    requirement_id: str | None,
    rationale: str,
) -> ClassifiedProposal:
    return ClassifiedProposal(
        kind="needs_evidence",
        original_span=original,
        proposed_text=proposed,
        evidence_span=found,
        requirement_id=requirement_id,
        rationale=rationale,
    )


def classify_proposal(
    proposal: ModelEditProposal,
    *,
    resume_text: str,
    matches: list[RequirementMatch],
) -> ClassifiedProposal:
    """
    Classify a model proposal using deterministic evidence checks.

    The model never assigns kind. Unverifiable claims are needs_evidence or unsupported.
    """
    original = proposal.original_span.strip()
    proposed = proposal.proposed_text.strip()
    location = locate_span(resume_text, original)
    found = location.exact
    attested = positive_evidence_text(resume_text)
    resume_norm = normalize(attested)
    resume_token_set = set(tokens(attested))
    resume_skills = short_skills(attested)
    resume_nouns = _proper_nouns(attested) | {normalize(part) for part in attested.split() if part}
    resume_titles = _title_tokens(attested)
    resume_months = _months(attested)
    resume_years = _years(attested)
    resume_numbers = numbers(attested)
    resume_verbs = _ownership_verbs(attested)

    extra_numbers = numbers(proposed) - resume_numbers
    if extra_numbers:
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Fabricated metric(s) are not present in the resume: "
            + ", ".join(sorted(extra_numbers)),
            start=location.start,
            end=location.end,
        )

    extra_years = _years(proposed) - resume_years
    extra_months = _months(proposed) - resume_months
    if extra_years or extra_months:
        invented = ", ".join(sorted(extra_years | extra_months))
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale=f"Date(s) are not present in the resume: {invented}",
            start=location.start,
            end=location.end,
        )

    extra_skills = short_skills(proposed) - resume_skills
    if extra_skills:
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Unsupported skill(s) are not demonstrated in the resume: "
            + ", ".join(sorted(extra_skills)),
            start=location.start,
            end=location.end,
        )

    extra_titles = _title_tokens(proposed) - resume_titles
    if extra_titles:
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Invented job title(s) are not present in the resume: "
            + ", ".join(sorted(extra_titles)),
            start=location.start,
            end=location.end,
        )

    extra_nouns: list[str] = []
    for noun in _proper_nouns(proposed):
        if noun in resume_norm or noun in resume_nouns:
            continue
        extra_nouns.append(noun)
    if extra_nouns:
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Invented employer or proper noun(s) are not present in the resume: "
            + ", ".join(sorted(set(extra_nouns))),
            start=location.start,
            end=location.end,
        )

    extra_verbs = _ownership_verbs(proposed) - resume_verbs
    extra_intensity = _intensifiers(proposed) - _intensifiers(attested)
    if extra_verbs or extra_intensity:
        labels = sorted(extra_verbs | extra_intensity)
        return _needs_evidence(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Claim is ambiguous without additional evidence: " + ", ".join(labels),
        )

    linked = None
    if proposal.requirement_id:
        for match in matches:
            if match.id == proposal.requirement_id:
                linked = match
                break
    if linked is not None and linked.evidence_state == "not_found" and location.status != "unique":
        return ClassifiedProposal(
            kind="missing_qualification",
            original_span=None,
            proposed_text=proposed,
            evidence_span=None,
            requirement_id=linked.id,
            rationale="This qualification is not in the resume. The candidate must supply evidence.",
        )

    extra_content = [
        token
        for token in tokens(proposed)
        if token not in resume_token_set
        and token not in resume_skills
        and token not in _GLUE
        and token not in _INTENSIFIERS
        and token not in _OWNERSHIP_VERBS
        and token not in _TITLE_TOKENS
    ]
    if extra_content:
        return _unsupported(
            original=original,
            proposed=proposed,
            found=found,
            requirement_id=proposal.requirement_id,
            rationale="Invented responsibility or achievement is not present in the resume: "
            + ", ".join(sorted(set(extra_content))),
            start=location.start,
            end=location.end,
        )

    if location.status == "missing":
        return _unsupported(
            original=original,
            proposed=proposed,
            found=None,
            requirement_id=proposal.requirement_id,
            rationale="original_span is not identifiable in the supplied resume.",
        )
    if location.status == "ambiguous":
        return _needs_evidence(
            original=original,
            proposed=proposed,
            found=None,
            requirement_id=proposal.requirement_id,
            rationale="original_span matches more than one location; refusing first-occurrence replacement.",
        )
    if location.start is None or location.end is None or location.exact is None:
        return _needs_evidence(
            original=original,
            proposed=proposed,
            found=None,
            requirement_id=proposal.requirement_id,
            rationale="original_span could not be bound to a unique offset.",
        )
    if (location.end - location.start) < _MIN_SPAN_LENGTH:
        return _needs_evidence(
            original=location.exact,
            proposed=proposed,
            found=location.exact,
            requirement_id=proposal.requirement_id,
            rationale="original_span is too short to apply safely.",
        )

    return ClassifiedProposal(
        kind="supported_rewrite",
        original_span=location.exact,
        proposed_text=proposed,
        evidence_span=location.exact,
        requirement_id=proposal.requirement_id,
        rationale=proposal.rationale,
        span_start=location.start,
        span_end=location.end,
    )


def resolve_span_conflicts(classified: list[ClassifiedProposal]) -> list[ClassifiedProposal]:
    """Downgrade overlapping or duplicate supported rewrites in a batch."""
    resolved: list[ClassifiedProposal] = []
    claimed: list[tuple[int, int]] = []
    for item in classified:
        if item.kind != "supported_rewrite" or item.span_start is None or item.span_end is None:
            resolved.append(item)
            continue
        current = (item.span_start, item.span_end)
        conflict = next((existing for existing in claimed if ranges_overlap(existing, current)), None)
        if conflict is not None:
            reason = (
                "duplicate span"
                if conflict == current
                else "overlapping span"
            )
            resolved.append(
                ClassifiedProposal(
                    kind="unsupported",
                    original_span=item.original_span,
                    proposed_text=item.proposed_text,
                    evidence_span=item.evidence_span,
                    requirement_id=item.requirement_id,
                    rationale=f"Conflicting rewrite ({reason}); not applied automatically.",
                    span_start=item.span_start,
                    span_end=item.span_end,
                )
            )
            continue
        claimed.append(current)
        resolved.append(item)
    return resolved


def missing_qualification_proposals(matches: list[RequirementMatch]) -> list[ClassifiedProposal]:
    """Deterministic flags for requirements with no resume evidence."""
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
