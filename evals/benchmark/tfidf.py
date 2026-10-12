"""Closed-set TF-IDF cosine used only as an evaluation baseline.

IDF is fit on the supplied corpus. Thresholds are frozen in REVIEW.md.
This module is not imported by the CareerOS request path.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
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

CONFIRMED_THRESHOLD = 0.50
PARTIAL_THRESHOLD = 0.20


def tokenize(text: str) -> list[str]:
    """Lowercase tokens of length >= 2, minus eval stopwords."""
    return [
        token
        for token in _TOKEN_RE.findall(re.sub(r"\s+", " ", text.lower()))
        if token not in _STOPWORDS
    ]


def _tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    n = float(len(tokens))
    return {token: count / n for token, count in counts.items()}


class TfidfIndex:
    """Document-frequency table fit on a frozen corpus."""

    def __init__(self, documents: Iterable[str]) -> None:
        docs = [tokenize(doc) for doc in documents]
        self._n_docs = max(len(docs), 1)
        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        self._idf: dict[str, float] = {
            token: math.log((1.0 + self._n_docs) / (1.0 + count)) + 1.0
            for token, count in df.items()
        }

    def vector(self, text: str) -> dict[str, float]:
        """tf-idf vector; unknown terms receive smoothed IDF of 1.0."""
        weights: dict[str, float] = {}
        for token, tf in _tf(tokenize(text)).items():
            weights[token] = tf * self._idf.get(token, 1.0)
        return weights


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    """Cosine similarity of two sparse vectors."""
    if not left or not right:
        return 0.0
    dot = sum(left[token] * right[token] for token in left if token in right)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def similarity(index: TfidfIndex, requirement: str, resume: str) -> float:
    """Cosine(requirement, full resume text)."""
    return cosine(index.vector(requirement), index.vector(resume))


def state_from_similarity(score: float) -> str:
    """Map a frozen cosine into an evidence state."""
    if score >= CONFIRMED_THRESHOLD:
        return "confirmed"
    if score >= PARTIAL_THRESHOLD:
        return "partial"
    return "not_found"
