# CareerOS

FastAPI + React platform for **resume analysis**, JWT auth, user profiles, and PostgreSQL persistence. Resume analysis uses a **local GGUF model** through a small inference adapter — not a hosted LLM API.

> Honest scope: this is a working resume-analysis product surface (auth, profiles, local-model analysis, deploy configs). It is **not** a fully autonomous job-application system. For phased job discovery / match orchestration, see [Range-Apply](https://github.com/granzer69/Range-Apply).

## Overview

CareerOS helps a user upload a resume, paste a job description, and receive three versioned scores: **job-fit**, **resume-alignment**, and **application-readiness**. A local GGUF model may extract extra JD requirements or propose span rewrites; it does not invent the final numbers. Profiles, analyses, edit suggestions, and accepted resume versions are stored in Postgres (SQLite usable locally). A static React frontend talks to the API; Render + Vercel deploy configs are included.

`POST /api/v1/resume/analyze` requires a Bearer JWT, a resume file, `target_role`, and `job_description`. Analyses are stored under the token subject. History, edits, and versions are owner-scoped. Legacy rows with a NULL `user_id` are not listed or readable. The frontend source in `frontend/src` is a signed-in campus resume studio: register/login, upload a resume, paste a JD, inspect evidence and scores, review grounded edits, and read owner-scoped analytics. Build it with `npm run build` in `frontend/`. Do not hand-edit `frontend/dist`.

If `LOCAL_MODEL_PATH` is unset or the weight file is missing, analyze still returns rubric scores from deterministic JD requirements and lexical evidence matching. Edit generation returns HTTP 503 `model_unavailable`. The API does not call a hosted provider.

## Architecture

```text
React frontend  →  FastAPI (JWT)  →  PostgreSQL
                         │
                         ├─ resume parse (PDF/DOCX)
                         ├─ deterministic JD split + evidence match + rubric v1.0.0
                         ├─ evidence-grounded edit proposals + accepted resume versions
                         └─ local GGUF adapter → ModelExtraction / ModelEditBatch (no scores)
```

## Tech stack

| Layer | Tech (in repo) |
|------|----------------|
| API | FastAPI, Uvicorn, Pydantic Settings |
| Auth | JWT (`python-jose`) |
| DB | SQLAlchemy, Alembic, asyncpg / aiosqlite |
| AI | Local GGUF via `llama-cpp-python` (optional extra), prompt template + JSON validation with retry |
| Resume I/O | PyPDF2, python-docx |
| Frontend | React (Vite build), deploy via Vercel |
| Deploy | Render (`render.yaml`), Vercel (`frontend/vercel.json`) |
| Tests | pytest (local adapter is mocked; no weights required) |

Also listed in requirements (available for extension): ChromaDB, Redis — not required for the core resume-analysis path described above.

## Implemented features

- User registration / login with JWT
- User profile create/update and `GET /api/v1/user-profile/me` (owner-scoped)
- Resume upload + job description → text extraction → local-model requirement extraction → deterministic evidence match (including short skills such as Go, R, and C++) and rubric scoring → persisted `resume_analyses` owned by the authenticated user
- User-scoped analysis history (`GET /api/v1/resume/analyses` and `GET /api/v1/resume/analyses/{id}`)
- Owner-scoped analytics (`GET /api/v1/resume/analytics`) — evidence mix, mandatory gaps, score trends, edit funnel, version lift, requirement coverage, eligibility rollups, and profile-skill vs JD mention counts for the caller’s last 100 analyses. Optional `target_role` filter. Not a hiring probability or cross-user benchmark
- Evidence-grounded edit proposals (`POST/GET /api/v1/resume/analyses/{id}/edits`) with accept/reject. Original resume text is immutable. Each batch is bound to the current version content hash. Accepted supported rewrites create a `resume_versions` row that is re-scored with rubric `v1.0.0`. Stale or concurrent accepts return 409. Owner-only version detail includes `resume_text` so the working copy can be reviewed; analysis GET and version list omit it. `POST .../restore-original` and `POST .../versions/{id}/restore` create a new version without rewriting history.
- Health endpoint and CORS configuration for split frontend/backend deploy
- Alembic migrations for users, profiles, resume analyses
- Unit / integration tests for auth and profile flows
- Deployment scripts and verify helpers

## Partially implemented / stubbed

- **Roadmap API** (`/roadmap`) returns a placeholder `"coming soon"` response
- Broader “career OS / autonomous apply” ambitions live primarily in **Range-Apply**, not here

## Key engineering decisions

- **Local inference only**: no Anthropic/OpenAI/Gemini keys or cloud fallback in the runtime
- **Missing weights degrade safely**: analyze uses deterministic JD parsing and lexical matching (no hosted LLM); edit generation returns 503 `model_unavailable`; `/health` and auth keep running
- **Structured model output**: extraction JSON is validated with Pydantic (`extra=forbid`); numeric scores are rejected; malformed JSON triggers a bounded retry
- **Deterministic scoring**: job-fit, alignment, and readiness come from rubric `v1.0.0`; `overall_score` is application-readiness; `ats_score` is terminology coverage, not a vendor ATS
- **Prompt as file**: extraction and edit prompts kept under `app/ai/prompts/` for inspectability
- **Evidence-grounded edits**: `supported_rewrite` requires unique source offsets and attested employers, titles, responsibilities, dates, metrics, and short skills (including Go, R, C++). Unverifiable claims are `needs_evidence` or `unsupported`. The local model cannot override classification or scores.
- **Version integrity**: edits are generated against the current snapshot, not always the original upload. Pending batches are preserved. Offset replacement is used instead of first-occurrence `find`.
- **Migrations first**: schema changes via Alembic rather than ad-hoc create-all in production paths
- **Split deploy**: API on Render, frontend on Vercel, with explicit `ALLOWED_ORIGINS` / `BACKEND_URL`

## Getting started

1. Copy `.env.example` → `.env` (set DB URL, JWT secret, CORS origins).
2. `pip install -r requirements.txt`
3. PostgreSQL: `alembic upgrade head`. Local sqlite: `python scripts/init_db.py` (Alembic revisions use Postgres types such as JSONB).
4. Optional, only on a machine that will run analysis:
   - download a GGUF **outside** the request path
   - `pip install -r requirements-local-inference.txt`
   - set `LOCAL_MODEL_PATH` to that file
   - optional: `LOCAL_MODEL_PATH_JD` and `LOCAL_MODEL_PATH_EVIDENCE` for separate GGUF files (JD understanding + extraction vs semantic evidence matching). When unset, every stage uses `LOCAL_MODEL_PATH`.
5. `uvicorn app.main:app --reload`

Analysis runs three local stages when weights are present: (1) infer JD objectives, (2) extract requirements in that context, (3) judge resume evidence semantically (not keyword overlap). Lexical matching is used only when understanding or inference is unavailable.
6. In `frontend`: `npm install && npm run build` (relative `/api` for local unified mode). For Vercel, set `BACKEND_URL` to the HTTPS API before `npm run build`.

If `LOCAL_MODEL_PATH` is empty, the API still boots. Analyze scores the resume from deterministic JD requirements and rubric `v1.0.0`. Edit generation returns `{"detail": {"detail": "Local model weights are not available", "code": "model_unavailable"}}`.

If local sqlite was created before the current Alembic head, `alembic upgrade head` can fail with “table already exists” and history can return 503 `schema_outdated`. Delete the leftover `.db` file and run the upgrade again. `create_all` does not add columns such as `resume_analyses.user_id`.

The default Render free instance does not have enough RAM for a GGUF. Leave `LOCAL_MODEL_PATH` empty there, or run inference on a host that can hold the file.

### Deploy notes

- **Render**: build `pip install -r requirements-prod.txt`, pre-deploy `alembic upgrade head`, start `bash scripts/start.sh`, health `/health`
- **Vercel API** (when the API is not on Render): framework FastAPI, repository root, `ENVIRONMENT=production`, `RUN_MIGRATIONS=true`, Postgres `DATABASE_URL`, `ALLOWED_ORIGINS=https://<frontend-host>`. Leave `LOCAL_MODEL_PATH` empty unless that host can hold a GGUF file.
- **Vercel UI**: root `frontend`, build `npm run build`, env `BACKEND_URL=https://<api-host>`

## Testing

```bash
pytest tests/ -q
python3 -m alembic heads
```

CI and default `pytest` mock the local adapter and must not download weights.

Grounding is fail-closed lexical/pattern matching, not a semantic entailment model. The frozen Slice 4.1 set lives at `evals/grounding/v1.0.0/` (`n=55`). Run `PYTHONPATH=. python evals/grounding/run.py`. Those tests do not prove the rewriter never invents a fact in production.

The Slice 5 pipeline benchmark lives at `evals/benchmark/v1.0.0/` (`n=14` matching cases). Run `PYTHONPATH=. python evals/benchmark/run.py`. It compares lexical vs TF-IDF vs hybrid matching, checks rubric stability and schema validity, and records a model decision. It does not download embedding or GGUF weights. Fine-tuning is not justified from this set.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for shipped slices, CI/deploy next steps, and future work (mobile UI, overall UX, JD understanding).

## Future improvements

- Flesh out roadmap / career-planning endpoints
- Tighten production observability and rate limits
- Clearer separation docs vs Range-Apply product surface

## License / status

Active personal / educational project. Treat autonomous job submission as **out of scope** for this repository.
