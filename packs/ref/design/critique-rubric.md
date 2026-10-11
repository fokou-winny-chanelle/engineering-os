---
id: design/critique-rubric
title: Design critique loop with screenshots (12-row scoring rubric, agent self-critique procedure, human review) and usability testing for a small team (5-user rounds, heuristic review, remote and in-person)
area: design
read_when: reviewing a screen or flow, after building the first reference screen, before a design PR, an agent must critique its own UI, planning a usability test with little time or budget, scoring docs/design/critiques/*.md
verified: 2026-10-11
revisit_days: 180
sources: ["https://github.com/microsoft/playwright-mcp", "https://www.nngroup.com/articles/ten-usability-heuristics/", "https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/", "https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/", "https://www.nngroup.com/articles/remote-usability-tests/", "https://www.nngroup.com/articles/visual-hierarchy-ux-definition/", "https://playwright.dev/docs/screenshots", "https://playwright.dev/docs/api/class-page#page-emulate-media", "https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md", "https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md"]
---
# Critique rubric and usability testing

Design quality is judged on the rendered screen, by people other than its author, repeatedly. The loop: build one screen → screenshot → score → fix the top 3 → re-shoot → human review → test with users. `eos new critique "<screen>"` creates the scoring sheet; `e2e/design-critique.spec.ts` (from `eos scaffold design-tokens`) captures the screenshots.

## Decision guide

**1. Capture the evidence.** Phone (360 px; also 320 px for reflow) and desktop (1280 px), light and dark, `reducedMotion: "reduce"`, full page (Playwright `page.screenshot({ fullPage: true })`, `page.emulateMedia({ colorScheme, reducedMotion })`). Add: every state in the state matrix (empty, loading, error, offline, success), the longest French string, 200% zoom, a grayscale copy and a 5–10 px blurred copy (the squint test). Native: simulator and emulator screenshots, compact and expanded.

**2. Score the 12 rows** (0 fails, 1 partly, 2 good), each with evidence pointing at a region of a screenshot:
| # | Row | Look for | Ref |
|---|---|---|---|
| 1 | direction fit | the 3 adjectives and the one bold thing are visible | `design/direction-process` |
| 2 | no generic tells | the rejected-defaults list, emoji icons, stock theme | `design/generic-ai-look` |
| 3 | hierarchy | one primary action; blurred copy still shows the focal point | `design/layout-hierarchy` |
| 4 | typography | ≤ 2 families, scale steps only, 45–90 character lines, accents, French fits | `design/typography` |
| 5 | colour | tokens only, `eos design check` clean, not colour-only, dark mode | `design/colour` |
| 6 | layout and spacing | scale values, alignment, intentional at 360 and 1280, no sideways scroll at 320 | `design/layout-hierarchy` |
| 7 | states | all states designed and written | `design/forms-states-copy` |
| 8 | copy | user's words, verbs on buttons, errors with a fix, FR and EN reviewed | `design/forms-states-copy` |
| 9 | interaction and motion | targets ≥ 44 px on touch, focus visible, purposeful motion, reduced motion | `design/motion-icons-imagery` |
| 10 | accessibility floor | axe clean, keyboard path, labels, contrast | `frontend/accessibility` |
| 11 | context fit | low-end phone, data cost, lower literacy, few steps | `design/cameroon-context` |
| 12 | platform | HIG / Material 3 navigation, back, safe areas | `design/ia-navigation-platforms` |
Ship rule (team default; change it in direction.md): no 0 on rows 5, 7, 9, 10; total ≥ 18/24; at least two rounds with before/after screenshots; then human approval.

**3. Agent self-critique procedure** (when an agent built the screen).
- Look at the screenshots, not the code; describe what a first-time user sees in 5 seconds before scoring.
- Score every row; quote the evidence. A row without evidence scores 0.
- Pick the top 3 fixes by user impact (not by ease), apply them, re-shoot, re-score. Stop after the rubric passes or after 3 rounds and escalate to a human with the open questions.
- Use the vendored checklists for line-level review once they are signed off (`vendor:` Vercel web interface guidelines; Anthropic frontend-design for the "remove one accessory" pass). Until a human signs them off they are not loaded.
- Never mark rows 8 (both languages) or 11 (context) as 2 without a human or user check; an agent cannot judge French register or local fit alone.
- **Live critique with Playwright MCP** (profiles `design`, `debug-ui`; `eos mcp use design`). With the dev server running: `browser_navigate` to the localhost URL → `browser_resize` 360×800, then 1280×800 → `browser_emulate_media` for dark and `reduce` motion → `browser_take_screenshot` with `fullPage` (files land in `.eos/state/playwright/`) → `browser_evaluate` `async () => (await axe.run({ runOnly: ["wcag2a", "wcag2aa"] })).violations.map(v => [v.id, v.impact, v.nodes.length])` for row 10 (axe is preloaded when the project has `axe-core` installed; only localhost origins load). Use it to explore and iterate quickly; the committed `e2e/design-critique.spec.ts` stays the repeatable record for the PR. Never approve `browser_run_code_unsafe`.

**4. Heuristic review by the team (1 hour).** NN/g: evaluators judge the design against heuristics (the 10 usability heuristics), first **independently**, then merge; one observation per line with its heuristic and a screenshot; group by severity. It works best with several evaluators, because any single one misses problems.

**5. Usability testing for a small team.**
- NN/g: "testing no more than 5 users and running as many small tests as you can afford"; in their model the first 5-person study found 85% of the problems; fix, then test again. With distinct user groups (e.g. vendors and customers), test 3–4 per group.
- Plan (half a day): 3–5 realistic tasks from the top tasks ("Payez la facture de ce mois avec Orange Money"), a short script, consent, a think-aloud prompt, no leading questions.
- Run: moderated, in person where possible (NN/g prefers it: body language, timing of probes); remote moderated over a video call or a shared phone screen when travel is hard. Use real devices people own, on their network, in their language.
- Record: task success, where they hesitated, their words (feed microcopy and labels), severity. Pay or thank participants fairly.
- Act: the same week, fix the top issues, update direction.md if a principle changed, schedule the next round. Keep a log in `docs/design/research/`.

## Examples
```markdown
| 3 | Hierarchy | 1 | phone-light: "Payer" and "Partager" both filled; blurred copy shows the banner first | make Partager a text button; shrink banner |
| 11 | Context | 0 | total in 4 rows of fees with decimals; 6 steps to pay | one total "15 000 FCFA"; fees behind "Détails"; merge steps 2–3 |
```

## Anti-patterns
- Critiquing from code or from the Figma file only; scoring without evidence.
- One reviewer, the author, once.
- Big, rare usability studies instead of small, frequent ones; testing only with colleagues.
- Fixing the easiest issues and calling the round done; skipping the re-shoot.
- Loading unsigned vendored skills to "speed up" review.

## Checks
- A `docs/design/critiques/<date>-<screen>.md` per key screen with two scored rounds and screenshots linked in the PR.
- `eos design check` and axe clean before the human review.
- Usability round log with tasks, findings and the changes made.

## Sources
- Microsoft, Playwright MCP (tools, --allowed-origins, --init-script): https://github.com/microsoft/playwright-mcp
- NN/g, 10 usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
- NN/g, How to conduct a heuristic evaluation: https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/
- NN/g, Why you only need to test with 5 users: https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/
- NN/g, Remote usability tests: https://www.nngroup.com/articles/remote-usability-tests/
- NN/g, Visual hierarchy (squint test): https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- Playwright, Screenshots: https://playwright.dev/docs/screenshots
- Playwright, page.emulateMedia: https://playwright.dev/docs/api/class-page#page-emulate-media
- Vercel, Web Interface Guidelines command.md (MIT, pinned): https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md
- Anthropic skills, frontend-design SKILL.md (Apache-2.0, pinned): https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md
