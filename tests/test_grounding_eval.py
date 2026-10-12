from __future__ import annotations

import json
from pathlib import Path

from evals.grounding.run import (
    ALLOWED_EXPECTED,
    CASES_PATH,
    load_dataset,
    run_eval,
)

DATASET = load_dataset()


def test_eval_set_is_well_formed() -> None:
    """Every classification case has a unique id and an allowed expected label."""
    ids = [case["id"] for case in DATASET["classification_cases"]]
    assert ids == sorted(set(ids), key=ids.index)
    for case in DATASET["classification_cases"]:
        assert case["expected"] in ALLOWED_EXPECTED
        assert case["original_span"]
        assert case["proposed_text"]
        assert case["family"]
    integrity_ids = [case["id"] for case in DATASET["integrity_cases"]]
    assert len(integrity_ids) == len(set(integrity_ids))


def test_eval_covers_required_families() -> None:
    """The frozen set includes the Slice 4.1 evaluation families requested for review."""
    families = {case["family"] for case in DATASET["classification_cases"]}
    required = {
        "supported_paraphrase",
        "invented_employer",
        "invented_title",
        "invented_responsibility",
        "invented_date",
        "invented_metric",
        "short_skill",
        "ownership_or_intensifier",
        "ambiguous_span",
        "missing_evidence",
        "conflicting_or_negated",
        "adversarial_mixed_facts",
    }
    assert required <= families


def test_integrity_invariants_hold() -> None:
    """Offsets, hashes, overlaps, Unicode, and stale edits stay consistent."""
    payload = run_eval(CASES_PATH)
    failed = [row for row in payload["integrity"] if not row["passed"]]
    assert failed == []


def test_eval_runner_is_deterministic() -> None:
    """Two runs produce identical case outcomes and metrics except the timestamp."""
    first = run_eval(CASES_PATH)
    second = run_eval(CASES_PATH)
    first["ran_at"] = second["ran_at"] = "frozen"
    assert first == second


def test_eval_does_not_touch_hosted_inference() -> None:
    """The eval runner imports only the local grounding classifier."""
    source = Path("evals/grounding/run.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for snippet in ("anthropic", "openai", "gemini", "from_pretrained", "huggingface"):
        assert snippet not in lowered


def test_classification_size_is_recorded() -> None:
    """Exact test-set size is the frozen JSON length, not an implied round number."""
    payload = run_eval(CASES_PATH)
    assert payload["metrics"]["n_classification"] == len(DATASET["classification_cases"])
    assert payload["n_integrity"] == len(DATASET["integrity_cases"])
    assert payload["metrics"]["n_classification"] >= 40


def test_last_run_schema_roundtrip(tmp_path: Path) -> None:
    """The machine report is JSON-serializable and includes expected-versus-actual rows."""
    payload = run_eval(CASES_PATH)
    dump = tmp_path / "last_run.json"
    dump.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(dump.read_text(encoding="utf-8"))
    assert "false_supported" in loaded
    assert "false_rejected" in loaded
    assert len(loaded["classification"]) == payload["metrics"]["n_classification"]
