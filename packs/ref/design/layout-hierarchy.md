---
id: design/layout-hierarchy
title: Layout, spacing systems, grids and visual hierarchy (4/8 px scale, responsive grids and breakpoints, density, squint test, scanning patterns, reflow and targets)
area: design
read_when: laying out a new screen or page, spacing feels random, a page has no clear focal point, choosing breakpoints or a grid, designing for 360 px phones and large screens, dense dashboards or tables
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.nngroup.com/articles/visual-hierarchy-ux-definition/", "https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/", "https://www.w3.org/WAI/WCAG22/Understanding/reflow.html", "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html", "https://developer.apple.com/design/human-interface-guidelines/buttons", "https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes", "https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html", "https://tailwindcss.com/docs/theme"]
---
# Layout, spacing and hierarchy

Hierarchy answers "what do I look at first, and what can I do here?". NN/g names three tools: colour and contrast, scale, and grouping (proximity and common regions). Spacing and grids make grouping consistent; tokens make it repeatable.

## Decision guide

**1. One spacing scale, in tokens.** A 4 px base (`spacing.1 = 0.25rem`, then 2, 3, 4, 6, 8, 12, 16) covers UI from icon gaps to section breaks; Tailwind v4 derives spacing utilities from `--spacing` theme variables. Rules of thumb:
- space inside a group < space between groups (proximity is the cheapest grouping);
- use 3–5 scale steps per screen; random values (`mt-[13px]`) are a smell;
- radius and elevation get their own small scales (2–3 steps each).

**2. Hierarchy per screen.**
- One primary action, visually dominant (filled, action colour); secondary actions quieter (outline or text). Two equal primary buttons = no decision made.
- Scale and weight before colour: size, weight and position do most of the work; colour is for the one thing that must pop.
- **Squint test** (NN/g): blur the screenshot (5–10 px). The intended focal point and groups should still be obvious; if a decorative element wins, fix it. Run it in every critique round.
- Scanning: people scan headings and the first words of lines (F and layer-cake patterns). Start headings with the information-carrying words ("if users see only the first 2 words, they should still get the gist"), use headings and lists, bold sparingly. Canada.ca suggests a heading roughly every 200 words of text.

**3. Grids and breakpoints by content, not device names.**
- Web: mobile-first single column, then add columns when content needs them. Whatever column count you pick, what matters is that edges align.
- Android's window size classes give adaptive layout thresholds: compact width < 600 dp, medium 600–840 dp, expanded 840–1200 dp (larger classes exist above). Use them for app layouts and as sane web breakpoints too.
- Max content width for reading (about 65ch for prose); dashboards can go wider but keep a predictable left edge.
- Reflow: content must work at 320 CSS px wide without two-dimensional scrolling (WCAG 1.4.10), which also covers 400% zoom on a 1280 px screen. Tables and maps may scroll horizontally inside their own container.

**4. Density matches the job.** Field and novice users (outdoors, one hand, lower literacy) need larger targets, fewer items per screen, generous spacing. Expert, repeated work (back-office tables) can be dense, with a compact mode rather than a separate design.

**5. Targets and thumbs.** WCAG 2.5.8 (AA): pointer targets at least 24×24 CSS px or spaced so a 24 px circle doesn't overlap another target. Apple: buttons need a hit region of at least 44×44 pt. On touch, aim for 44–48 px and put frequent actions within thumb reach (bottom of the screen on phones; see `design/ia-navigation-platforms`).

**6. Avoid layout clichés.** A centred hero + three identical cards + a gradient is the generic template (`design/generic-ai-look`). Alternatives that come from content: lead with a real task screen, asymmetric splits, a strong typographic block, a list or table where the content is a list, edge-to-edge imagery from the product's world.

## Examples
```
Phone (360 px)               Desktop (1280 px, 12 col)
┌────────────────────┐       ┌──────────┬──────────────────────────────┐
│ Facture ENEO       │       │ Nav      │ Facture ENEO           [Payer]│
│ 15 000 FCFA  (big) │       │ (visible │ 15 000 FCFA · échéance 12 oct  │
│ échéance 12 oct    │       │  list)   │ ───────────────────────────── │
│ [ Payer ]  primary │       │          │ Historique (table)            │
│ Historique ›       │       └──────────┴──────────────────────────────┘
└────────────────────┘
```

## Anti-patterns
- Everything in a card; cards inside cards. Use whitespace and rules to group.
- Several elements competing as the focal point (two filled buttons, a banner and a carousel).
- Fixed-width layouts that scroll sideways at 320 px; text in fixed-height boxes.
- Breakpoints named after devices ("iPhone") instead of where the content breaks.
- Tiny icon-only targets packed together on touch screens.

## Checks
- Screenshots at 320/360 px and 1280 px in each critique round, plus the blurred squint version (rubric rows 3 and 6).
- Playwright: no horizontal scroll at 320 px (`document.documentElement.scrollWidth <= 320`).
- Review: spacing, radius and shadow values come from tokens; one primary action per screen.

## Sources
- NN/g, Visual hierarchy in UX: https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- NN/g, F-shaped pattern of reading: https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- WCAG 2.2 Understanding 1.4.10 Reflow: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- WCAG 2.2 Understanding 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Apple HIG, Buttons: https://developer.apple.com/design/human-interface-guidelines/buttons
- Android, Use window size classes: https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes
- Canada.ca Content Style Guide: https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html
- Tailwind CSS, Theme variables: https://tailwindcss.com/docs/theme
