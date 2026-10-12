---
name: careeros-design-system
description: Use when adding CareerOS UI components, pages, tokens, CSS, layout, or a component library. Defines density, states, score cards, and how to grow from the Slice 6 copilot into an enterprise visual system.
---

# CareerOS design system

Use this when creating or restyling CareerOS UI. Pair with `careeros-frontend-contract` for copy/API and `careeros-figma` when a Figma file exists.

## Goal

A focused, dense, trustworthy copilot — closer to Linear / Stripe Dashboard than a marketing landing page or a fake “career OS” mosaic.

## Until a library is adopted

Current source: `frontend/src/styles.css` plus page-level TSX.

- Extract shared pieces into `frontend/src/components/` before duplicating markup
- Tokens already implied: `--bg`, `--ink`, `--muted`, `--line`, `--paper`, `--brand`, `--danger`, `--warn`, `--ok`
- Keep the warm paper + forest brand; do not switch to a generic violet SaaS theme without a Figma foundation

## When adding a component library

Prefer **shadcn/ui + Tailwind CSS** on the existing Vite+React app. Do not migrate to Next.js, MUI, Chakra, or a new framework unless the user explicitly requests it and there is a demonstrated need.

Rules:

1. Search `frontend/src/components` and Figma Code Connect before creating a new primitive
2. Primitives: Button, Input, Textarea, Select, Banner, Card, Table, Tabs, Dialog, Dropdown, Tooltip, EmptyState, ScoreCard, EvidencePill, ChartFrame
3. One primary button style, one secondary, one destructive
4. No CSS-in-JS (`styled-components`, emotion) and no MUI/Chakra unless already in the tree

## Layout

- Max content width ~1100–1200px for analyze/history; analytics views may go to 1280px
- Top bar: brand + Analyze + History (+ Analytics when that route exists) + Sign out
- Forms: stacked labels above controls, visible `:focus` rings
- Score row: four equal ScoreCards (fit, alignment, readiness, terminology)
- Tables for requirements; do not turn evidence into unlabeled colored dots

## Density and type

- Body 15–16px; scores can be large but captions must define them
- Sentence case. No all-caps section headers
- Prefer serif brand + system UI for data tables if mixing type; keep tables tabular/ lining nums

## States (mandatory)

| State | Pattern |
|---|---|
| Loading | Skeleton or “Loading…” in the content region, not a blank shell |
| Empty | Explain how to get data (e.g. history: run an analysis) |
| Error | Banner using `actionableMessage`; keep the form values |
| Success | Quiet confirmation, not confetti |
| Model missing | Persistent warn banner from `/health.local_model === "missing"` |

## ScoreCard contract

Every numeric score on screen must include:

1. Label in plain language
2. Value or em-dash if null
3. One-sentence definition (see frontend-contract skill)
4. Rubric version when rendering an analysis

Never use a gauge that implies 100 = “will be hired”.

## Evidence pills

Map `evidence_state` to text + color + icon, never color alone:

- `confirmed` — ok
- `partial` — warn
- `not_found` — muted
- `contradicted` — danger
- `unknown` — muted

## Do not

- Add a marketing homepage, testimonial carousel, or employer logo wall
- Dark-mode-only first; if theming, token-based light default then dark
- Decorative charts on screens that have no data
- Patch `frontend/dist` to restyle the product
