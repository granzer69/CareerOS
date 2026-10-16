---
name: careeros-frontend-contract
description: Use when changing CareerOS frontend pages, API client, types, copy, routes, or dist build. Enforces JWT, ResumeAnalysisRead fields, honest score labels, and forbidden placement-predictor language.
---

# CareerOS frontend contract

Read this before editing `frontend/src`, `frontend/scripts`, or `frontend/dist`.

CareerOS is a **signed-in, JD-driven resume copilot**. It is not a placement predictor and not a broad career OS dashboard.

## Stack (do not rewrite)

- Source of truth: `frontend/src`
- Vite 5 + React 18 + TypeScript + react-router-dom
- Build: `npm run build` → `frontend/scripts/prepare-deploy.mjs` writes `frontend/dist`
- Local unified mode: relative `/api` (no `BACKEND_URL`)
- Vercel: HTTPS `BACKEND_URL` injected as `VITE_BACKEND_URL`
- FastAPI serves `frontend/dist` only when `ENVIRONMENT` is not production
- **Never hand-edit `frontend/dist` or minified bundles**

## Auth and API

- JWT in `localStorage` key `careeros_token`
- Every private call goes through `frontend/src/api.ts` `request()` with `Authorization: Bearer`
- 401 clears the token
- Types live in `frontend/src/types.ts` and must match backend Pydantic schemas
- Do not send `user_id` in analyze/history bodies; ownership is the JWT subject

### Routes the UI may call

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`
- `GET /health` (public) — `{ status, database, local_model }`
- `POST /api/v1/resume/analyze` (multipart: `file`, `target_role`, `job_description`)
- `GET /api/v1/resume/analyses`, `GET /api/v1/resume/analyses/{id}`
- `GET /api/v1/resume/analytics` — owner-scoped aggregate (last 100 analyses). Optional `target_role` query filter. Not a hiring probability
- `GET /api/v1/user-profile/me`, `POST|PUT /api/v1/user-profile/{user_id}` — owner-scoped profile
- Edits/versions: `.../edits`, `.../edits/{id}/accept|reject`, `.../versions`, `.../restore-original`

Missing GGUF → analyze still scores from deterministic JD requirements and rubric `v1.0.0`. Edit generation returns 503 `model_unavailable`. Never add Anthropic, OpenAI, Gemini, or any hosted fallback in the UI or client.

## Score field meanings (required copy)

| Field | Meaning |
|---|---|
| `job_fit_score` | How much of the JD is supported by resume evidence |
| `resume_alignment_score` | How clearly the resume communicates verified qualifications |
| `application_readiness_score` | `0.60×fit + 0.35×alignment + 0.05×completeness` (renormalized if completeness unknown) |
| `overall_score` | Same as application-readiness. **Not** P(hire) or P(interview) |
| `ats_score` | Terminology coverage vs the JD. **Not** a vendor ATS result |
| `rubric_version` | Always show when present (currently `v1.0.0`) |
| `blocked_by_requirement` | Eligibility blocker; must not be hidden by the composite score |

Evidence states: `confirmed` | `partial` | `not_found` | `contradicted` | `unknown`.  
Edit kinds: `supported_rewrite` (only kind that can be applied) | `missing_qualification` | `unsupported` | `needs_evidence`.

## Error codes the UI must map

Handle via `actionableMessage` in `api.ts`: `unauthorized`, `invalid_token`, `model_unavailable`, `file_too_large`, `unsupported_media_type`, `empty_resume`, `job_description_required`, `edit_source_stale`, `version_conflict`, `edit_not_acceptable`, `email_exists`, `invalid_credentials`, `schema_outdated`, `not_found`.

Do not show raw stack traces or “Internal server error” as the only copy when a `code` exists.

## Forbidden UI copy (fail the change if present)

- placement probability, chance of getting hired, predicted company
- will get placed; Google, Amazon, Microsoft as recommended employers
- anthropic, openai, gemini as runtime providers
- “Student Placement Prediction”
- labeling `ats_score` as an ATS pass/fail from Workday/Greenhouse/Lever

## Required UX states

Every screen: loading, empty, error, success. Never fabricate scores, companies, or history rows to fill the layout.

## Build checks

After UI copy or client changes:

```bash
cd frontend && npm run build && npx tsc --noEmit
python3 -m pytest tests/test_frontend_source.py tests/test_no_hosted_inference.py -q
```
