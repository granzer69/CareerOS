# CareerOS roadmap

Honest scope: JD-driven resume evidence and rubric scores for signed-in owners — not placement prediction or autonomous applying. See [Range-Apply](https://github.com/granzer69/Range-Apply) for job discovery orchestration.

## Shipped (main)

- Slices 1–8: local inference adapter, JWT owner scope, rubric v1.0.0, grounded edits, campus studio UI, owner-scoped analytics
- Slice 9: profile (`GET /user-profile/me`), Analyze prefill, analytics role filter
- Deeper analytics: edit funnel, version lift, heatmaps, eligibility rollups, profile-skill JD mentions
- Async analyze jobs + polling (proxy-safe), deterministic JD fallback when model JSON is invalid

## In progress / next engineering slices

| Slice | Focus | Notes |
|-------|--------|--------|
| **JD-10** | Deterministic JD coverage | Section-aware parsing, colon/comma skill lists, numbered bullets; model only augments gaps |
| **CI-1** | GitHub Actions | `pytest`, frontend unit tests, `npm run build`; optional Playwright smoke |
| **Deploy** | Render + Vercel | Prod GGUF host or `model_unavailable`; CORS + `BACKEND_URL` |

## Future prospects (product & UX)

### 1. Mobile UI refinement

- Single-column layouts below 720px with consistent spacing and no horizontal scroll on tables/charts
- 44px minimum touch targets on nav, primary actions, and evidence pills
- `safe-area-inset` padding for notched phones; sticky “Run analysis” on long Analyze forms
- Chart data tables remain the accessible source of truth (no hover-only metrics)
- Optional: bottom nav for Analyze / History / Analytics / Profile on small viewports

### 2. Overall UI/UX experience

**Shipped (Slice 8 polish):** top bar separation, typography scale, button/hover/focus on forms, loading skeleton card, centered empty states with primary CTA, scrollable table chrome on History + analytics charts.

- Onboarding checklist (first analysis, first profile save, first accepted rewrite)
- Clearer analysis detail hierarchy: scores → blocked/eligibility → evidence table → edits
- Loading skeleton on Analysis detail (History/Analytics use skeleton card)
- Optional: bottom nav on small viewports; dark mode

### 3. JD understanding (“derive everything from the JD”)

**Principle:** Every scored requirement must be traceable to JD text. The model must not invent requirements; it may only structure and classify what is already in the posting.

**Near term (deterministic-first)**

- Section-aware extraction (`Requirements`, `Qualifications`, `Responsibilities`, `Nice to have`)
- Split inline lists (`Skills: A, B, C`), numbered bullets, semicolon clauses
- Strengthen merge: deterministic rows win; model adds only non-overlapping lines
- Analysis detail flag when extraction used JD-only fallback (no valid model JSON)

**Medium term**

- Larger local GGUF on inference hosts; keep small models for dev with fallback
- Eval set: real intern/new-grad JDs with human-labeled requirement counts (`evals/jd-extraction/`)
- Optional second pass: model re-labels importance **only** for texts already in deterministic set

**Out of scope**

- Hosted LLM for JD parsing in production
- Hiring probability, ATS pass/fail, or cross-user benchmarks

## How to propose a slice

Open a PR with: problem statement, honest metrics affected, API/UI contract changes, tests, and screenshots for UI work.
