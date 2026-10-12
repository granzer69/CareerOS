---
name: careeros-telemetry
description: Use when adding analytics SDKs, product tracking, PostHog, Mixpanel, Vercel Analytics, logs of user actions, or outcome tracking. Opt-in only; never send resume or JD text to third parties by default.
---

# CareerOS product telemetry

This is **product usage telemetry**, not career-outcome prediction. Phase 6 of the roadmap allows opt-in feedback and outcome tracking **with consent**, only after the copilot is stable.

## Default

- **Off** for candidate document contents
- Local/offline mode must keep working with telemetry blocked or unset
- Missing GGUF, JWT failures, and rubric scores stay in the CareerOS API — do not proxy them through a third-party LLM or analytics warehouse as raw text

## Never send to a third party (unless the user later designs an explicit, documented export)

- Resume file bytes or `resume_text`
- Job description paste
- Evidence spans, proposed rewrite text, profile fields
- Email as a tracking identity without consent
- Scores joined to resume content

## Allowed events (once an SDK is chosen and consented)

Names only; properties are enums / ids / booleans / durations:

- `auth_register_succeeded` / `auth_login_failed` (reason code, not password)
- `analyze_submitted` (`file_kind`: pdf|docx)
- `analyze_failed` (`code`: `model_unavailable` | `file_too_large` | …)
- `history_viewed` (`empty`: boolean)
- `edit_generated` / `edit_accepted` / `edit_rejected` (`kind`)
- `version_restored`
- `health_model_missing_shown`

No `predicted_company`. No `hire_probability`.

## Implementation rules

1. Ask the user before adding PostHog/Mixpanel/Amplitude/GA
2. Gate on an env flag (`VITE_TELEMETRY_ENABLED`) and a user consent setting when you add persistence
3. Prefer first-party: Vercel Analytics (page views) or `custom-metrics` for latency — still no document bodies
4. Server logs: timing, status, `code`, model path **existence**, rubric version — never prompt+resume dumps
5. Outcome tracking (“I got the interview”) is a separate consented form, stored owner-scoped in CareerOS, not a shadow profile at an ad network

## Interaction with honest analytics

In-app charts use CareerOS APIs (`careeros-honest-analytics`). Telemetry does not replace those charts and must not be used as a backdoor to plot other users’ scores.

## Tests

If telemetry is added, tests must assert:

- fixtures still pass with telemetry disabled
- mocked SDK is not called with `resume_text` or `job_description`
- forbidden copy scans still pass
