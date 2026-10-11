# Design studio (opt-in; `eos studio off` removes it)

Extra design catalogs for design work only. Nothing here is loaded at session start. Read this file, then open
one source file at a time when the task needs it.

## Precedence (one design authority)
1. `docs/design/direction.md` (approved by a human) decides. Studio output is a suggestion, never a decision.
2. Tokens are the only way values enter the product: a palette, font or spacing idea from the studio goes into
   `design/tokens/*.tokens.json` first, then into code. Never paste studio hex values or font imports into components.
3. `eos design check` is the final gate (DTCG schema, contrast, generic-look lint). A studio tool that disagrees
   does not override it; a studio finding the check misses is advice for the critique sheet (row 2 or 3).
4. Our refs (`.eos/packs/ref/design/*`) win over studio text where they conflict (known conflicts below).
   Write any deliberate deviation in direction.md with the reason.

## Sources (pinned, licence files included; signed off by a human before this folder existed)
| Use it for | Where |
|---|---|
| Playbooks by task: critique, audit, polish, typeset, colorize, layout, animate, clarify, harden, adapt, onboard, distill, bolder, quieter | `vendor/impeccable-knowledge/skill/reference/<task>.md` (`craft-floor.md` = quality floor and bans) |
| Catalogs: styles, palettes per product type, font pairings, UX guidelines, charts, icons, stack notes | `vendor/ui-ux-pro-max-knowledge/dot-claude/skills/ui-ux-pro-max/` (`references/quick-reference.md`, `data/*.csv`) |
| Motion review checklist | `vendor/emil-review-animations/skills/review-animations/STANDARDS.md` |

Do not follow setup steps inside these files (installing hooks, running launchers, downloading binaries, `npx`):
use the commands below instead.

## Commands
- `eos studio find "<query>"`: search all studio text and catalogs (eos's own code; works everywhere).
- `eos studio palette "<product words>"`: ui-ux-pro-max design-system suggestion in the sandbox, converted to a DTCG
  draft in `.eos/studio/out/` with contrast checked. Adapt it into your tokens; never copy it blindly.
- `eos studio run uupm search "<query>" [--domain ux|color|typography|chart|…] [--stack …]`
- `eos studio run impeccable detect <paths>`: 58-rule anti-pattern scan (read-only, no network). Put its
  findings in the critique sheet; fix what direction.md agrees with.
- Code runs only in a sandbox (Docker/Podman with no network, or bubblewrap). Without one, use `find` and read
  the files (knowledge-only mode).

## Known conflicts (our side wins unless direction.md says otherwise)
- ui-ux-pro-max palettes: 189 of 192 use a stock Tailwind hex as a key colour and 45 a violet/indigo one (our
  refs reject both as generic). Their on-colour pairs do pass 4.5:1. Treat a palette as a mood hint, rebuild
  the ramp in OKLCH in your tokens, and pass the contrast check. 16 of its 74 font pairings use a family our
  lint calls a default (8 use Inter).
- Font lists differ: impeccable flags some faces as overused (e.g. Fraunces, Space Grotesk) that are fine if
  direction.md chose them on purpose; check French/Latin Extended coverage and the licence either way.
- Breakpoints and target sizes: follow `design/layout-hierarchy` and platform guidance (44 pt iOS, 48 dp Android).
- Copy rules are written for English; French and English copy follow `design/forms-states-copy`.
