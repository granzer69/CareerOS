# CareerOS

FastAPI + React platform for **resume analysis**, JWT auth, user profiles, and PostgreSQL persistence. Resume analysis uses a **local GGUF model** through a small inference adapter — not a hosted LLM API.

> Honest scope: this is a working resume-analysis product surface (auth, profiles, local-model analysis, deploy configs). It is **not** a fully autonomous job-application system. For phased job discovery / match orchestration, see [Range-Apply](https://github.com/granzer69/Range-Apply).

## Overview

CareerOS helps a user upload a resume, choose a target role, and receive a validated analysis payload from a local model. Profiles and analysis rows are stored in Postgres (SQLite usable locally). A static React frontend talks to the API; Render + Vercel deploy configs are included.

`POST /api/v1/resume/analyze`, `GET /api/v1/resume/analyses`, and `GET /api/v1/resume/analyses/{id}` require a Bearer JWT. Analyses are stored under the token subject. Legacy rows with a NULL `user_id` are not listed or readable. The checked-in static frontend bundle does not send a token, so analyze will return 401 until the frontend is rebuilt from source.

If `LOCAL_MODEL_PATH` is unset or the weight file is missing, analyze returns HTTP 503 `model_unavailable` and does not call a hosted provider.

## Architecture

```text
React frontend  →  FastAPI (JWT)  →  PostgreSQL
                         │
                         ├─ resume parse (PDF/DOCX)
                         └─ local GGUF adapter → ResumeAnalysisResult (Pydantic)
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
- User profile CRUD (write paths)
- Resume upload → text extraction → local-model analysis → persisted `resume_analyses` owned by the authenticated user
- User-scoped analysis history (`GET /api/v1/resume/analyses` and `GET /api/v1/resume/analyses/{id}`)
- Health endpoint and CORS configuration for split frontend/backend deploy
- Alembic migrations for users, profiles, resume analyses
- Unit / integration tests for auth and profile flows
- Deployment scripts and verify helpers

## Partially implemented / stubbed

- **Roadmap API** (`/roadmap`) returns a placeholder `"coming soon"` response
- Broader “career OS / autonomous apply” ambitions live primarily in **Range-Apply**, not here

## Key engineering decisions

- **Local inference only**: no Anthropic/OpenAI/Gemini keys or cloud fallback in the runtime
- **Missing weights fail closed**: analyze returns 503; `/health` and auth keep running
- **Structured model output**: response is parsed as JSON and validated with Pydantic; malformed JSON triggers a bounded retry
- **Prompt as file**: analysis prompt kept under `app/ai/prompts/` for inspectability
- **Migrations first**: schema changes via Alembic rather than ad-hoc create-all in production paths
- **Split deploy**: API on Render, frontend on Vercel, with explicit `ALLOWED_ORIGINS` / `BACKEND_URL`

## Getting started

1. Copy `.env.example` → `.env` (set DB URL, JWT secret, CORS origins).
2. `pip install -r requirements.txt`
3. `alembic upgrade head`
4. Optional, only on a machine that will run analysis:
   - download a GGUF **outside** the request path
   - `pip install -r requirements-local-inference.txt`
   - set `LOCAL_MODEL_PATH` to that file
5. `uvicorn app.main:app --reload`
6. In `frontend`: set `BACKEND_URL`, then `npm run build`

If `LOCAL_MODEL_PATH` is empty, the API still boots. Analyze returns `{"detail": {"detail": "Local model weights are not available", "code": "model_unavailable"}}`.

The default Render free instance does not have enough RAM for a GGUF. Leave `LOCAL_MODEL_PATH` empty there, or run inference on a host that can hold the file.

### Deploy notes

- **Render**: build `pip install -r requirements-prod.txt`, pre-deploy `alembic upgrade head`, start `bash scripts/start.sh`, health `/health`
- **Vercel**: root `frontend`, build `npm run build`, env `BACKEND_URL=https://<render-service>.onrender.com`

## Testing

```bash
pytest tests/ -q
python3 -m alembic heads
```

CI and default `pytest` mock the local adapter and must not download weights.

## Future improvements

- JD-driven scoring and evidence-grounded resume edits
- Flesh out roadmap / career-planning endpoints
- Tighten production observability and rate limits
- Clearer separation docs vs Range-Apply product surface

## License / status

Active personal / educational project. Treat autonomous job submission as **out of scope** for this repository.
