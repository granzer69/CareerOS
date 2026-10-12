from __future__ import annotations

import json
from pathlib import Path

from evals.benchmark.run import CASES_PATH, load_dataset, run_eval
from evals.benchmark.tfidf import CONFIRMED_THRESHOLD, PARTIAL_THRESHOLD

DATASET = load_dataset()


def test_benchmark_set_is_well_formed() -> None:
    """Locked cases have unique ids, labeled states, and a frozen matcher protocol."""
    ids = [case["id"] for case in DATASET["matching_cases"]]
    assert ids == sorted(set(ids), key=ids.index)
    families = {case["family"] for case in DATASET["matching_cases"]}
    required = {
        "happy_path",
        "paraphrase_stability",
        "format_stability",
        "hard_negative",
        "missing_evidence",
        "eligibility",
        "boilerplate",
        "partial_evidence",
        "short_skill",
    }
    assert required <= families
    for case in DATASET["matching_cases"]:
        assert case["jd"]
        assert "resume" in case
        assert case["expected_requirements"]
        assert isinstance(case["expected_blocked"], bool)


def test_tfidf_thresholds_are_frozen() -> None:
    """TF-IDF cutoffs must stay at the a-priori values in REVIEW.md."""
    assert CONFIRMED_THRESHOLD == 0.50
    assert PARTIAL_THRESHOLD == 0.20


def test_benchmark_runner_is_deterministic() -> None:
    """Two runs produce identical outcomes except the timestamp."""
    first = run_eval(CASES_PATH)
    second = run_eval(CASES_PATH)
    first["ran_at"] = second["ran_at"] = "frozen"
    assert first == second


def test_schema_cases_pass() -> None:
    """Score-bearing payloads are rejected; valid extraction/edit JSON is accepted."""
    payload = run_eval(CASES_PATH)
    assert payload["schema_passed"] == payload["n_schema"]
    assert payload["n_schema"] >= 4


def test_benchmark_does_not_download_weights() -> None:
    """The Slice 5 runner must not fetch hosted models or hub weights."""
    source = Path("evals/benchmark/run.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for snippet in ("anthropic", "openai", "gemini", "from_pretrained", "huggingface", "hf_hub"):
        assert snippet not in lowered
    assert payload_not_downloaded()


def payload_not_downloaded() -> bool:
    payload = run_eval(CASES_PATH)
    return payload["gguf"]["downloaded"] is False and payload["embeddings"]["status"] == "not_run"


def test_matching_size_is_recorded() -> None:
    """Exact n is the frozen JSON length."""
    payload = run_eval(CASES_PATH)
    assert payload["matching"]["extraction"]["n_cases"] == len(DATASET["matching_cases"])
    assert payload["matching"]["extraction"]["n_cases"] >= 12


def test_format_variant_does_not_change_job_fit() -> None:
    """Blank lines around the same resume must not move job-fit."""
    payload = run_eval(CASES_PATH)
    format_rows = [row for row in payload["matching"]["stability"] if row["kind"] == "format"]
    assert format_rows
    assert all(row["passed"] and row["delta_job_fit"] == 0 for row in format_rows)


def test_last_run_schema_roundtrip(tmp_path: Path) -> None:
    """The machine report remains JSON-serializable."""
    payload = run_eval(CASES_PATH)
    dump = tmp_path / "last_run.json"
    dump.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(dump.read_text(encoding="utf-8"))
    assert "matchers" in loaded["matching"]
    assert set(loaded["matching"]["matchers"]) == {"lexical", "tfidf", "hybrid"}
