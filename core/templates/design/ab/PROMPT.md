# Task (identical in both arms except the "Context" section)

You are designing three screens for a product team in Cameroon. The specs are in `specs/`. For each spec,
create `screens/<spec-file-name-without-.md>/` containing:

- `docs/design/direction.md`: a short design direction (adjectives, references, palette roles, type, the one
  bold thing, the defaults you rejected and why).
- `design/tokens/base.tokens.json` (and `dark.tokens.json` if you design dark): DTCG 2025.10 tokens. Every
  colour in the CSS comes from these tokens (as CSS custom properties).
- `src/index.html` + `src/styles.css`: a static, self-contained page showing the screen. Show every required state
  (e.g. sections or a state switcher). No JavaScript frameworks, no external images; a `<link>` to a
  free-licence web font is allowed.

Before you finish each screen run `{{EOS}} design check --dir screens/<name>` and fix every error.
Work alone, in this folder only. Do not look at the other arm's folder. Stop when the three screens are done.

## Context
{{CONTEXT}}
