# Design critique: <screen>

Date: YYYY-MM-DD · Round: 1 · Direction: `docs/design/direction.md` · Rubric: `.eos/packs/ref/design/critique-rubric.md`

## Screenshots
Capture with `CRITIQUE=1 CRITIQUE_PATHS="/<path>" npx playwright test e2e/design-critique.spec.ts` (phone 360 px and desktop 1280 px, light and dark, reduced motion) or a simulator. Also check 320 px wide and 200% zoom.

| View | Before | After |
|---|---|---|
| phone, light | | |
| phone, dark | | |
| desktop, light | | |

## Scores (0 = fails, 1 = partly, 2 = good; judge the screenshot, not the code)
| # | Criterion | Score | Evidence (where on the screenshot) | Fix |
|---|---|---|---|---|
| 1 | Direction fit: the 3 adjectives and the one bold thing are visible | | | |
| 2 | No generic AI tells (rejected-defaults list) without a written reason | | | |
| 3 | Hierarchy: one primary action; the squint test finds the most important thing first | | | |
| 4 | Typography: ≤ 2 families, scale steps only, body 45–90 characters, French text fits | | | |
| 5 | Colour: tokens only, `eos design check` passes, colour never the only cue, dark mode checked | | | |
| 6 | Layout and spacing: on the scale, aligned, intentional at 360 and 1280 px, no sideways scroll at 320 px | | | |
| 7 | States: empty, loading, error, offline, success all designed | | | |
| 8 | Copy: the user's words, active verbs, errors say what happened and how to fix it; FR and EN read by a speaker | | | |
| 9 | Interaction and motion: touch targets ≥ 44 px, visible focus, motion explains a change, reduced motion respected | | | |
| 10 | Accessibility floor: axe clean, keyboard path, every control labelled | | | |
| 11 | Context: low-end phone, slow or expensive data, lower literacy (icons with text, clear numbers, few steps) | | | |
| 12 | Platform (mobile): HIG / Material 3 navigation, back behaviour, safe areas | | | |

Total: __ / 24. Ship rule (team default; change it in direction.md): no 0 on rows 5, 7, 9 or 10, total ≥ 18, and at least two rounds with before/after screenshots.

## Top 3 changes for the next round
1.
2.
3.

## Human review
Reviewer: · Date: · Verdict: approve / another round
