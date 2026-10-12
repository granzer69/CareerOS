# Grounding evaluation set v1.0.0

Labeled against the Slice 4.1 product rules, **not** against `classify_proposal` output.

## Label protocol

- `supported_rewrite`: the original span is uniquely identifiable, and every factual claim in the proposal is attested in the source resume (employer, title, responsibility, date, metric, qualification, short skill). Reordering and function-word changes that preserve meaning are allowed.
- `needs_evidence`: the proposal is not a safe apply. Intensifiers, ownership upgrades, ambiguous repeated spans, or missing qualifications that the candidate must still prove.
- `unsupported`: the proposal invents or contradicts a fact. Includes adversarial phrasing that avoids obvious employer/title/metric/JD-missing-token patterns.

`missing_qualification` from the implementation is scored as agreement with expected `needs_evidence` (both mean: do not apply as a rewrite).

## What this set is not

It is a frozen regression fixture, not a statistically powered production audit. It does not establish semantic entailment. A later human review pass should expand adversarial paraphrases before treating grounding as complete.

## How to run

From the repo root, with no network and no model weights:

```bash
PYTHONPATH=. python evals/grounding/run.py
```

This writes `evals/grounding/v1.0.0/last_run.json` and `evals/grounding/v1.0.0/RESULTS.md`.

Integrity cases are asserted in `tests/test_grounding_eval.py`. Classification precision is reported, not gated at 1.0.

## Scoring

Positive class is `supported_rewrite` (safe to apply).

- False-supported: expected reject, actual `supported_rewrite`
- False-rejected: expected `supported_rewrite`, actual reject
- `missing_qualification` maps to `needs_evidence` for agreement
- Reject-bucket swaps (`needs_evidence` vs `unsupported`) are listed separately and do not count as false-supported or false-rejected
