---
name: careeros-honest-analytics
description: Use when adding CareerOS dashboards, charts, insights, KPIs, heatmaps, trends, or any analytics UI. Defines allowed metrics, required labels, and chart implementation rules. Forbids hiring-probability and fake ATS analytics.
---

# CareerOS honest analytics

Analytics here explain **this user’s evidence, scores, and versions** under a named rubric. They do not predict hiring.

Read `careeros-frontend-contract` first. If a requested chart cannot be sourced from the API (or a new owner-scoped aggregate you also implement), refuse the chart rather than inventing series.

## Allowed metrics

From one analysis (`ResumeAnalysisRead` / version read):

- `job_fit_score`, `resume_alignment_score`, `application_readiness_score` / `overall_score`, `ats_score` (labeled **terminology coverage**)
- Counts of `requirement_matches` by `evidence_state` and `importance`
- Eligibility items and `blocked_by_requirement`
- `keywords_missing`
- Edit mix by `kind` and `status`
- Version scores vs original (same `rubric_version`)

From the user’s history (list + details, or a future aggregate endpoint):

- Analyses over time (readiness / fit / alignment)
- Coverage heatmap: requirements × evidence state, grouped by `target_role`
- Mandatory `not_found` + `contradicted` counts (gaps)
- Edit accept rate for `supported_rewrite` only

Ops (internal, not candidate-facing “career insights”):

- `/health.local_model`
- Analyze 401/503 rates, latency — only with consented product telemetry (`careeros-telemetry`)

## Forbidden metrics

- P(hire), P(interview), placement probability, “chance of getting hired”
- Predicted company, recruiter likelihood, salary prediction
- Vendor ATS pass/fail, Workday/Greenhouse scores
- Benchmarks against other users unless a documented, consented, aggregated product exists
- Model “confidence” that is not in the API
- Interpolated scores for analyses that have null rubric fields

## Required chart chrome

Every chart or KPI tile must show:

1. Metric name in plain language
2. Definition (one sentence)
3. `rubric_version` (or “rubric unknown”)
4. n (number of analyses or requirements)
5. Empty state if n = 0
6. Timezone/date for trends (`created_at`)

Color is never the only encoding (see `frontend-a11y`).

## Implementation

- Library: Recharts or Visx, lazy-loaded; do not add Chart.js + Recharts together
- Data: typed objects from `frontend/src/types.ts`; fetch via `request()`
- New aggregates: backend service + Pydantic schema + owner-scoped route + Alembic if stored + pytest, then UI
- Loading skeleton → empty copy → error banner using `actionableMessage`
- Tooltips quote `rationale` / `evidence_state` / version number when those exist
- Do not default-null to 0 on a line chart; gap or omit the point and say scores are missing

## Page placement

- Default product remains Analyze / History / report
- Analytics is a signed-in route, e.g. `/analytics`, not a public marketing dashboard
- Do not replace the copilot with a “career OS” widget grid

## Copy examples

- Good: “Job-fit 62 · 8/14 JD requirements have confirmed evidence · rubric v1.0.0”
- Bad: “You are 62% likely to get this job”

## Tests

Forbidden-phrase scan must still pass. Add a fixture-driven test that a chart renders `not_found` counts from fixture JSON and an empty state when `requirement_matches` is `[]`.
