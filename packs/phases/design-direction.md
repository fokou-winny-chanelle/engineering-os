---
id: design-direction
title: Design direction (distinctive UI, no AI-generic look)
kind: phase
mode: both
when: starting a new product UI, a new screen family, a redesign, a landing page, or changing theme/tokens
description: Use before building new UI or a visual theme: write the design direction and tokens first; avoid generic AI looks.
globs: ["**/*.tokens.json", "**/tokens/**", "**/tailwind.config.*", "**/theme/**", "docs/design/**"]
next: [ux-design, frontend, mobile]
---
# Design direction

## Entry
New UI surface, redesign or theme change. If `docs/design/direction.md` is missing, create it before writing UI code (`eos new design`). If it exists, follow it; change it only on purpose, in its own PR.

## Standards
1. **Ground the design in the subject:** who uses it, where (bright sun on a phone?), its one main job, the product's world (materials, vernacular, local culture). Distinctive choices come from here, not a UI kit.
2. **Direction before code.** `docs/design/direction.md` holds: 3 adjectives and 3 anti-adjectives; 2–3 references and anti-references (with why); palette roles (OKLCH + hex); type families, roles and scale; spacing/radius/shadow scale; layout concept (ASCII wireframe); motion principle; the **one bold thing**; the defaults it deliberately rejects.
3. **Check the plan for AI defaults before building.** Unless the brief asks for them, reject:
   - Inter/Roboto/Geist/system-font-only; purple/indigo gradients on white;
   - cream + serif + terracotta; near-black + one acid accent;
   - identical rounded cards with the same soft shadow; centred hero + 3 feature cards; gradient blobs;
   - ALL-CAPS eyebrows, one highlighted word per headline, "→" on every button, 01/02/03 on non-sequences;
   - emoji as icons; fade-up on every section; stock shadcn/Tailwind theme left unchanged.

   For each rejected default, say what you chose instead.
4. **Tokens are the source of truth.** `design/tokens/*.tokens.json` (DTCG) built to CSS/Tailwind/Flutter (`eos scaffold design-tokens`). Components use semantic tokens (`--color-action`), never raw colours. Dark mode and brands are token sets, not forks.
5. **Restraint.** Boldness in one place; 1–2 type families; body lines under ~80 characters; motion explains a change (one orchestrated moment at most).
6. **Quality floor (WCAG 2.2 AA):** contrast 4.5:1 text and 3:1 UI; visible focus never hidden by sticky bars; targets ≥ 24×24 CSS px (44–48 on touch); no drag-only actions; `prefers-reduced-motion` honoured; works at 320 px and 200% zoom.
7. **Copy is design.** User's words, active verbs ("Save changes"), one name per action; errors say what happened and how to fix it; French and English both reviewed.
8. **Critique loop.** Build one key screen; screenshot phone and desktop, light and dark (`CRITIQUE=1` Playwright spec); score it with `eos new critique "<screen>"` (12-row rubric); fix the top 3; at least 2 rounds; then human review.
9. **Platform conventions.** On mobile, keep HIG / Material 3 behaviours (navigation, back, gestures, safe areas) even with a custom look.
10. **One authority:** direction.md > tokens > `eos design check` (final gate) > our refs > suggestions. An opt-in studio (`.eos/studio/README.md`) only suggests; its palettes and fonts enter through tokens.

## Deliverables
- `docs/design/direction.md`, token files, one critiqued reference screen (screenshots and critique sheet in the PR), component inventory.

## Automated checks
- `eos design check`: DTCG schema, contrast of token/theme pairs, generic-look lint. Runs in `eos verify` when UI or token files change.
- axe on key pages.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `design/direction-process` · `design/generic-ai-look` · `design/typography` (French) · `design/colour` (OKLCH, contrast) · `design/layout-hierarchy` · `design/motion-icons-imagery` · `design/critique-rubric` (screenshot loop, user tests) · `design/tokens-pipeline` (DTCG, Style Dictionary, Figma MCP) · `design/cameroon-context` · `frontend/design-system`.

## Exit checklist (Definition of Done)
- [ ] direction.md exists; a human approved it for new products or redesigns.
- [ ] No rejected default used without a written reason. The "one bold thing" is visible.
- [ ] `eos design check` passes; components use semantic tokens only.
- [ ] Two scored critique rounds, with before/after screenshots in the PR.

## Handoff → ux-design / frontend / mobile
Pass direction.md, the tokens, the reference screen and the open questions.

## Stop & escalate
Stop when brand assets, font/image licences or the direction are undecided; ask. Never copy another product's look.
