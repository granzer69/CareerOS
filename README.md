# CareerOS

CareerOS is a FastAPI backend with a static React frontend for resume analysis,
JWT authentication, user profiles, PostgreSQL persistence, and Anthropic Claude.

## Local development

1. Copy `.env.example` to `.env` and use the local override values.
2. Install backend dependencies with `pip install -r requirements.txt`.
3. Run migrations with `alembic upgrade head`.
4. Start the API with `uvicorn app.main:app --reload`.
5. In `frontend`, set `BACKEND_URL` and run `npm run build`.

## Render backend

- Root directory: `.`
- Build command: `pip install -r requirements-prod.txt`
- Pre-deploy command: `alembic upgrade head`
- Start command: `bash scripts/start.sh`
- Health check: `/health`

Required environment variables are documented in `.env.example`.

## Vercel frontend

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `build`
- Environment variable: `BACKEND_URL=https://<render-service>.onrender.com`

After Vercel assigns the production domain, set the backend
`ALLOWED_ORIGINS` value to that exact HTTPS origin and redeploy Render.

## Verification

Run:

```bash
pytest
alembic heads
cd frontend
npm run build
npm run verify
```
