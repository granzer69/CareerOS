---
name: frontend-test
description: Use when writing or changing CareerOS frontend tests (Vitest, Testing Library, Playwright) or after UI/API-client changes. Complements the pytest test-writer skill, which must not be used for React.
---

# CareerOS frontend tests

The repo skill `test-writer` is **pytest-only**. For `frontend/**` you write frontend tests, not Python, and not implementation code unless the user asked for both.

## Layers

1. **Unit / component** — Vitest + React Testing Library against `frontend/src`
2. **Contract** — `tests/test_frontend_source.py` already forbids dishonest copy and requires Bearer + rubric fields; keep it green
3. **E2E** — Playwright against Vite or the FastAPI-served `frontend/dist` (prefer the unified local mode)

Do not call a real GGUF, hosted LLM, or production API from tests. Mock `fetch` / MSW, or run the FastAPI TestClient/local server with missing weights (503 `model_unavailable` is a valid assertion).

## File naming

- Component: `frontend/src/**/__tests__/<Name>.test.tsx` or `frontend/src/**/*.test.tsx`
- E2E: `frontend/e2e/<flow>.spec.ts`
- Keep Python copy/bundle guards in `tests/test_frontend_source.py`

Each test function needs a docstring (or `test('scenario …')` title) stating the scenario.

## Coverage that is required for a changed screen

- Happy path with **fixture JSON** shaped like `ResumeAnalysisRead`
- Loading, empty, and error
- 401 → token cleared / redirect to login
- `model_unavailable` shows the actionable GGUF message (no hosted-provider mention)
- History empty: “No analyses yet”, never a fake row
- Forbidden phrases absent: placement probability, chance of getting hired, predicted company
- Score captions present for fit / alignment / readiness / terminology
- Only `supported_rewrite` exposes Accept; other edit kinds cannot be applied

## Playwright smoke (local)

Prereq: API on `127.0.0.1:8000`, sqlite via `python scripts/init_db.py`, no GGUF.

1. Register
2. See missing-model banner
3. Analyze → 503 mapped in UI
4. History empty state
5. Sign out

## Commands

```bash
cd frontend && npx tsc --noEmit && npm run build
python3 -m pytest tests/test_frontend_source.py tests/test_health.py -q
```

When Vitest/Playwright scripts exist in `frontend/package.json`, run those too. Do not add testing libraries in a drive-by; add them in the same change that introduces the first frontend test runner.

## Bugs found while testing

If you are following this skill as a test-only pass, comment `# BUG DETECTED:` or `// BUG DETECTED:` and stop. Do not silently “fix” product behavior in a test-only task.
