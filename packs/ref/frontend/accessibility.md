---
id: frontend/accessibility
title: Accessibility implementation to WCAG 2.2 AA (what changed in 2.2, semantic HTML first, ARIA Authoring Practices patterns, focus management in SPAs and dialogs, Next.js route announcer, lint and axe limits, manual checks)
area: frontend
read_when: building any interactive component, a dialog/menu/tabs/combobox, handling focus after navigation or submit, a page fails axe or an accessibility audit, adding touch targets or drag interactions, writing accessibility tests
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/", "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html", "https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/", "https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/", "https://nextjs.org/docs/architecture/accessibility", "https://github.com/jsx-eslint/eslint-plugin-jsx-a11y", "https://playwright.dev/docs/accessibility-testing", "https://www.deque.com/axe/core-documentation/api-documentation/", "https://www.deque.com/automated-accessibility-testing-coverage/"]
---
# Accessibility implementation (WCAG 2.2 AA)

Target WCAG 2.2 Level AA. Automated tools catch only part of the problems, so build with semantic HTML and tested primitives, then check by keyboard and screen reader.

## Decision guide

**1. What WCAG 2.2 added at A/AA** (on top of 2.1; 4.1.1 Parsing was removed):
| SC | Level | In code |
|---|---|---|
| 2.4.11 Focus Not Obscured (Minimum) | AA | sticky headers, cookie banners and bottom bars must not fully hide the focused element; use `scroll-padding-top`/`scroll-margin` |
| 2.5.7 Dragging Movements | AA | every drag (reorder, slider, map pan) has a single-pointer alternative (buttons, tap-to-select) |
| 2.5.8 Target Size (Minimum) | AA | pointer targets at least 24×24 CSS px, or spaced so a 24 px circle around each does not overlap another (exceptions: inline text links, equivalent control, browser-native) |
| 3.2.6 Consistent Help | A | help/contact link in the same place on every page |
| 3.3.7 Redundant Entry | A | don't make users re-type info given earlier in the same flow (prefill or let them select) |
| 3.3.8 Accessible Authentication (Minimum) | AA | no memory/puzzle test to log in unless there is an alternative; allow paste and password managers; OTP fields accept paste |

**2. Semantic HTML first.** `<button>` for actions, `<a href>` for navigation, `<label>` for every input, headings in order, landmarks (`<header> <nav> <main> <footer>`), `<table>` for tabular data, `lang` on `<html>` matching the locale (`fr`/`en`). The ARIA Authoring Practices say "No ARIA is better than Bad ARIA": add ARIA only when no native element fits, and then follow the APG pattern exactly.

**3. Complex widgets.** Use headless primitives (Radix, React Aria; `frontend/design-system`) that implement the APG patterns: dialog (focus moves inside on open, Tab/Shift+Tab cycle within, Escape closes, focus returns to the trigger), menu button, tabs (arrow keys between tabs), combobox, disclosure, listbox. Prefer native `<dialog>` with `showModal()` or `inert` on background content over hand-made focus traps.

**4. Focus management in an App Router app.**
- Next.js includes a route announcer: on client-side navigation it announces `document.title`, then the first `<h1>`, then the pathname. Give every page a unique, descriptive `metadata.title`.
- After a form submit with errors, move focus to the error summary or first invalid field; after a successful action that removes the triggering element, move focus to something sensible (heading, next item).
- Provide a "skip to main content" link as the first focusable element.
- Never remove outlines without a visible `:focus-visible` replacement.
- Live updates (toast, "saved", cart count): an `aria-live="polite"` region that exists before the update; `role="alert"` only for urgent errors.

**5. Visual and motion.** Contrast 4.5:1 text / 3:1 large text and UI parts; content usable at 200% zoom and 320 px width (reflow); honour `prefers-reduced-motion`; don't convey meaning by colour alone; images get `alt` that says what matters (empty `alt=""` for decoration).

**6. Tooling limits.** `eslint-config-next` registers jsx-a11y but turns on only six of its rules as warnings (`alt-text`, `aria-props`, `aria-proptypes`, `aria-unsupported-elements`, `role-has-required-aria-props`, `role-supports-aria-props`). Add the plugin's `flatConfigs.recommended` rules (`eos scaffold eslint-next`). axe-core in e2e finds rendered-DOM issues; include the `wcag21a`, `wcag21aa` and `wcag22aa` tags, not just `wcag2a`/`wcag2aa`, or the 2.2 target-size rule never runs. Deque's own study of its audits found 57.38% of issues by automated tests (a vendor figure), so a clean axe run is not conformance.

## Examples
```tsx
// focus the error summary after a failed submit
const summaryRef = useRef<HTMLDivElement>(null);
useEffect(() => { if (state?.fieldErrors) summaryRef.current?.focus(); }, [state]);
return state?.fieldErrors ? (
  <div ref={summaryRef} tabIndex={-1} role="alert" aria-labelledby="err-title">
    <h2 id="err-title">{t("form.errorsTitle")}</h2>
    <ul>{Object.keys(state.fieldErrors).map((f) => <li key={f}><a href={`#${f}`}>{t(`fields.${f}`)}</a></li>)}</ul>
  </div>) : null;
```

## Anti-patterns
- `<div onClick>` as a button; `<a>` without `href` for actions; icon buttons without an accessible name.
- `aria-label` copied onto everything; `role="menu"` for site navigation; positive `tabIndex`.
- Placeholder-only inputs; errors shown only in colour or a vanishing toast.
- Sticky bottom bars (common on mobile checkouts) covering the focused field.
- Treating "axe passes" or a Lighthouse accessibility score as WCAG conformance.

## Checks
- `eos scaffold eslint-next`: eslint-config-next + jsx-a11y recommended, errors in CI.
- `eos scaffold e2e-node`: Playwright + `@axe-core/playwright` on key pages, failing on serious/critical; add pages in error and open-dialog states.
- Manual, per release on changed flows: keyboard-only pass (Tab order, visible focus, Escape, no traps), screen reader smoke test (NVDA + Firefox or Chrome on Windows, VoiceOver on iOS, TalkBack on Android), 200% zoom and 320 px width.
- Lighthouse accessibility category in LHCI only as a regression signal (`eos scaffold lighthouse` does not assert it; add `categories:accessibility` yourself if wanted).

## Sources
- W3C WAI, What's New in WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- WCAG 2.2 Understanding 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- WAI-ARIA APG, Read Me First: https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/
- WAI-ARIA APG, Dialog (Modal) pattern: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- Next.js, Accessibility: https://nextjs.org/docs/architecture/accessibility
- eslint-plugin-jsx-a11y: https://github.com/jsx-eslint/eslint-plugin-jsx-a11y
- Playwright, Accessibility testing: https://playwright.dev/docs/accessibility-testing
- axe-core API (tags): https://www.deque.com/axe/core-documentation/api-documentation/
- Deque, automated testing coverage study: https://www.deque.com/automated-accessibility-testing-coverage/
