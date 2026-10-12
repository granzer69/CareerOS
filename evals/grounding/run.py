#!/usr/bin/env python3
"""Deterministic Slice 4.1 grounding evaluation.

No hosted model APIs. No weight downloads. Labels come from the frozen
JSON set, not from classifier output.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.evidence import RequirementMatch  # noqa: E402
from app.schemas.resume_edit import ModelEditProposal  # noqa: E402
from app.services.edit_grounding import (  # noqa: E402
    apply_span_at,
    classify_proposal,
    content_hash,
    locate_span,
    resolve_span_conflicts,
)

DATASET_DIR = Path(__file__).resolve().parent / "v1.0.0"
CASES_PATH = DATASET_DIR / "cases.json"
LAST_RUN_PATH = DATASET_DIR / "last_run.json"
UNPATCHED_PATH = DATASET_DIR / "last_run_unpatched.json"
RESULTS_PATH = DATASET_DIR / "RESULTS.md"

ALLOWED_EXPECTED = {"supported_rewrite", "needs_evidence", "unsupported"}
REJECT_BUCKET = {"needs_evidence", "unsupported", "missing_qualification"}


def load_dataset(path: Path = CASES_PATH) -> dict[str, Any]:
    """Load the frozen evaluation set."""
    return json.loads(path.read_text(encoding="utf-8"))


def resume_text(case: dict[str, Any], fixtures: dict[str, str]) -> str:
    """Resolve resume text from a fixture name or inline field."""
    if "resume_text" in case:
        return str(case["resume_text"])
    return fixtures[str(case["resume"])]


def map_actual_kind(kind: str) -> str:
    """missing_qualification agrees with expected needs_evidence."""
    if kind == "missing_qualification":
        return "needs_evidence"
    return kind


def classify_case(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    """Run classify_proposal on one frozen case."""
    text = resume_text(case, fixtures)
    matches = [
        RequirementMatch.model_validate(item) for item in case.get("matches") or []
    ]
    proposal = ModelEditProposal(
        original_span=case["original_span"],
        proposed_text=case["proposed_text"],
        requirement_id=case.get("requirement_id"),
        rationale="eval",
    )
    classified = classify_proposal(proposal, resume_text=text, matches=matches)
    actual_raw = classified.kind
    actual = map_actual_kind(actual_raw)
    expected = case["expected"]
    if expected not in ALLOWED_EXPECTED:
        raise ValueError(f"{case['id']}: invalid expected label {expected}")
    false_supported = actual == "supported_rewrite" and expected != "supported_rewrite"
    false_rejected = expected == "supported_rewrite" and actual != "supported_rewrite"
    label_match = actual == expected
    return {
        "id": case["id"],
        "family": case["family"],
        "expected": expected,
        "actual": actual,
        "actual_raw": actual_raw,
        "rationale": classified.rationale,
        "span_start": classified.span_start,
        "span_end": classified.span_end,
        "label_match": label_match,
        "false_supported": false_supported,
        "false_rejected": false_rejected,
        "notes": case.get("notes", ""),
    }


def _run_locate(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    text = resume_text(case, fixtures)
    located = locate_span(text, case["span"])
    ok = located.status == case["expected_status"]
    if ok and located.status == "unique":
        start = located.start
        end = located.end
        if start is None or end is None:
            ok = False
        elif text[start:end] != (located.exact or ""):
            ok = False
        elif located.exact is not None and located.exact.lower() != case["span"].strip().lower():
            # Allow case-insensitive unique hits; slice length must still match the needle.
            if len(located.exact) != len(case["span"].strip()):
                ok = False
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": ok,
        "detail": {
            "status": located.status,
            "start": located.start,
            "end": located.end,
            "exact": located.exact,
        },
    }


def _run_hash(case: dict[str, Any]) -> dict[str, Any]:
    left = content_hash(case["left"])
    right = content_hash(case["right"])
    equal = left == right
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": equal is case["expected_equal"],
        "detail": {"left": left, "right": right, "equal": equal},
    }


def _run_nfc_nfd(case: dict[str, Any]) -> dict[str, Any]:
    nfc = unicodedata.normalize("NFC", case["text_nfc"])
    nfd = unicodedata.normalize("NFD", case["text_nfc"])
    hashes_differ = content_hash(nfc) != content_hash(nfd)
    locate_missing = locate_span(nfd, nfc).status == "missing" if nfc != nfd else True
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": hashes_differ and locate_missing and nfc != nfd,
        "detail": {
            "nfc": nfc,
            "nfd": nfd,
            "nfc_hash": content_hash(nfc),
            "nfd_hash": content_hash(nfd),
            "nfc_len": len(nfc),
            "nfd_len": len(nfd),
            "locate_nfd_with_nfc": locate_span(nfd, nfc).status,
        },
    }


def _run_unicode_offsets(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    text = resume_text(case, fixtures)
    span = case["span"]
    located = locate_span(text, span)
    ok = located.status == "unique"
    if located.start is None or located.end is None or located.exact is None:
        ok = False
    else:
        sliced = text[located.start : located.end]
        ok = ok and sliced == located.exact and sliced == span
        ok = ok and (located.end - located.start) == len(span)
        rebound = locate_span(text, sliced)
        ok = ok and rebound.start == located.start and rebound.end == located.end
        hashed = content_hash(text)
        edited = apply_span_at(
            resume_text=text,
            start=located.start,
            end=located.end,
            expected_span=span,
            proposed_text=span,
        )
        ok = ok and edited == text and content_hash(edited) == hashed
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": ok,
        "detail": {
            "status": located.status,
            "start": located.start,
            "end": located.end,
            "hash": content_hash(text),
        },
    }


def _run_apply(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    text = resume_text(case, fixtures)
    span = case["span"]
    located = locate_span(text, span)
    start = case.get("start_override", located.start if located.start is not None else 0)
    end = case.get("end_override", located.end if located.end is not None else 0)
    expected_span = case.get("expected_span_override", span)
    error: str | None = None
    result: str | None = None
    try:
        result = apply_span_at(
            resume_text=text,
            start=start,
            end=end,
            expected_span=expected_span,
            proposed_text=case["proposed_text"],
        )
    except ValueError as exc:
        error = str(exc)
    expect_error = bool(case["expect_error"])
    passed = (error is not None) if expect_error else (error is None and result is not None)
    if passed and not expect_error and result is not None:
        passed = content_hash(result) != content_hash(text)
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": passed,
        "detail": {"error": error, "result": result},
    }


def _run_apply_then_stale(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    text = resume_text(case, fixtures)
    span = case["span"]
    located = locate_span(text, span)
    if located.start is None or located.end is None:
        return {"id": case["id"], "check": case["check"], "passed": False, "detail": {"reason": "span not unique"}}
    original_hash = content_hash(text)
    edited = apply_span_at(
        resume_text=text,
        start=located.start,
        end=located.end,
        expected_span=span,
        proposed_text=case["proposed_text"],
    )
    new_hash = content_hash(edited)
    stale_error = False
    try:
        apply_span_at(
            resume_text=edited,
            start=located.start,
            end=located.end,
            expected_span=span,
            proposed_text="stale",
        )
    except ValueError:
        stale_error = True
    passed = original_hash != new_hash and stale_error and edited != text
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": passed,
        "detail": {
            "original_hash": original_hash,
            "edited_hash": new_hash,
            "stale_apply_rejected": stale_error,
        },
    }


def _run_conflicts(case: dict[str, Any], fixtures: dict[str, str]) -> dict[str, Any]:
    text = resume_text(case, fixtures)
    classified = [
        classify_proposal(
            ModelEditProposal(
                original_span=item["original_span"],
                proposed_text=item["proposed_text"],
                requirement_id=None,
                rationale="eval",
            ),
            resume_text=text,
            matches=[],
        )
        for item in case["proposals"]
    ]
    resolved = resolve_span_conflicts(classified)
    kinds = [item.kind for item in resolved]
    return {
        "id": case["id"],
        "check": case["check"],
        "passed": kinds == case["expected_kinds"],
        "detail": {"kinds": kinds, "rationales": [item.rationale for item in resolved]},
    }


def run_integrity(cases: list[dict[str, Any]], fixtures: dict[str, str]) -> list[dict[str, Any]]:
    """Execute offset/hash/overlap/unicode integrity cases."""
    results: list[dict[str, Any]] = []
    for case in cases:
        check = case["check"]
        if check == "locate_span":
            results.append(_run_locate(case, fixtures))
        elif check == "content_hash":
            results.append(_run_hash(case))
        elif check == "nfc_nfd_hash":
            results.append(_run_nfc_nfd(case))
        elif check == "unicode_offsets":
            results.append(_run_unicode_offsets(case, fixtures))
        elif check == "apply_span_at":
            results.append(_run_apply(case, fixtures))
        elif check == "apply_then_stale":
            results.append(_run_apply_then_stale(case, fixtures))
        elif check == "resolve_conflicts":
            results.append(_run_conflicts(case, fixtures))
        else:
            results.append(
                {
                    "id": case["id"],
                    "check": check,
                    "passed": False,
                    "detail": {"reason": f"unknown check {check}"},
                }
            )
    return results


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Precision/recall for the supported_rewrite apply decision."""
    n = len(rows)
    tp = sum(1 for row in rows if row["expected"] == "supported_rewrite" and row["actual"] == "supported_rewrite")
    fp = sum(1 for row in rows if row["false_supported"])
    fn = sum(1 for row in rows if row["false_rejected"])
    tn = n - tp - fp - fn
    expected_supported = sum(1 for row in rows if row["expected"] == "supported_rewrite")
    expected_reject = n - expected_supported
    predicted_supported = sum(1 for row in rows if row["actual"] == "supported_rewrite")
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    false_supported_rate = (fp / expected_reject) if expected_reject else 0.0
    false_rejected_rate = (fn / expected_supported) if expected_supported else 0.0
    confusion: dict[str, dict[str, int]] = {}
    for row in rows:
        confusion.setdefault(row["expected"], {})
        confusion[row["expected"]][row["actual"]] = confusion[row["expected"]].get(row["actual"], 0) + 1
    return {
        "n_classification": n,
        "tp_supported": tp,
        "fp_false_supported": fp,
        "fn_false_rejected": fn,
        "tn_correct_reject": tn,
        "predicted_supported": predicted_supported,
        "expected_supported": expected_supported,
        "expected_reject": expected_reject,
        "precision_supported": precision,
        "recall_supported": recall,
        "false_supported_rate": false_supported_rate,
        "false_rejected_rate": false_rejected_rate,
        "label_agreement": (sum(1 for row in rows if row["label_match"]) / n) if n else 0.0,
        "confusion_expected_by_actual": confusion,
        "family_counts": dict(Counter(row["family"] for row in rows)),
        "limitation": (
            "n is too small for production-level factual guarantees. "
            "These are lexical regression tests, not semantic entailment."
        ),
    }


def render_results(payload: dict[str, Any]) -> str:
    """Human-readable report for review. Not a production audit."""
    metrics = payload["metrics"]
    precision = metrics["precision_supported"]
    recall = metrics["recall_supported"]

    def pct(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.1%}"

    lines = [
        "# Grounding evaluation RESULTS v1.0.0",
        "",
        f"Ran: {payload['ran_at']}",
        f"Dataset: `{payload['dataset']}`",
        f"Classifier: `{payload['classifier']}`",
        "Inference: none (no hosted APIs, no weight downloads).",
        "",
        "## Metrics (supported_rewrite as the positive / apply class)",
        "",
        f"- Test-set size (classification): **{metrics['n_classification']}**",
        f"- Integrity cases: **{payload['n_integrity']}** (passed {payload['integrity_passed']})",
        f"- Precision: **{pct(precision)}**",
        f"- Recall: **{pct(recall)}**",
        f"- False-supported rate: **{pct(metrics['false_supported_rate'])}** ({metrics['fp_false_supported']}/{metrics['expected_reject']})",
        f"- False-rejected rate: **{pct(metrics['false_rejected_rate'])}** ({metrics['fn_false_rejected']}/{metrics['expected_supported']})",
        f"- Exact 3-way label agreement (after mapping missing_qualification → needs_evidence): **{pct(metrics['label_agreement'])}**",
        "",
    ]
    unpatched = payload.get("unpatched_metrics")
    if unpatched:
        lines.extend(
            [
                "## Unpatched baseline (same frozen set, before tokenizer/negation patches)",
                "",
                f"- Precision: **{pct(unpatched['precision_supported'])}**",
                f"- Recall: **{pct(unpatched['recall_supported'])}**",
                f"- False-supported rate: **{pct(unpatched['false_supported_rate'])}** ({unpatched['fp_false_supported']}/{unpatched['expected_reject']})",
                f"- False-rejected rate: **{pct(unpatched['false_rejected_rate'])}** ({unpatched['fn_false_rejected']}/{unpatched['expected_supported']})",
                f"- Integrity: {unpatched.get('integrity_passed', 'n/a')}/{unpatched.get('n_integrity', 'n/a')}",
                "",
                "Patches applied after this baseline: strip sentence-final periods from tokens and proper nouns; treat `as`/`by`/`is` as glue; ignore tokens that appear only in negated clauses; classify unbound not-found requirements before extra-content.",
                "",
            ]
        )
    lines.extend(
        [
            metrics["limitation"],
            "",
            "## Confusion (expected → actual, mapped)",
            "",
            "```",
            json.dumps(metrics["confusion_expected_by_actual"], indent=2, sort_keys=True),
            "```",
            "",
            "## False-supported (unsafe apply)",
            "",
        ]
    )
    false_supported = payload["false_supported"]
    if not false_supported:
        lines.append("None.")
    else:
        for row in false_supported:
            lines.append(
                f"- `{row['id']}` [{row['family']}] expected `{row['expected']}`, "
                f"actual `{row['actual']}` — {row['rationale']}"
            )
    lines.extend(["", "## False-rejected (safe paraphrase blocked)", ""])
    false_rejected = payload["false_rejected"]
    if not false_rejected:
        lines.append("None.")
    else:
        for row in false_rejected:
            lines.append(
                f"- `{row['id']}` [{row['family']}] expected `{row['expected']}`, "
                f"actual `{row['actual']}` — {row['rationale']}"
            )
    lines.extend(["", "## Other 3-way mismatches (still correctly not applied)", ""])
    other = payload["other_mismatches"]
    if not other:
        lines.append("None.")
    else:
        for row in other:
            lines.append(
                f"- `{row['id']}` [{row['family']}] expected `{row['expected']}`, "
                f"actual `{row['actual']}` (raw `{row['actual_raw']}`) — {row['rationale']}"
            )
    failed_integrity = [row for row in payload["integrity"] if not row["passed"]]
    lines.extend(["", "## Integrity failures", ""])
    if not failed_integrity:
        lines.append("None. Offset, hash, overlap, Unicode, and stale-edit checks passed.")
    else:
        for row in failed_integrity:
            lines.append(f"- `{row['id']}` `{row['check']}` {row.get('detail')}")
    lines.extend(
        [
            "",
            "## Remaining limitations",
            "",
            "- Bag-of-tokens grounding cannot prove semantic entailment.",
            "- Mixing attested employers, titles, dates, and metrics can still look supported.",
            "- Near-synonyms (built/created) are lexical misses, not NLI.",
            "- Negation handling is clause-window lexical stripping, not semantic scope.",
            "- Do not treat these percentages as production factual guarantees.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def run_eval(dataset_path: Path = CASES_PATH) -> dict[str, Any]:
    """Run classification and integrity cases; return a JSON-serializable report."""
    dataset = load_dataset(dataset_path)
    fixtures: dict[str, str] = dataset["fixtures"]
    classification = [
        classify_case(case, fixtures) for case in dataset["classification_cases"]
    ]
    integrity = run_integrity(dataset["integrity_cases"], fixtures)
    metrics = compute_metrics(classification)
    false_supported = [row for row in classification if row["false_supported"]]
    false_rejected = [row for row in classification if row["false_rejected"]]
    other_mismatches = [
        row
        for row in classification
        if not row["label_match"] and not row["false_supported"] and not row["false_rejected"]
    ]
    payload = {
        "version": dataset["version"],
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": str(dataset_path.relative_to(ROOT)),
        "classifier": "app.services.edit_grounding.classify_proposal",
        "inference": "none",
        "metrics": metrics,
        "n_integrity": len(integrity),
        "integrity_passed": sum(1 for row in integrity if row["passed"]),
        "false_supported": false_supported,
        "false_rejected": false_rejected,
        "other_mismatches": other_mismatches,
        "classification": classification,
        "integrity": integrity,
    }
    if UNPATCHED_PATH.exists():
        baseline = json.loads(UNPATCHED_PATH.read_text(encoding="utf-8"))
        payload["unpatched_metrics"] = {
            **baseline.get("metrics", {}),
            "n_integrity": baseline.get("n_integrity"),
            "integrity_passed": baseline.get("integrity_passed"),
            "false_supported_ids": [row["id"] for row in baseline.get("false_supported", [])],
            "false_rejected_ids": [row["id"] for row in baseline.get("false_rejected", [])],
        }
    return payload


def write_report(payload: dict[str, Any], last_run: Path = LAST_RUN_PATH, results: Path = RESULTS_PATH) -> None:
    """Persist machine and human reports next to the frozen set."""
    last_run.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    results.write_text(render_results(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CareerOS Slice 4.1 grounding eval v1.0.0")
    parser.add_argument("--dataset", type=Path, default=CASES_PATH)
    parser.add_argument("--write", action="store_true", default=True)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    payload = run_eval(args.dataset)
    if not args.no_write:
        write_report(payload)
    metrics = payload["metrics"]
    print(f"n={metrics['n_classification']} integrity={payload['integrity_passed']}/{payload['n_integrity']}")
    precision = metrics["precision_supported"]
    recall = metrics["recall_supported"]
    print(
        "precision={p} recall={r} false_supported={fs:.1%} false_rejected={fr:.1%}".format(
            p="n/a" if precision is None else f"{precision:.3f}",
            r="n/a" if recall is None else f"{recall:.3f}",
            fs=metrics["false_supported_rate"],
            fr=metrics["false_rejected_rate"],
        )
    )
    print("false-supported:", ", ".join(row["id"] for row in payload["false_supported"]) or "none")
    print("false-rejected:", ", ".join(row["id"] for row in payload["false_rejected"]) or "none")
    failed = [row["id"] for row in payload["integrity"] if not row["passed"]]
    if failed:
        print("integrity failures:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
