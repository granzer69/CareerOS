---
name: frontend-a11y
description: Use when building CareerOS forms, tables, charts, dialogs, banners, or any interactive UI. Enforces WCAG 2.2 AA, keyboard access, and non-color encodings for evidence and scores.
---

# CareerOS frontend accessibility

Target **WCAG 2.2 AA**. CareerOS is a data-heavy copilot; accessibility failures hide the product.

## Always

- Semantic HTML: `header`, `nav`, `main`, `table` for tabular evidence, `label` for every control
- Visible focus ring (do not `outline: none` without a replacement)
- Buttons are `<button>`; links that navigate are `<a>` / router `Link`
- `htmlFor` / `id` on form fields; do not rely on placeholder as the label
- `prefers-reduced-motion`: no required animation to complete analyze, accept, or reject

## Auth and analyze

- Sign-in errors in a `role="alert"` banner
- File input has an associated label (“Resume (PDF or DOCX, max 5 MB)”)
- Disable submit while pending; announce “Analyzing…” via the button text and `aria-busy`
- 401: send the user to login; do not trap them on a dead page

## Scores and evidence

- Score value + text definition; do not use color-only bars
- Evidence pills: text of the state (`confirmed`, …) plus color
- `blocked_by_requirement`: `role="alert"` banner, not only a red card
- Requirement tables: real `<th scope="col">`; do not rebuild tables as div grids unless a grid has row/columnheaders

## Charts (`careeros-honest-analytics`)

- `aria-label` or visible heading naming the metric, rubric version, and n
- Data available as a table or equivalent text, not canvas-only
- Patterns/shapes in addition to hue for series
- Keyboard: focusable summary, not hover-only tooltips as the sole value readout

## Dialogs and banners

- Modal dialogs: focus trap, Escape closes, return focus to invoker
- Model-missing banner is readable by SR (not `display:none` color strip)
- Do not auto-dismiss errors

## Contrast

- Body text on `--paper` / `--bg` ≥ 4.5:1
- Warn/danger banners: text (not the background tint) carries the message
- Muted text is for captions, not primary scores

## Checks before finishing a UI change

- Keyboard-only pass of the changed flow
- Zoom 200% without clipping primary actions
- No `title`-only instructions
- If Playwright exists, add an axe or equivalent scan on the changed route; if not, document the keyboard pass you ran
