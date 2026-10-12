# Slice 5 model decision

Date: 2026-10-12T07:30:18Z
Benchmark: `evals/benchmark/v1.0.0`

## Decision

**Keep the production lexical matcher.** Do not add embeddings, a vector database, or a fine-tune.

## Measured comparison

- Lexical accuracy 96.9%, hard-negative false-confirmed 1/3
- TF-IDF accuracy 46.9%, hard-negative false-confirmed 0/3
- Hybrid accuracy 96.9%, hard-negative false-confirmed 1/3

Measured deltas: tfidf hard-negative rate. Still too small-n to replace production matching.

## What was not measured

- Local GGUF generations: not_measured (LOCAL_MODEL_PATH is unset)
- Sentence embeddings / cross-encoders: not run; would require downloading weights
- Fine-tune: not run; there is no labeled generation training set and no GGUF baseline

## Fine-tune gate

Fine-tuning is not justified. Slice 5 patched short-skill tokens and skill-level negation in 
the lexical matcher. The remaining miss is place-name token overlap (`Kubernetes Coffee`), 
which is not evidence that a new weight file would help.

Do not claim a production embedding or GGUF quality ranking from this slice.

