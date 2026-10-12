# Pipeline benchmark RESULTS v1.0.0

Ran: 2026-10-12T07:30:18Z
Dataset: `evals/benchmark/v1.0.0/cases.json`
Inference: none. Embeddings: not run. GGUF generations: not run. Downloads: none.

## Test-set size

- Matching/extraction cases: **14**
- Labeled evidence states: **32**
- Schema cases: **4** (passed 4)

n is too small for production ML claims. This is a locked regression fixture.

## Requirement extraction (deterministic splitter)

- Precision: **100.0%**
- Recall: **100.0%**
- F1: **100.0%**
- tp=32 fp=0 fn=0

## Evidence-state agreement

### lexical

- Accuracy: **96.9%**
- Macro-F1 (states with support): **98.4%**
- Hard-negative false-confirmed: **1/3**

### tfidf

- Accuracy: **46.9%**
- Macro-F1 (states with support): **61.0%**
- Hard-negative false-confirmed: **0/3**

### hybrid

- Accuracy: **96.9%**
- Macro-F1 (states with support): **98.4%**
- Hard-negative false-confirmed: **1/3**

## Score stability (lexical rubric v1.0.0)

- `paraphrase-python-fastapi` vs `happy-python-fastapi` (paraphrase): Δ job-fit 0 (limit 5) [pass]
- `format-python-fastapi` vs `happy-python-fastapi` (format): Δ job-fit 0 (limit 0) [pass]

Eligibility blocker accuracy: **100.0%**

## Hard-negative false confirms

- `hardneg-k8s-cafe` key `kubernetes` matcher `lexical` → `confirmed`
- `hardneg-k8s-cafe` key `kubernetes` matcher `hybrid` → `confirmed`

## Grounding (imported from Slice 4.1)

- Dataset: `evals/grounding/v1.0.0/cases.json`
- n=55 precision=73.3% recall=100.0%
- False-supported rate=9.1% false-rejected rate=0.0%
- n is too small for production-level factual guarantees. These are lexical regression tests, not semantic entailment.

## Local GGUF / embeddings

- GGUF: **not_measured** — LOCAL_MODEL_PATH is unset
- Downloaded weights this run: **False**
- Sentence embeddings: **not run** (would require downloading weights).

## Schema validity

- `extract-valid` expected_valid=True actual_valid=True [pass]
- `extract-rejects-score` expected_valid=False actual_valid=False [pass]
- `edit-valid` expected_valid=True actual_valid=True [pass]
- `edit-rejects-score` expected_valid=False actual_valid=False [pass]

## Remaining limitations

- Closed-set n is too small to choose a production embedding model.
- TF-IDF IDF is fit on this locked corpus; it is not a held-out IR system.
- Token overlap still confirms place-name and other hard-negative hits.
- No GGUF generation quality, latency, or RAM numbers were collected.

