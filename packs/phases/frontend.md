---
id: frontend
title: Frontend implementation
kind: phase
mode: files
when: writing or changing UI code, components, styles or client state
description: Use when writing or changing web UI - components, pages, styles, client state, forms, data fetching. Accessibility, all UI states, performance budgets, security of the client.
globs: ["**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.svelte", "**/*.css", "**/*.scss", "**/components/**", "**/hooks/**", "**/app/**/page.*", "**/app/**/layout.*"]
next: [testing-qa, code-review]
---
# Frontend implementation

## Entry
A story with ACs, UX flows and the state matrix, tokens, and the API contract with a generated client.

## Standards
1. Reuse before you create. Search the existing components and design system first. New components need a reason and a story per state.
2. Every state is implemented: loading, empty, error (with retry), partial, success, offline/slow, and no-permission. Map them from the UX state matrix.
3. Accessibility (WCAG 2.2 AA).
   - Use semantic HTML first and ARIA only when needed.
   - Every input has a label.
   - Focus is managed on route changes, dialogs and errors.
   - Keyboard paths work.
4. Data.
   - Use the generated API client and types; no hand-written fetch shapes.
   - Validate untrusted data at the boundary.
   - Server state lives in the framework's data layer or a query cache, not copied into global stores.
   - Mutations are idempotent-safe: disable the button and send an idempotency key for payments.
5. Forms.
   - Use a schema validator shared with the API types where possible.
   - Server errors are mapped to fields.
   - Never trust client-side validation alone.
6. Performance budgets.
   - Watch Core Web Vitals: LCP < 2.5 s, INP < 200 ms, CLS < 0.1 at p75.
   - Set a JS-per-route budget.
   - Size images and lazy-load them; avoid layout shift; code-split heavy widgets.
   - Test on a throttled mid-range mobile profile.
7. Client security.
   - No secrets in client bundles; only explicitly public env vars.
   - No `dangerouslySetInnerHTML`/`v-html` with untrusted data; sanitise if unavoidable.
   - CSP-friendly code.
   - Auth tokens go in httpOnly cookies, not localStorage.
8. Styling. Follow `docs/design/direction.md` (design-direction pack). Use design tokens only, with no magic numbers. Layouts must work at 320 px and up and with the longest translation.
9. i18n. No hard-coded user-facing strings. Locale-aware number, currency and date formatting.

## Deliverables
- Components and pages, plus stories for new components, component tests and an e2e test for the main AC path.
- A screenshot or short recording in the PR for visible changes.

## Automated checks (commands come from the stack pack)
- format, lint (with jsx-a11y), type-check, unit/component tests, build.
- e2e plus axe scan on key pages.
- `eos i18n check`; `eos bundle-size` and Lighthouse CI budgets if configured.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `frontend/nextjs-rendering-data` (server vs client, caching, PPR/ISR) · `frontend/nextjs-actions-routes` (actions, route handlers, proxy, env) · `frontend/state-forms` (TanStack Query, URL state, schemas, form errors) · `frontend/design-system` (tokens, variants, headless primitives) · `frontend/accessibility` (WCAG 2.2, focus, axe limits) · `frontend/web-vitals-budgets` (LCP/INP/CLS, Lighthouse CI) · `frontend/assets-bundles` (images, fonts, scripts, splitting) · `frontend/i18n-l10n` (fr/en, XAF, Africa/Douala) · `frontend/web-security` (XSS, CSP, token storage) · `frontend/errors-observability` (error.tsx, RUM, test map) · `frontend/low-bandwidth` (offline, PWA, data saver) · `frontend/react-native-web` (sharing with Expo) · `design/forms-states-copy` (error, empty, loading copy).

## Exit checklist (Definition of Done)
- [ ] All UI states are implemented and visible in stories or tests.
- [ ] Keyboard and screen-reader basics are verified, and the axe scan is clean.
- [ ] No secrets in the bundle, and no unsafe HTML injection.
- [ ] Performance budget is respected (or a regression is justified).
- [ ] Stack fast and full checks are green, and the build passes.

## Handoff → testing-qa / code-review
Pass the PR with screenshots, AC coverage, and the list of states and devices checked.

## Stop & escalate
Stop when the design is missing a state or rule, when an API change is needed (go to api-design), or after 3 failed fix attempts.
