---
id: design/tokens-pipeline
title: Design tokens pipeline and Figma-to-code (Figma variables, W3C DTCG 2025.10 files, Style Dictionary 5 builds for CSS/Tailwind, React Native and Flutter, the Figma MCP server, Code Connect, validation)
area: design
read_when: setting up tokens for a new product, moving colours or spacing out of components, syncing Figma variables with code, generating CSS/Tailwind, React Native or Flutter values from one source, implementing a Figma frame with an agent, eos design check reports token schema errors
verified: 2026-10-10
revisit_days: 120
sources: ["https://www.designtokens.org/tr/2025.10/format/", "https://www.designtokens.org/tr/2025.10/color/", "https://styledictionary.com/info/dtcg/", "https://styledictionary.com/reference/hooks/formats/predefined/", "https://registry.npmjs.org/style-dictionary/latest", "https://developers.figma.com/docs/rest-api/variables/", "https://help.figma.com/hc/en-us/articles/32132100833559", "https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/", "https://tailwindcss.com/docs/theme"]
---
# Tokens pipeline and Figma-to-code

One source of truth for colour, type, space, radius, elevation and motion; every platform's values are generated from it; nobody types a hex value into a component. `eos scaffold design-tokens` sets this up; `eos design check` guards it.

## Decision guide

**1. The pipeline.**
```
Figma variables (design)  ──read──▶  design/tokens/*.tokens.json (DTCG 2025.10, in git, reviewed)
                                            │  eos design check (schema, aliases, contrast)
                                            ▼  node design/build-tokens.mjs (Style Dictionary 5)
                       design/build/tokens.css (@theme + .dark) · tokens.js (React Native, charts) · tokens.dart (Flutter)
```
The JSON in git is the source; Figma and code are both consumers. For a single web app with no designer, CSS variables in one file are enough (`frontend/design-system`); move to DTCG when a second platform or a designer arrives.

**2. DTCG 2025.10 format essentials** (first stable version; files `*.tokens.json`, media type `application/design-tokens+json`).
- A token is an object with `$value`; groups are objects without it. `$type` may sit on a group and is inherited; a token whose type can't be determined is invalid, and tools must not guess.
- Names can't start with `$` or contain `{`, `}` or `.`. Aliases: `"{color.base.green.700}"`; JSON Pointer `$ref` also exists. Also `$description`, `$deprecated`, `$extensions`, `$extends` (group inheritance), `$root`.
- Types: `color` (object: `colorSpace` such as `srgb`, `oklch`, `display-p3`; `components`; optional `alpha`, `hex` fallback), `dimension` (`{value, unit: "px"|"rem"}`, unit required even for 0), `fontFamily`, `fontWeight` (1–1000 or names like `semi-bold`, case-sensitive), `duration` (`{value, unit: "ms"|"s"}`), `cubicBezier` (`[x1, y1, x2, y2]`, x in 0..1), `number`, and composites `strokeStyle`, `border`, `transition`, `shadow`, `gradient`, `typography`.
- Tiers: primitives (`color.base.*`) → semantic roles (`color.action`, `color.on-action`) → optional component tokens (`button.primary.bg`) only when a component truly diverges. Themes (dark, partner brand) override semantic tokens in their own file.

**3. Style Dictionary 5 (Apache-2.0, 5.6.1 at the time of writing).** Reads DTCG since v4, but "the latest format 2025.10 does not have full support yet". In 5.6.1 we observed: colour objects (including OKLCH) convert to hex correctly; DTCG `px` dimensions are wrongly treated as `rem` by the built-in Flutter transforms (2px became 32.00); duration objects print `[object Object]`. The scaffold's `build-tokens.mjs` adds small transforms for these. Built-in formats include `css/variables`, `javascript/es6`, `typescript/es6-declarations`, `android/resources`, `compose/object`, `ios-swift/class.swift`, `flutter/class.dart`.
- Tailwind v4: emit `css/variables` with `selector: "@theme"` and name groups to match theme namespaces (`color`, `font`, `text`, `spacing`, `radius`, `shadow`, `ease`) so utilities like `bg-action` and `p-4` come from tokens.
- React Native: import the ES module values into a theme object (or Unistyles/Tamagui theme); Flutter: generated `AppTokens` constants feed `ThemeData`/`ColorScheme`.
- Commit generated files or build them in CI, but never edit them by hand; CI fails if regenerated output differs.

**4. Figma variables → tokens.**
- The Figma Variables REST API needs "a Full seat in an Enterprise org": most small teams can't use it.
- With the **Figma MCP server**, an agent can read what a selection uses: `get_variable_defs` returns the variables and styles in the selection (colours, spacing, typography) with names and values; `get_design_context` returns code for a frame (React + Tailwind by default, can target your components); `get_screenshot` shows the frame; `get_metadata` gives a sparse outline for large files; `get_code_connect_map` / Code Connect maps Figma components to your code components; `create_design_system_rules` writes rules for your repo.
- Remote server `https://mcp.figma.com/mcp` is preferred and "available on all seats and plans" (it needs a link to a frame); the desktop server needs a Dev or Full seat on a paid plan and supports selection-based prompts. Writing to the canvas "will eventually be a usage-based paid feature" (free during the beta). Check your plan's rate limits.
- MCP config with tokens or OAuth stays out of git (`mcp/servers.json` pattern; secrets in the environment).

**5. Figma-to-code with an agent, safely.**
1. Tokens first: map Figma variable names to DTCG paths once (write the map in direction.md); reject frames that use raw values.
2. Ask `get_design_context` to use *your* components and token classes; treat its output as a draft.
3. Replace any literal colours, sizes or fonts it emitted with tokens (`eos design check` lists them).
4. Screenshot the result and compare with `get_screenshot` of the frame; critique with the rubric (`design/critique-rubric`), including states the frame didn't show.

## Examples
```json
{ "space": { "$type": "dimension", "4": { "$value": { "value": 1, "unit": "rem" } } },
  "duration": { "$type": "duration", "fast": { "$value": { "value": 120, "unit": "ms" } } },
  "color": { "$type": "color", "on-action": { "$value": "{color.base.paper.50}" } } }
```
```
$ eos design check
  error: design/tokens/base.tokens.json: space.0: dimension needs a unit, even for 0: {"value": 0, "unit": "px"}
  error: design/tokens/dark.tokens.json: color.on-muted on color.muted contrast 3.10:1 < 4.5:1 (WCAG 2.2 AA)
```

## Anti-patterns
- Tokens copied by hand from Figma into three places; hex values in components "just this once".
- Component tokens for everything (thousands of names nobody can review).
- Editing generated CSS/Dart; letting Figma, not git, be the place where changes happen silently.
- Shipping agent-generated Figma code without replacing literals and without checking states.
- Committing a Figma personal access token in an MCP config.

## Checks
- `eos design check` on every UI/token change (`eos verify`) and in CI (`eos check`).
- CI: run the token build and fail on a diff in generated files.
- Review: new tokens are semantic, named for roles, and their contrast pairs pass.

## Sources
- DTCG Format Module 2025.10: https://www.designtokens.org/tr/2025.10/format/
- DTCG Color Module 2025.10: https://www.designtokens.org/tr/2025.10/color/
- Style Dictionary, DTCG support: https://styledictionary.com/info/dtcg/
- Style Dictionary, Predefined formats: https://styledictionary.com/reference/hooks/formats/predefined/
- style-dictionary npm registry metadata: https://registry.npmjs.org/style-dictionary/latest
- Figma REST API, Variables: https://developers.figma.com/docs/rest-api/variables/
- Figma Help, Guide to the Figma MCP server: https://help.figma.com/hc/en-us/articles/32132100833559
- Figma, MCP server tools and prompts: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/
- Tailwind CSS, Theme variables: https://tailwindcss.com/docs/theme
