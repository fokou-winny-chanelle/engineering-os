---
id: design/generic-ai-look
title: Recognising and avoiding the generic "AI look" (default fonts, purple gradients, stock shadcn/Tailwind theme, card grids, emoji icons, newer tells) and what eos design check flags
area: design
read_when: reviewing generated UI, a screen "looks like every AI demo", before building a landing page or dashboard, writing the rejected-defaults table, triaging eos design check warnings
verified: 2026-10-10
revisit_days: 120
sources: ["https://claude.com/blog/improving-frontend-design-through-skills", "https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb", "https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md", "https://tailwindcss.com/docs/colors", "https://tailwindcss.com/docs/font-family", "https://tailwindcss.com/docs/box-shadow", "https://nextjs.org/docs/app/getting-started/fonts", "https://ui.shadcn.com/docs/theming", "https://www.unicode.org/faq/emoji_dingbats.html", "https://www.nngroup.com/articles/icon-usability/"]
---
# The generic "AI look"

Models converge on the most common patterns in their training data ("distributional convergence", Anthropic). Without guidance the result "will almost always conform to Inter fonts, purple gradients on white backgrounds, and minimal animations". None of these is wrong alone; together, unchosen, they say "nobody decided anything". The fix is a written direction (`design/direction-process`), not a different set of clichés.

## Decision guide

**1. Know the tells.** Sources in brackets: A = Anthropic blog/cookbook, S = Anthropic `frontend-design` skill (vendored, pending sign-off), T = Tailwind/shadcn defaults, B = named in our brief (common, not measured).
| Tell | Why it reads as default | Instead |
|---|---|---|
| Inter, Roboto, Open Sans, Lato, Arial or the system stack as the only family (A); Space Grotesk as the "escape" (A) | the most frequent web fonts; Tailwind's `--font-sans` is the system stack (T); the Next.js font docs and the create-next-app template use Geist | a display face with character + a quiet text face, licensed, with French accents (`design/typography`) |
| purple/indigo/violet gradient on white (A) | stock palette names (`indigo-500 → purple-600`) are one keystroke away | a colour from the subject's world; flat colour fields; gradients only with a reason |
| stock shadcn theme: neutral base, `--radius: 0.625rem`, `--primary: oklch(0.205 0 0)` (T) | identical to thousands of apps | your palette and radius in tokens (`design/colour`) |
| identical rounded cards with the same soft shadow (`0 1px 3px rgb(0 0 0 / 0.1)`, Tailwind `shadow-sm`) (S, T) | the "SaaS card kit" | vary density and grouping; use rules, whitespace and alignment instead of boxes |
| centred hero + three feature cards + gradient blob (B) | the template layout | lead with the product doing its job (a real screen, real numbers) |
| cream background + serif + terracotta; near-black + one acid accent; broadsheet hairlines (S) | the newer "tasteful AI" defaults | only if the subject calls for it, with a written reason |
| ALL-CAPS eyebrow over every heading; one accented word per headline; "A · B · C" meta strings; "→" on every button; 01/02/03 on things that are not steps (S) | decoration standing in for hierarchy | hierarchy from size, weight and position (`design/layout-hierarchy`) |
| fade-up on every section (S) | motion with no meaning | motion only to explain a change (`design/motion-icons-imagery`) |
| big number + small label + gradient accent hero (S) | stat-card cliché | show the number where it is used, with its unit and source |
| emoji as icons (🚀 ✨ ✅) | glyphs differ by platform (Unicode allows "a great deal of flexibility" in emoji presentation); meaning is ambiguous | one icon set with text labels (NN/g: few icons are universal) |

**2. Generate past the default.** Ask for 2–3 distinct directions in words before code, pick one, and name concrete choices (font names, OKLCH values, a layout sketch). The skill's own method: plan, build, then review against the plan and "remove one accessory".

**3. Review with screenshots, not code.** The look is only visible rendered. Use the rubric in `design/critique-rubric`; row 2 is this table.

**4. What `eos design check` flags** (warnings by default; set `"design": {"generic": "error"}` or `"raw_colors": "error"` in `.eos/config.json` to fail the gate):
- literal colours in components: CSS declarations, Tailwind arbitrary colours (`bg-[#1a1a1a]`), inline style colours, hex string literals;
- purple/indigo/violet/fuchsia gradient utilities (`bg-linear-to-r from-indigo-500 to-purple-600`);
- the unchanged shadcn theme values above;
- only default/AI-typical font families declared (Inter, Roboto, Arial, Helvetica, Open Sans, Lato, Geist, Space Grotesk, system stacks), or no font declared at all;
- animation with no `prefers-reduced-motion` / `motion-reduce:` / `useReducedMotion` anywhere;
- emoji in UI markup;
- more than `stock_palette_max` (25) stock palette classes (`bg-slate-100`, `text-blue-600` …).
It cannot judge taste: a centred hero, generic copy or card monotony need the human or screenshot critique.

## Examples
```tsx
// Flagged: stock gradient, arbitrary colour, emoji icon
<section className="bg-linear-to-r from-indigo-500 to-purple-600 text-[#fafafa]"><h1>🚀 Launch faster</h1></section>
// Direction-led: semantic tokens, real content, an icon with a label
<section className="bg-action text-on-action"><h1>Payez votre facture ENEO en 3 étapes</h1>
  <Button><ReceiptIcon aria-hidden /> Voir le reçu</Button></section>
```

## Anti-patterns
- Replacing one cliché with the next (Inter → Space Grotesk; purple → cream + terracotta) without a reason from the subject.
- Silencing the lint instead of deciding (add `allow_files` only for charts, emails or OG images, with a comment why).
- Treating "no generic tells" as "good design": hierarchy, copy and states still decide usability.
- Copying a well-known brand's look to avoid looking generic.

## Checks
- `eos design check` (runs in `eos verify` for UI changes and in `eos check`).
- Rejected-defaults table in direction.md filled, each with "what we chose instead".
- Critique rubric row 2 scored on real screenshots.

## Sources
- Anthropic, Improving frontend design through Skills: https://claude.com/blog/improving-frontend-design-through-skills
- Anthropic cookbook, Prompting for frontend aesthetics: https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb
- Anthropic skills, frontend-design SKILL.md (Apache-2.0, pinned): https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md
- Tailwind CSS, Colors: https://tailwindcss.com/docs/colors
- Tailwind CSS, font-family: https://tailwindcss.com/docs/font-family
- Tailwind CSS, box-shadow: https://tailwindcss.com/docs/box-shadow
- Next.js, Fonts (Geist example): https://nextjs.org/docs/app/getting-started/fonts
- shadcn/ui, Theming: https://ui.shadcn.com/docs/theming
- Unicode, Emoji and dingbats FAQ: https://www.unicode.org/faq/emoji_dingbats.html
- NN/g, Icon usability: https://www.nngroup.com/articles/icon-usability/
