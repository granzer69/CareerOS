---
name: careeros-production-frontend
description: Use when preparing CareerOS frontend for deploy, daily users, Vercel/Render split, CORS, JWT session handling, caching, or production hardening. No Mixpanel/hosted LLM by default.
---

# CareerOS production frontend

The copilot is meant to be **deployed and used every day**. Harden the existing Vite + React app. Do not rewrite it as Next.js or add a marketing site.

Read `careeros-frontend-contract` and `careeros-telemetry` first.

## Split deploy (default)

| Piece | Where | Rule |
|---|---|---|
| API | Render (or any HTTPS FastAPI host) | `ENVIRONMENT=production`, strong `SECRET_KEY`, explicit `ALLOWED_ORIGINS` |
| UI | Vercel, `frontend/` as root | `BACKEND_URL=https://<api-host>` injected as `VITE_BACKEND_URL` |
| Local unified | FastAPI serves `frontend/dist` | relative `/api` — do not set `BACKEND_URL` |

Never ship a mixed origin (`http` UI talking to `https` API, or `*` CORS). Production settings already reject wildcard origins and short secrets.

## Daily-user path

1. JWT in `localStorage` key `careeros_token`. 401 clears it and returns the user to `/login`
2. One health fetch per shell mount. Persist **missing GGUF** as a warn banner; do not flash a success banner on every visit
3. Analyze is a single multipart POST. History is one list GET. Analytics is **one** aggregate GET (`/api/v1/resume/analytics`) — do not N+1 every analysis to draw charts
4. Actionable errors for `model_unavailable`, `schema_outdated`, `file_too_large`, session expiry
5. Rebuild `frontend/dist` from source (`npm run build`). Never patch minified bundles

## What not to add for “scale”

- Mixpanel / PostHog / GA **by default**. Product telemetry is opt-in (`careeros-telemetry`) and must never send resume or JD text
- Hosted LLM fallback when GGUF is missing
- Client-side score invention while the API is 503
- Service workers that cache authenticated JSON without a plan
- Chart libraries plus Chart.js together; native SVG + a table is enough until Recharts is justified

## Performance and payload

- Analytics is capped at 100 owned rows server-side. Do not request resume_text on list, analytics, or analysis GET
- Keep the JS bundle to the signed-in copilot; code-split only if a new heavy dependency lands
- Images: none required. If you add a mark, inline SVG
- `prefers-reduced-motion` already disables animation

## Observability (first-party)

Log on the API: status, `code`, latency, whether `LOCAL_MODEL_PATH` exists, rubric version. Do not log `resume_text`, JD paste, or tokens. Frontend may show `/health.local_model`. That is enough until consented telemetry exists.

## Checklist before a production frontend change

- `npx tsc --noEmit` and `npm run build` in `frontend/`
- `python3 -m pytest tests/test_frontend_source.py tests/test_cors.py tests/test_no_hosted_inference.py -q`
- Confirm `BACKEND_URL` is HTTPS in Vercel and listed in `ALLOWED_ORIGINS`
- Confirm missing GGUF is a 503 the UI can explain, not a blank page
