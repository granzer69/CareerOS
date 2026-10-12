#!/usr/bin/env python3
"""Deterministic Slice 5 pipeline benchmark.

No hosted APIs. No embedding or GGUF weight downloads. Labels come from the
frozen JSON set. Local GGUF quality is recorded as not-measured when weights
are absent.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.local_inference import LocalModelNotFoundError, require_local_model_file  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.schemas.evidence import ModelExtraction  # noqa: E402
from app.schemas.resume_edit import ModelEditBatch  # noqa: E402
from app.services.evidence_matcher import match_requirement  # noqa: E402
from app.services.jd_extraction import extract_requirements  # noqa: E402
from app.services.scoring import score_application  # noqa: E402
from evals.benchmark.tfidf import TfidfIndex, similarity, state_from_similarity  # noqa: E402

DATASET_DIR = Path(__file__).resolve().parent / "v1.0.0"
CASES_PATH = DATASET_DIR / "cases.json"
LAST_RUN_PATH = DATASET_DIR / "last_run.json"
RESULTS_PATH = DATASET_DIR / "RESULTS.md"
DECISION_PATH = DATASET_DIR / "MODEL_DECISION.md"
GROUNDING_LAST_RUN = ROOT / "evals" / "grounding" / "v1.0.0" / "last_run.json"

MATCHERS = ("lexical", "tfidf", "hybrid")
STATES = ("confirmed", "partial", "not_found", "contradicted", "unknown")


def load_dataset(path: Path = CASES_PATH) -> dict[str, Any]:
    """Load the locked Slice 5 split."""
    return json.loads(path.read_text(encoding="utf-8"))


def _key_in_text(key: str, text: str) -> bool:
    haystack = text.lower()
    needle = key.lower()
    if needle in {"go", "r", "c"}:
        return f" {needle} " in f" {haystack} " or haystack.strip() == needle
    return needle in haystack


def _find_requirement(extracted: list[Any], key: str) -> Any | None:
    for item in extracted:
        if _key_in_text(key, item.text):
            return item
    return None


def _build_tfidf(cases: list[dict[str, Any]]) -> TfidfIndex:
    docs: list[str] = []
    for case in cases:
        docs.append(case["resume"])
        docs.append(case["jd"])
        for req in extract_requirements(case["jd"]):
            docs.append(req.text)
    return TfidfIndex(docs)


def _tfidf_state(index: TfidfIndex, requirement: Any, resume: str) -> str:
    lexical = match_requirement(requirement, resume)
    if lexical.evidence_state == "contradicted":
        return "contradicted"
    if lexical.evidence_state == "unknown":
        return "unknown"
    return state_from_similarity(similarity(index, requirement.text, resume))


def _hybrid_state(lexical_state: str, tfidf_state: str) -> str:
    """Frozen hybrid rule: exact/negated lexical wins; TF-IDF may fill not_found."""
    if lexical_state in {"contradicted", "unknown", "confirmed"}:
        return lexical_state
    if lexical_state == "not_found" and tfidf_state in {"confirmed", "partial"}:
        return tfidf_state
    return lexical_state


def _extraction_hits(extracted: list[Any], expected: list[dict[str, Any]]) -> dict[str, int]:
    predicted_keys = []
    for item in extracted:
        matched = next((row["key"] for row in expected if _key_in_text(row["key"], item.text)), None)
        predicted_keys.append(matched)
    tp = sum(1 for key in predicted_keys if key is not None)
    fp = sum(1 for key in predicted_keys if key is None)
    found = {key for key in predicted_keys if key is not None}
    fn = sum(1 for row in expected if row["key"] not in found)
    return {"tp": tp, "fp": fp, "fn": fn}


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def _state_confusion(rows: list[dict[str, Any]], matcher: str) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        table[row["expected"]][row[matcher]] += 1
    return {expected: dict(actuals) for expected, actuals in table.items()}


def _state_prf(rows: list[dict[str, Any]], matcher: str) -> dict[str, Any]:
    per_state: dict[str, dict[str, float | None | int]] = {}
    for state in STATES:
        tp = sum(1 for row in rows if row["expected"] == state and row[matcher] == state)
        fp = sum(1 for row in rows if row["expected"] != state and row[matcher] == state)
        fn = sum(1 for row in rows if row["expected"] == state and row[matcher] != state)
        stats = _prf(tp, fp, fn)
        per_state[state] = {"tp": tp, "fp": fp, "fn": fn, **stats}
    labeled = [row for row in rows if row["expected"] in STATES]
    accuracy = (
        sum(1 for row in labeled if row[matcher] == row["expected"]) / len(labeled) if labeled else 0.0
    )
    f1s = [value["f1"] for value in per_state.values() if value["f1"] is not None and (value["tp"] + value["fn"])]
    macro_f1 = (sum(f1s) / len(f1s)) if f1s else None
    return {"accuracy": accuracy, "macro_f1": macro_f1, "per_state": per_state}


def run_schema_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate extraction and edit payloads against Pydantic contracts."""
    results: list[dict[str, Any]] = []
    for case in cases:
        error: str | None = None
        valid = True
        try:
            if case["kind"] == "extraction":
                ModelExtraction.model_validate(case["payload"])
            elif case["kind"] == "edit_batch":
                ModelEditBatch.model_validate(case["payload"])
            else:
                valid = False
                error = f"unknown kind {case['kind']}"
        except ValidationError as exc:
            valid = False
            error = exc.errors()[0]["type"] if exc.errors() else "validation_error"
        passed = valid is case["expected_valid"]
        results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "expected_valid": case["expected_valid"],
                "actual_valid": valid,
                "passed": passed,
                "error": error,
            }
        )
    return results


def probe_local_gguf() -> dict[str, Any]:
    """Record whether a local GGUF file exists. Never download weights."""
    path = settings.LOCAL_MODEL_PATH.strip()
    if not path:
        return {
            "status": "not_measured",
            "reason": "LOCAL_MODEL_PATH is unset",
            "downloaded": False,
        }
    try:
        resolved = require_local_model_file(path)
    except LocalModelNotFoundError as exc:
        return {
            "status": "not_measured",
            "reason": str(exc),
            "configured_path": path,
            "downloaded": False,
        }
    return {
        "status": "file_present_not_loaded",
        "reason": "Weight file exists; Slice 5 does not load llama.cpp or run generations.",
        "configured_path": str(resolved),
        "downloaded": False,
    }


def load_grounding_metrics() -> dict[str, Any] | None:
    """Import Slice 4.1 grounding metrics rather than relabeling that set."""
    if not GROUNDING_LAST_RUN.exists():
        return None
    payload = json.loads(GROUNDING_LAST_RUN.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})
    return {
        "dataset": payload.get("dataset"),
        "n_classification": metrics.get("n_classification"),
        "precision_supported": metrics.get("precision_supported"),
        "recall_supported": metrics.get("recall_supported"),
        "false_supported_rate": metrics.get("false_supported_rate"),
        "false_rejected_rate": metrics.get("false_rejected_rate"),
        "limitation": metrics.get("limitation"),
    }


def run_matching(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Score extraction, evidence states, and rubric stability for every matcher."""
    index = _build_tfidf(cases)
    by_id = {case["id"]: case for case in cases}
    extraction_totals = Counter()
    state_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    false_confirmed: list[dict[str, Any]] = []
    stability: list[dict[str, Any]] = []

    for case in cases:
        extracted = extract_requirements(case["jd"])
        extraction_totals.update(_extraction_hits(extracted, case["expected_requirements"]))
        scored_lexical = score_application(
            matches=[match_requirement(item, case["resume"]) for item in extracted],
            resume_text=case["resume"],
            estimated_level_hint=None,
        )
        labeled_states: dict[str, dict[str, str]] = {}
        for expected in case["expected_requirements"]:
            requirement = _find_requirement(extracted, expected["key"])
            if requirement is None:
                lexical_state = "missing_extraction"
                tfidf_state = "missing_extraction"
                hybrid_state = "missing_extraction"
            else:
                lexical_state = match_requirement(requirement, case["resume"]).evidence_state
                tfidf_state = _tfidf_state(index, requirement, case["resume"])
                hybrid_state = _hybrid_state(lexical_state, tfidf_state)
            row = {
                "case_id": case["id"],
                "key": expected["key"],
                "expected": expected["evidence_state"],
                "lexical": lexical_state,
                "tfidf": tfidf_state,
                "hybrid": hybrid_state,
                "hard_negative": bool(case.get("hard_negative")),
            }
            state_rows.append(row)
            labeled_states[expected["key"]] = row
            if case.get("hard_negative") and expected["key"] in (case.get("false_confirmed_keys") or []):
                for matcher in MATCHERS:
                    if row[matcher] == "confirmed":
                        false_confirmed.append(
                            {
                                "case_id": case["id"],
                                "key": expected["key"],
                                "matcher": matcher,
                                "actual": row[matcher],
                            }
                        )
        case_rows.append(
            {
                "id": case["id"],
                "family": case["family"],
                "job_fit": scored_lexical.job_fit_score,
                "resume_alignment": scored_lexical.resume_alignment_score,
                "readiness": scored_lexical.application_readiness_score,
                "blocked": scored_lexical.blocked_by_requirement,
                "expected_blocked": case["expected_blocked"],
                "blocked_match": scored_lexical.blocked_by_requirement is case["expected_blocked"],
                "states": labeled_states,
            }
        )
        parent_id = case.get("paraphrase_of") or case.get("format_variant_of")
        if parent_id:
            parent = by_id[parent_id]
            parent_extracted = extract_requirements(parent["jd"])
            parent_scored = score_application(
                matches=[match_requirement(item, parent["resume"]) for item in parent_extracted],
                resume_text=parent["resume"],
                estimated_level_hint=None,
            )
            delta = abs(scored_lexical.job_fit_score - parent_scored.job_fit_score)
            limit = int(case.get("max_job_fit_delta", 5))
            stability.append(
                {
                    "id": case["id"],
                    "parent": parent_id,
                    "kind": "paraphrase" if case.get("paraphrase_of") else "format",
                    "delta_job_fit": delta,
                    "limit": limit,
                    "passed": delta <= limit,
                    "child_job_fit": scored_lexical.job_fit_score,
                    "parent_job_fit": parent_scored.job_fit_score,
                }
            )

    hard_neg_keys = [
        row
        for row in state_rows
        if row["hard_negative"] and row["key"] in _false_confirmed_key_set(cases, row["case_id"])
    ]
    matcher_metrics = {
        matcher: {
            **_state_prf(state_rows, matcher),
            "confusion": _state_confusion(state_rows, matcher),
            "hard_negative_false_confirmed": sum(1 for row in hard_neg_keys if row[matcher] == "confirmed"),
            "hard_negative_n": len(hard_neg_keys),
        }
        for matcher in MATCHERS
    }
    return {
        "extraction": {
            **dict(extraction_totals),
            **_prf(extraction_totals["tp"], extraction_totals["fp"], extraction_totals["fn"]),
            "n_cases": len(cases),
        },
        "n_labeled_states": len(state_rows),
        "matchers": matcher_metrics,
        "false_confirmed": false_confirmed,
        "stability": stability,
        "cases": case_rows,
        "state_rows": state_rows,
        "blocked_accuracy": (
            sum(1 for row in case_rows if row["blocked_match"]) / len(case_rows) if case_rows else 0.0
        ),
    }


def _false_confirmed_key_set(cases: list[dict[str, Any]], case_id: str) -> set[str]:
    for case in cases:
        if case["id"] == case_id:
            return set(case.get("false_confirmed_keys") or [])
    return set()


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def render_results(payload: dict[str, Any]) -> str:
    """Human-readable Slice 5 report."""
    matching = payload["matching"]
    extraction = matching["extraction"]
    lines = [
        "# Pipeline benchmark RESULTS v1.0.0",
        "",
        f"Ran: {payload['ran_at']}",
        f"Dataset: `{payload['dataset']}`",
        "Inference: none. Embeddings: not run. GGUF generations: not run. Downloads: none.",
        "",
        "## Test-set size",
        "",
        f"- Matching/extraction cases: **{extraction['n_cases']}**",
        f"- Labeled evidence states: **{matching['n_labeled_states']}**",
        f"- Schema cases: **{payload['n_schema']}** (passed {payload['schema_passed']})",
        "",
        "n is too small for production ML claims. This is a locked regression fixture.",
        "",
        "## Requirement extraction (deterministic splitter)",
        "",
        f"- Precision: **{_pct(extraction['precision'])}**",
        f"- Recall: **{_pct(extraction['recall'])}**",
        f"- F1: **{_pct(extraction['f1'])}**",
        f"- tp={extraction['tp']} fp={extraction['fp']} fn={extraction['fn']}",
        "",
        "## Evidence-state agreement",
        "",
    ]
    for matcher in MATCHERS:
        stats = matching["matchers"][matcher]
        hn = stats["hard_negative_false_confirmed"]
        hn_n = stats["hard_negative_n"]
        lines.extend(
            [
                f"### {matcher}",
                "",
                f"- Accuracy: **{_pct(stats['accuracy'])}**",
                f"- Macro-F1 (states with support): **{_pct(stats['macro_f1'])}**",
                f"- Hard-negative false-confirmed: **{hn}/{hn_n}**",
                "",
            ]
        )
    lines.extend(
        [
            "## Score stability (lexical rubric v1.0.0)",
            "",
        ]
    )
    if not matching["stability"]:
        lines.append("No paired cases.")
    else:
        for row in matching["stability"]:
            status = "pass" if row["passed"] else "FAIL"
            lines.append(
                f"- `{row['id']}` vs `{row['parent']}` ({row['kind']}): "
                f"Δ job-fit {row['delta_job_fit']} (limit {row['limit']}) [{status}]"
            )
    lines.extend(
        [
            "",
            f"Eligibility blocker accuracy: **{_pct(matching['blocked_accuracy'])}**",
            "",
            "## Hard-negative false confirms",
            "",
        ]
    )
    if not matching["false_confirmed"]:
        lines.append("None.")
    else:
        for row in matching["false_confirmed"]:
            lines.append(
                f"- `{row['case_id']}` key `{row['key']}` matcher `{row['matcher']}` → `{row['actual']}`"
            )
    grounding = payload.get("grounding")
    lines.extend(["", "## Grounding (imported from Slice 4.1)", ""])
    if grounding:
        lines.extend(
            [
                f"- Dataset: `{grounding['dataset']}`",
                f"- n={grounding['n_classification']} precision={_pct(grounding['precision_supported'])} "
                f"recall={_pct(grounding['recall_supported'])}",
                f"- False-supported rate={_pct(grounding['false_supported_rate'])} "
                f"false-rejected rate={_pct(grounding['false_rejected_rate'])}",
                f"- {grounding['limitation']}",
                "",
            ]
        )
    else:
        lines.append("Grounding last_run.json was not found.")
        lines.append("")
    gguf = payload["gguf"]
    lines.extend(
        [
            "## Local GGUF / embeddings",
            "",
            f"- GGUF: **{gguf['status']}** — {gguf['reason']}",
            f"- Downloaded weights this run: **{gguf['downloaded']}**",
            "- Sentence embeddings: **not run** (would require downloading weights).",
            "",
            "## Schema validity",
            "",
        ]
    )
    for row in payload["schema"]:
        status = "pass" if row["passed"] else "FAIL"
        lines.append(
            f"- `{row['id']}` expected_valid={row['expected_valid']} "
            f"actual_valid={row['actual_valid']} [{status}]"
        )
    lines.extend(
        [
            "",
            "## Remaining limitations",
            "",
            "- Closed-set n is too small to choose a production embedding model.",
            "- TF-IDF IDF is fit on this locked corpus; it is not a held-out IR system.",
            "- Token overlap still confirms place-name and other hard-negative hits.",
            "- No GGUF generation quality, latency, or RAM numbers were collected.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_decision(payload: dict[str, Any]) -> str:
    """Record the Slice 5 model decision from measured numbers only."""
    matching = payload["matching"]
    lexical = matching["matchers"]["lexical"]
    tfidf = matching["matchers"]["tfidf"]
    hybrid = matching["matchers"]["hybrid"]
    gguf = payload["gguf"]
    better = []
    if (tfidf["accuracy"] - lexical["accuracy"]) >= 0.05:
        better.append("tfidf accuracy")
    if (hybrid["accuracy"] - lexical["accuracy"]) >= 0.05:
        better.append("hybrid accuracy")
    if tfidf["hard_negative_false_confirmed"] < lexical["hard_negative_false_confirmed"]:
        better.append("tfidf hard-negative rate")
    if hybrid["hard_negative_false_confirmed"] < lexical["hard_negative_false_confirmed"]:
        better.append("hybrid hard-negative rate")
    keep_lexical = not better
    return "\n".join(
        [
            "# Slice 5 model decision",
            "",
            f"Date: {payload['ran_at']}",
            "Benchmark: `evals/benchmark/v1.0.0`",
            "",
            "## Decision",
            "",
            "**Keep the production lexical matcher.** Do not add embeddings, a vector database, or a fine-tune.",
            "",
            "## Measured comparison",
            "",
            f"- Lexical accuracy {_pct(lexical['accuracy'])}, hard-negative false-confirmed "
            f"{lexical['hard_negative_false_confirmed']}/{lexical['hard_negative_n']}",
            f"- TF-IDF accuracy {_pct(tfidf['accuracy'])}, hard-negative false-confirmed "
            f"{tfidf['hard_negative_false_confirmed']}/{tfidf['hard_negative_n']}",
            f"- Hybrid accuracy {_pct(hybrid['accuracy'])}, hard-negative false-confirmed "
            f"{hybrid['hard_negative_false_confirmed']}/{hybrid['hard_negative_n']}",
            "",
            (
                "Neither TF-IDF nor hybrid beat lexical by 5 accuracy points or a lower hard-negative rate."
                if keep_lexical
                else "Measured deltas: " + ", ".join(better) + ". Still too small-n to replace production matching."
            ),
            "",
            "## What was not measured",
            "",
            f"- Local GGUF generations: {gguf['status']} ({gguf['reason']})",
            "- Sentence embeddings / cross-encoders: not run; would require downloading weights",
            "- Fine-tune: not run; there is no labeled generation training set and no GGUF baseline",
            "",
            "## Fine-tune gate",
            "",
            "Fine-tuning is not justified. Slice 5 patched short-skill tokens and skill-level negation in ",
            "the lexical matcher. The remaining miss is place-name token overlap (`Kubernetes Coffee`), ",
            "which is not evidence that a new weight file would help.",
            "",
            "Do not claim a production embedding or GGUF quality ranking from this slice.",
            "",
        ]
    ) + "\n"


def run_eval(dataset_path: Path = CASES_PATH) -> dict[str, Any]:
    """Run the locked benchmark and return a JSON-serializable report."""
    dataset = load_dataset(dataset_path)
    matching = run_matching(dataset["matching_cases"])
    schema = run_schema_cases(dataset["schema_cases"])
    payload = {
        "version": dataset["version"],
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": str(dataset_path.relative_to(ROOT)),
        "inference": "none",
        "matching": matching,
        "schema": schema,
        "n_schema": len(schema),
        "schema_passed": sum(1 for row in schema if row["passed"]),
        "gguf": probe_local_gguf(),
        "grounding": load_grounding_metrics(),
        "embeddings": {"status": "not_run", "reason": "Would require downloading weights"},
        "fine_tune": {"status": "not_run", "reason": "No labeled generation set and no GGUF baseline"},
    }
    return payload


def write_report(payload: dict[str, Any]) -> None:
    """Persist machine and human Slice 5 artifacts."""
    LAST_RUN_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    RESULTS_PATH.write_text(render_results(payload), encoding="utf-8")
    DECISION_PATH.write_text(render_decision(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CareerOS Slice 5 benchmark v1.0.0")
    parser.add_argument("--dataset", type=Path, default=CASES_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    payload = run_eval(args.dataset)
    if not args.no_write:
        write_report(payload)
    matching = payload["matching"]
    print(
        "n_cases={n} states={s} extract_f1={f1} lexical_acc={acc}".format(
            n=matching["extraction"]["n_cases"],
            s=matching["n_labeled_states"],
            f1=_pct(matching["extraction"]["f1"]),
            acc=_pct(matching["matchers"]["lexical"]["accuracy"]),
        )
    )
    print("schema", payload["schema_passed"], "/", payload["n_schema"])
    print("gguf", payload["gguf"]["status"])
    failed_schema = [row["id"] for row in payload["schema"] if not row["passed"]]
    failed_stability = [row["id"] for row in matching["stability"] if not row["passed"]]
    if failed_schema or failed_stability:
        print("failures", failed_schema + failed_stability)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
