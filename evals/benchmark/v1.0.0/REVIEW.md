# Pipeline benchmark v1.0.0

Locked test split for Slice 5. Labels follow the scoring and matching specs, **not** matcher output.

## What is measured

- Deterministic JD requirement extraction vs labeled keys
- Evidence-state agreement for lexical, TF-IDF, and hybrid matchers
- Hard-negative false-confirmed rate (JD tokens present without skill evidence)
- Rubric v1.0.0 score stability on paraphrases and format-only variants
- Pydantic schema validity for extraction and edit payloads
- Grounding unsupported-claim rate from `evals/grounding/v1.0.0` (imported, not re-labeled)

## What is not measured

- Local GGUF quality, latency, or RAM (no weight file is present; none is downloaded)
- Sentence embeddings or cross-encoders (would require downloading weights)
- Fine-tuning (no generation-labeled training set, no GGUF baseline)

## Label protocol

- `confirmed`: the resume demonstrates the requirement, not merely repeating a token in an unrelated context
- `partial`: related terms exist but the requirement is incomplete
- `not_found`: not demonstrated
- `contradicted`: resume language conflicts
- `unknown`: boilerplate or too generic to score

Hard negatives: a JD keyword that appears as a place, title-of-a-blog, or negated mention is **not** confirmed skill evidence.

## Baselines (frozen a priori)

- **Lexical**: production `match_requirement` (token overlap + negation)
- **TF-IDF**: cosine of requirement vs resume; IDF fit on this locked corpus only
  - confirmed if cosine >= 0.50
  - partial if cosine >= 0.20
  - else not_found
  - same negation rule as lexical
- **Hybrid**: keep lexical `contradicted`/`unknown`/`confirmed`; if lexical `not_found` or `partial`, promote when TF-IDF is higher-confidence

Thresholds were not tuned on this split after seeing scores.

## Scoring

n is too small for production ML claims. Results are a closed-set regression fixture.
