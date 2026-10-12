# Grounding evaluation RESULTS v1.0.0

Ran: 2026-10-12T06:56:54Z
Dataset: `evals/grounding/v1.0.0/cases.json`
Classifier: `app.services.edit_grounding.classify_proposal`
Inference: none (no hosted APIs, no weight downloads).

## Metrics (supported_rewrite as the positive / apply class)

- Test-set size (classification): **55**
- Integrity cases: **18** (passed 18)
- Precision: **73.3%**
- Recall: **100.0%**
- False-supported rate: **9.1%** (4/44)
- False-rejected rate: **0.0%** (0/11)
- Exact 3-way label agreement (after mapping missing_qualification → needs_evidence): **89.1%**

## Unpatched baseline (same frozen set, before tokenizer/negation patches)

- Precision: **60.0%**
- Recall: **54.5%**
- False-supported rate: **9.1%** (4/44)
- False-rejected rate: **45.5%** (5/11)
- Integrity: 16/18

Patches applied after this baseline: strip sentence-final periods from tokens and proper nouns; treat `as`/`by`/`is` as glue; ignore tokens that appear only in negated clauses; classify unbound not-found requirements before extra-content.

n is too small for production-level factual guarantees. These are lexical regression tests, not semantic entailment.

## Confusion (expected → actual, mapped)

```
{
  "needs_evidence": {
    "needs_evidence": 9,
    "unsupported": 2
  },
  "supported_rewrite": {
    "supported_rewrite": 11
  },
  "unsupported": {
    "supported_rewrite": 4,
    "unsupported": 29
  }
}
```

## False-supported (unsafe apply)

- `title-mix-attested` [adversarial_mixed_facts] expected `unsupported`, actual `supported_rewrite` — eval
- `date-inverted` [adversarial_mixed_facts] expected `unsupported`, actual `supported_rewrite` — eval
- `metric-reattribute` [adversarial_mixed_facts] expected `unsupported`, actual `supported_rewrite` — eval
- `metric-employer-swap` [adversarial_mixed_facts] expected `unsupported`, actual `supported_rewrite` — eval

## False-rejected (safe paraphrase blocked)

None.

## Other 3-way mismatches (still correctly not applied)

- `int-10x` [ownership_or_intensifier] expected `needs_evidence`, actual `unsupported` (raw `unsupported`) — Fabricated metric(s) are not present in the resume: 10
- `syn-built-created` [ownership_or_intensifier] expected `needs_evidence`, actual `unsupported` (raw `unsupported`) — Invented responsibility or achievement is not present in the resume: created

## Integrity failures

None. Offset, hash, overlap, Unicode, and stale-edit checks passed.

## Remaining limitations

- Bag-of-tokens grounding cannot prove semantic entailment.
- Mixing attested employers, titles, dates, and metrics can still look supported.
- Near-synonyms (built/created) are lexical misses, not NLI.
- Negation handling is clause-window lexical stripping, not semantic scope.
- Do not treat these percentages as production factual guarantees.

