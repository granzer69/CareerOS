---
name: careeros-figma
description: Use when designing CareerOS screens in Figma, generating a design system from code, or implementing a Figma file as React. Wraps Figma MCP skills with CareerOS product constraints.
---

# CareerOS × Figma

CareerOS UI must be designed and implemented through Figma when the user wants visual/enterprise quality. Do not invent a second product (placement predictor, job board, autonomous apply).

## Mandatory Figma skill order

1. **New file**: load `figma-create-new-file` / `create_new_file`, then `create_session`
2. **Design system from code**: load `figma-generate-library` + `figma-use`
3. **App page into Figma**: load `figma-generate-design` + `figma-use`; `search_design_system` first
4. **Figma → React**: load `figma-design-to-code` **before** `get_design_context`
5. Never call `use_figma` or `get_design_context` without those skills

Reuse existing components and variables. Do not generate a parallel button set if a match exists.

## Screens to cover (in this order)

1. Sign in / register
2. Analyze (upload + JD + score disclaimer)
3. Analysis report (four scores, eligibility, evidence table, edits, versions)
4. History (empty + populated)
5. Analytics portfolio (only after `careeros-honest-analytics`; real fields only)
6. Version compare

Optional later (Phase 6): export/share, profile+analysis combined. Not Range-Apply job search/apply.

## Visual target

- Warm paper background, forest brand, editorial serif for titles, dense data for tables
- Enterprise = information hierarchy and empty/error states, not glassmorphism or hero illustrations
- Every ScoreCard in Figma includes definition caption
- Evidence states are labeled pills, not unlabeled dots
- Missing-model banner is a first-class component

## Code Connect

When mapping Figma ↔ code, connect: Button, Banner, ScoreCard, EvidencePill, RequirementTable, EditDiff, EmptyState, AppShell.

Implement in `frontend/src`, then `npm run build`. Never patch `frontend/dist` to match Figma.

## Honesty check before publishing a frame

Reject or relabel frames that show:

- Placement % / “chance of getting hired”
- Recommended companies
- Vendor ATS meters
- Hosted-LLM branding

If the Figma file came from an old “Student Placement Prediction” mock, replace it; do not implement it.
