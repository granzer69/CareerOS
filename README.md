# CareerOS

FastAPI + React platform for **resume analysis**, JWT auth, user profiles, and PostgreSQL persistence — with Anthropic Claude producing structured analysis results.

> Honest scope: this is a working resume-analysis product surface (auth, profiles, Claude analysis, deploy configs). It is **not** a fully autonomous job-application system. For phased job discovery / match orchestration, see [Range-Apply](https://github.com/granzer69/Range-Apply).

## Overview

CareerOS helps a signed-in user upload a resume, choose a target role, and receive a validated analysis payload from Claude. Profiles and analysis history are stored in Postgres (SQLite usable locally). A static React frontend talks to the API; Render + Vercel deploy configs are included.

## Architecture

```text
React frontend  →  FastAPI (JWT)  →  PostgreSQL
                         │
                         ├─ resume parse (PDF/DOCX)
                         └─ Anthropic Claude → ResumeAnalysisResult (Pydantic)
```

## Tech stack

| Layer | Tech (in repo) |
|------|----------------|
| API | FastAPI, Uvicorn, Pydantic Settings |
| Auth | JWT (`python-jose`) |
| DB | SQLAlchemy, Alembic, asyncpg / aiosqlite |
| AI | Anthropic Claude (`claude-sonnet-4-20250514`), prompt template + JSON validation with retry |
| Resume I/O | PyPDF2, python-docx |
| Frontend | React (Vite build), deploy via Vercel |
| Deploy | Render (`render.yaml`), Vercel (`frontend/vercel.json`) |
| Tests | pytest |

Also listed in requirements (available for extension): ChromaDB, Redis — not required for the core resume-analysis path described above.

## Implemented features

- User registration / login with JWT
- User profile CRUD
- Resume upload → text extraction → Claude analysis → persisted `resume_analyses`
- Health endpoint and CORS configuration for split frontend/backend deploy
- Alembic migrations for users, profiles, resume analyses
- Unit / integration tests for auth and profile flows
- Deployment scripts and verify helpers

## Partially implemented / stubbed

- **Roadmap API** (`/roadmap`) returns a placeholder `"coming soon"` response
- Broader “career OS / autonomous apply” ambitions live primarily in **Range-Apply**, not here

## Key engineering decisions

- **Structured LLM output**: Claude response is parsed as JSON and validated with Pydantic; malformed JSON triggers a bounded retry
- **Prompt as file**: analysis prompt kept under `app/ai/prompts/` for inspectability
- **Migrations first**: schema changes via Alembic rather than ad-hoc create-all in production paths
- **Split deploy**: API on Render, frontend on Vercel, with explicit `ALLOWED_ORIGINS` / `BACKEND_URL`

## Getting started

1. Copy `.env.example` → `.env` (set `ANTHROPIC_API_KEY`, DB URL, JWT secret, CORS origins).
2. `pip install -r requirements.txt`
3. `alembic upgrade head`
4. `uvicorn app.main:app --reload`
5. In `frontend`: set `BACKEND_URL`, then `npm run build`

### Deploy notes

- **Render**: build `pip install -r requirements-prod.txt`, pre-deploy `alembic upgrade head`, start `bash scripts/start.sh`, health `/health`
- **Vercel**: root `frontend`, build `npm run build`, env `BACKEND_URL=https://<render-service>.onrender.com`

## Testing

```bash
pytest
alembic heads
cd frontend && npm run build && npm run verify
```

## Future improvements

- Flesh out roadmap / career-planning endpoints
- Tighten production observability and rate limits
- Clearer separation docs vs Range-Apply product surface

## License / status

Active personal / educational project. Treat autonomous job submission as **out of scope** for this repository.
