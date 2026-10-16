---
name: careeros-student-ux
description: Use when polishing CareerOS copy, onboarding, empty states, auth hero, analyze steps, or any student-facing UI. Attracts students with a campus resume studio — never with placement prediction or employer-logo marketing.
---

# CareerOS student UX

CareerOS should feel like a **campus resume studio**: warm paper, forest brand, one posting at a time. Students stay because the JD match is honest, not because the UI promises a job.

Read `careeros-frontend-contract` and `careeros-design-system` first.

## Who it is for

Students, interns, co-ops, and early-career applicants who have a real posting and a PDF/DOCX. Speak to that person. Do not pivot the product into a placement office, FAANG tracker, or “career OS” mosaic.

## Attract students with

1. A sign-in hero that explains the four steps (upload, role, paste JD, review evidence)
2. Rubric names in plain language on every score
3. Empty history and empty analytics that tell them what to do next
4. Fast, calm daily use: no celebratory banners when the local model is merely present
5. Owner-scoped analytics they can show a counselor: evidence mix, gaps, readiness trend

## Never attract students with

- Placement probability, “chance of getting hired”, predicted company
- Employer logo walls, testimonial carousels, or “students placed at Google”
- Fake sample analyses to fill an empty dashboard
- Dark-pattern urgency (“12 recruiters viewing your profile”)
- Hosted-LLM claims or “AI that writes your resume for you”

## Onboarding contract

- Auth is a two-column studio: hero + form. The form heading stays “Sign in” / “Create an account”
- Analyze keeps the heading “Analyze a resume against a JD” so existing tests and muscle memory hold
- Steps live in `StepList` / `STUDIO_COPY`; do not invent a fifth marketing step
- Footer (`StudioFooter`) restates owner-scope and local GGUF — not a hiring forecast

## Voice

- Sentence case. Specific (“paste the posting you would submit to”)
- Second person is fine; do not talk down (“even if you have no internships…”)
- Campus, studio, posting, evidence — not pipeline, funnel, or yield

## Layout

- Auth and analyze may use a two-column studio layout; stack under 720px
- Analytics may use `shell-wide` (1280px); other pages stay ~1180px
- Keep skip-link, `main#main-content`, and `aria-current` on primary nav

## Tests

After copy or onboarding changes:

- Forbidden-phrase scan (`tests/test_frontend_source.py`)
- Auth still says it is not a placement predictor
- Empty history / analytics still have a path to Analyze
- Playwright smoke still finds Sign in, Analyze, History, Analytics
