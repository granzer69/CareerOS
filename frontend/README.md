# CareerOS frontend

Signed-in campus resume studio — JD-driven copilot plus owner-scoped analytics. Source of truth is `src/`. Do not hand-edit `dist/`.

## Local development

```bash
npm install
npm run dev
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`. Sign in, upload a PDF/DOCX, paste a job description, and read rubric scores. Missing GGUF weights show as `model_unavailable`; the UI does not call a hosted LLM.

To refresh the bundle FastAPI serves in non-production:

```bash
npm run build
```

That writes `frontend/dist` with relative `/api` URLs.

```bash
npm test
npx tsc --noEmit
npm run test:e2e   # needs the API on 127.0.0.1:8000
```

## Vercel

Set `BACKEND_URL` to the public HTTPS API (Render). `npm run build` (via `scripts/prepare-deploy.mjs`) injects `VITE_BACKEND_URL` and copies `dist` to `build`. Then `npm run verify`.
