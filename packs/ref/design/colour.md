---
id: design/colour
title: Colour systems (OKLCH palettes and gamut, semantic tokens and on-colour pairs, WCAG 2 contrast vs APCA, dark mode, colour-blind safety) and the eos contrast check
area: design
read_when: building or changing a palette, adding dark mode or a second theme, a contrast failure from eos design check or axe, choosing between WCAG ratios and APCA, colours look different on phones, defining semantic colour tokens
verified: 2026-10-10
revisit_days: 180
sources: ["https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/oklch", "https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl", "https://www.designtokens.org/tr/2025.10/color/", "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html", "https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html", "https://www.w3.org/TR/wcag-3.0/", "https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html", "https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale", "https://tailwindcss.com/docs/colors"]
---
# Colour

Colour does three jobs: identity (the brand's few hues), meaning (action, danger, success) and structure (surfaces, borders). Keep the three separate in tokens and almost every later decision becomes mechanical.

## Decision guide

**1. Two tiers of tokens.**
- Primitives: ramps per hue (`color.base.green.400/600/700`, `paper.50/100/200`). Only semantic tokens reference them.
- Semantic roles that components use: `bg`, `surface`, `muted`, `action`, `accent`, `danger`, `success`, `warning`, `border`, `focus`, each text-bearing role with an **on-colour** partner (`on-action`, `on-danger`; shadcn names them `*-foreground`). The pair *is* the contrast contract.
- Dark mode and partner brands remap semantic tokens to other primitives; components never change.

**2. Build ramps in OKLCH.** `oklch(L C H)`: L is perceived lightness 0–1, C chroma, H hue angle. Equal L steps look equally spaced, unlike HSL, so contrast is predictable and ramps generate cleanly (Evil Martians); MDN lists `oklch()` as Baseline widely available. Tailwind v4's default palette is itself OKLCH in 11 steps (50–950). Practical recipe:
- fix the hue, step L (e.g. 0.98 → 0.17), lower C near the extremes so colours stay in gamut;
- check each step's sRGB fallback: high-chroma OKLCH can fall outside sRGB (P3 screens show more). DTCG 2025.10 colour objects carry `{colorSpace, components, alpha, hex}`; the `hex` is the fallback, and `eos design check` warns when it disagrees with the components.
- Radix's 12-step scale is a good role map: steps 1–2 app backgrounds, 3–5 component backgrounds (normal, hover, pressed), 6–8 borders, 9–10 solid fills, 11–12 text.

**3. Contrast: WCAG 2.2 AA is the requirement.**
| What | Minimum | Criterion |
|---|---|---|
| body text and images of text | 4.5:1 | 1.4.3 |
| large text (≥ 18 pt, or 14 pt bold) | 3:1 | 1.4.3 |
| UI component boundaries, focus indicators, meaningful graphics | 3:1 against adjacent colours | 1.4.11 |
Thresholds are not rounded: 4.499:1 fails. Colour is never the only cue (1.4.1): errors get an icon and text, links in text get an underline, chart series get labels or patterns.

**4. APCA is advisory, not a standard.** The WCAG 3 Working Draft says the contrast algorithm "is yet to be determined". APCA reports Lc values (Lc 90 preferred for body text, 75 minimum for body columns, 60 for other readable text, 45 for headlines, 30 absolute minimum, 15 for non-text) and argues WCAG 2 overstates contrast for dark colours. Use it as a second opinion on dark themes and thin fonts; pass WCAG 2 for compliance. eos does not embed APCA (its code licence is not on our allow-list); use the official calculator by hand.

**5. Dark mode is a second palette, not an inversion.**
- Remap each semantic role; re-check every on-pair (`eos design check` checks `.dark` / `@media (prefers-color-scheme: dark)` blocks and dark token files separately).
- Lower chroma for large surfaces, raise lightness of action colours so they still read on dark surfaces, keep shadows subtle (use lighter surfaces for elevation).
- Respect the OS setting by default; offer a manual toggle that persists.
- Phones in sunlight: test light mode outdoors at full brightness; low-contrast "subtle" greys disappear first.

**6. Meaning colours.** Keep danger, warning and success distinguishable in lightness, not only hue, so they survive colour-vision deficiency and grayscale (see `design/data-visualisation`). Reserve the brand accent for one job; don't reuse danger red as a brand colour.

**7. What `eos design check` does.** Validates DTCG colour objects (colour space, component ranges, alpha, hex fallback), resolves aliases, then computes the WCAG 2 ratio for on-colour pairs found by name (`X` + `on-X`, `X` + `X-foreground`, `background` + `foreground`) in token files and in CSS custom properties per theme block, plus pairs you list in `.eos/config.json` (`"design": {"contrast_pairs": [{"fg": "color.focus", "bg": "color.bg", "min": 3}]}`). A failing pair is an error. `eos design contrast "<fg>" "<bg>"` checks one pair (hex, rgb, hsl, oklch, lab, color()).

## Examples
```json
"color": { "$type": "color",
  "action":    { "$value": "{color.base.green.700}" },
  "on-action": { "$value": "{color.base.paper.50}" },
  "base": { "green": { "700": { "$value": { "colorSpace": "oklch", "components": [0.46, 0.105, 155], "hex": "#14693d" } } } } }
```
```
$ eos design contrast "oklch(0.556 0 0)" "oklch(0.97 0 0)"
4.33:1 (#737373 on #f5f5f5): text 4.5:1 FAIL ...      # stock shadcn muted-foreground on muted
```
Fix it by darkening the foreground one step. If a pair is never used for text, add the foreground name to `design.contrast_ignore` in `.eos/config.json` and say why in the PR.

## Anti-patterns
- Components using primitives (`green-700`) or literal hex instead of roles.
- Picking "brand purple" first and discovering later that white text on it fails.
- Dark mode by `filter: invert()` or by swapping only background and text.
- Rounding 4.47:1 up to "4.5"; checking contrast only in light mode.
- Status shown by colour alone (green/red dots without text).
- Relying on APCA alone for compliance.

## Checks
- `eos design check` in `eos verify` (UI or token changes) and `eos check`.
- axe in e2e for rendered contrast (`frontend/accessibility`); it sees real backgrounds, the token check sees intent. Use both.
- Critique rubric row 5, including a dark-mode screenshot and a grayscale screenshot for colour-only cues.

## Sources
- MDN, oklch(): https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/oklch
- Evil Martians, OKLCH in CSS: https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl
- DTCG Color Module 2025.10: https://www.designtokens.org/tr/2025.10/color/
- WCAG 2.2 Understanding 1.4.3 Contrast (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- WCAG 2.2 Understanding 1.4.11 Non-text Contrast: https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- WCAG 2.2 Understanding 1.4.1 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- W3C, WCAG 3.0 Working Draft: https://www.w3.org/TR/wcag-3.0/
- APCA in a Nutshell: https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html
- Radix Colors, Understanding the scale: https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
- Tailwind CSS, Colors: https://tailwindcss.com/docs/colors
