---
id: ux-design
title: UX & design
kind: phase
mode: both
when: designing flows, screens, design tokens or reviewing Figma
description: Use when designing user flows, wireframes, UI states or design tokens, or turning Figma into components.
globs: ["docs/ux/**", "design/**", "**/tokens/**", "**/*.stories.*", "**/theme/**"]
next: [architecture, frontend]
---
# UX & design

## Entry
Approved requirements with personas and ACs. A design system exists or is about to be created.

## Standards
1. Flows before screens. Map each user journey step by step, including error and recovery paths. Every AC maps to a flow step.
2. Every screen has every state: empty, loading, partial, success, error, offline/slow, no-permission, and long content. Missing states are a common source of frontend bugs.
3. Accessibility is WCAG 2.2 AA by default.
   - Contrast ≥4.5:1 for text.
   - Visible focus and full keyboard paths.
   - Touch targets ≥24×24 CSS px.
   - Labels on every input; errors announced to screen readers.
   - Don't convey meaning by colour alone.
4. Design tokens are the contract. Colour, spacing, type, radius and motion are named tokens. Code uses tokens, never hex values or one-off pixel sizes. Tokens live in `design/tokens/*.tokens.json` (DTCG); Figma variables are an input, not the source of truth.
5. Content. Use real copy, not lorem ipsum. Design for the longest language (French usually runs longer than English). Error messages say what happened and what to do next.
6. Performance-aware design. Design mobile-first for low-end devices and slow networks: image budgets, skeletons over spinners, no layout shift.
7. Money UX. Show amounts with currency and correct grouping, show fees before confirmation, make confirmation steps explicit, never double-submit, and state clearly where a pending state applies.
8. Figma → code. The agent reads frames via Figma MCP and maps them to existing components first. Creating a new component requires a reason.

## Deliverables
- `docs/ux/flows.md`: journeys and a state matrix.
- Figma links per screen; a list of tokens and components (new versus reused).
- Optional: BMAD `bmad-ux` (Sally) design spec.

## Automated checks
- Storybook stories for every new component state.
- Accessibility checks (axe) in component/e2e tests; visual regression if configured.
- `eos design check` (token schema, contrast, raw colours outside tokens).

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `design/forms-states-copy` (forms, errors, empty/loading, FR/EN tone) · `design/ia-navigation-platforms` (card sort, HIG vs Material 3) · `design/data-visualisation` · `design/critique-rubric` (heuristic review, 5-user tests) · `design/cameroon-context` (literacy, data cost) · `design/tokens-pipeline` (Figma MCP) · `frontend/accessibility`.

## Exit checklist (Definition of Done)
- [ ] Every flow has error and recovery paths, and every screen has its full state matrix.
- [ ] Accessibility notes per screen (focus order, labels, contrast checked).
- [ ] Tokens are defined; new components are justified.
- [ ] Copy is reviewed in every supported language.
- [ ] Product/UX sign-off.

## Handoff → architecture / frontend
Pass flows, the state matrix, tokens, the component list and Figma links.

## Stop & escalate
Stop when a flow needs a business rule nobody has defined, or when accessibility conflicts with a requested design.
