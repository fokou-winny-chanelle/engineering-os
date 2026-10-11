# Design direction: <product>

Status: draft | approved by <human> on YYYY-MM-DD

## Subject
- Product and its one main job:
- Who uses it, where, on what device (light, network, hands busy?):
- The product's world (materials, vernacular, local culture) to draw from:

## Personality
- 3 adjectives:
- 3 anti-adjectives (what it must never feel like):
- 2–3 references and what to take from each (never copy a product's look):

## Tokens (source of truth: `design/tokens/*.tokens.json`, DTCG 2025.10; `eos scaffold design-tokens`)
| Role | Name | Value (OKLCH + hex) | Contrast pair checked |
|---|---|---|---|
| Background | | | |
| Surface | | | |
| Text | | | |
| Action | | | |
| Accent | | | |
| Danger | | | |

- Type families and roles (display / body / mono if needed), with licence:
- Type scale (e.g. 12 / 14 / 16 / 20 / 28 / 40):
- Spacing scale, radius scale, elevation, motion durations:

## Layout concept
```
(ASCII wireframe of the key screen)
```
Alignment, grid, density:

## The one bold thing
What will people remember? Everything else stays quiet.

## Rejected defaults (and what we chose instead)
| Default | Our choice |
|---|---|
| Inter/Roboto everywhere | |
| Purple/indigo gradient on white | |
| Identical rounded cards with one soft shadow | |
| ALL-CAPS eyebrow labels / one highlighted headline word | |
| Fade-up on every section | |

## Quality floor
WCAG 2.2 AA; targets ≥ 24 px (44–48 on touch); visible focus; reduced motion; 320 px wide; 200% zoom; French and English lengths; low-end Android.

## Critique log
Scored sheets live in `docs/design/critiques/` (`eos new critique "<screen>"`).

| Round | Screenshot | What was generic / wrong | Change |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
