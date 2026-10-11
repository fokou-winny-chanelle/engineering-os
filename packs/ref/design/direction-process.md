---
id: design/direction-process
title: Setting a design direction (brand attributes, audience, mood, references and moodboards, anti-references, the one bold thing)
area: design
read_when: writing or revising docs/design/direction.md, starting a new product or landing page, a redesign, choosing a visual theme, a stakeholder says "make it look modern" or "like X"
verified: 2026-10-10
revisit_days: 180
sources: ["https://claude.com/blog/improving-frontend-design-through-skills", "https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb", "https://www.nngroup.com/articles/visual-hierarchy-ux-definition/", "https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html", "https://datareportal.com/reports/digital-2025-cameroon"]
---
# Design direction process

A direction is a short written decision that makes later choices fast and consistent. Without one, a model fills every gap with the statistical average of the web: Anthropic calls this "distributional convergence" and lists the result as Inter, purple gradients on white and minimal animation. The direction is how you leave the average on purpose. Template: `eos new design`; tokens: `eos scaffold design-tokens`.

## Decision guide

**1. Start from the subject, not from a UI kit (30 minutes, written).**
- Who: the main user group, their device and setting (a phone in bright sun at a market stall? a laptop in an office?), their language(s), reading comfort, data budget. For a Cameroonian audience see `design/cameroon-context`.
- Job: the one task the product must make easy. Everything else is secondary.
- World: materials, vernacular, places and objects of the domain (a pharmacy, a bus station, a tontine meeting). Distinctive choices come from here.

**2. Brand attributes as a constrained pair list.** Write 3 adjectives and 3 anti-adjectives, each with a visible consequence:
| Attribute | Means on screen | Anti-attribute | Avoid |
|---|---|---|---|
| trustworthy | plain numbers, receipts, calm colour | flashy | gradients, confetti |
| warm | rounded type, human photos, "you" voice | corporate | stock handshake photos |
| quick | one primary action, short forms | busy | three CTAs per screen |
Adjectives without consequences ("modern", "clean") decide nothing; replace them.

**3. Mood and references.**
- Collect 6–12 references, at least half from outside software (signage, packaging, print, architecture, local textiles or markets). For each, write what to take (a type contrast, a colour relationship, a density), never the whole look.
- Add 2–3 **anti-references**: real screens that show what you must not become (often: the default template of your framework, a competitor's look, a generic SaaS landing page).
- A moodboard is a working file (Figma page, a folder of screenshots). Put the links and the "take this" notes in direction.md, not just images; images and fonts need a licence before shipping.

**4. Commit to decisions that tokens can encode.**
- Palette: 4–6 roles (background, surface, text, action, accent, danger) with values in OKLCH + hex (`design/colour`).
- Type: 1–2 families with roles and a scale (`design/typography`).
- Space, radius, elevation, motion durations (`design/layout-hierarchy`, `design/motion-icons-imagery`).
- Layout concept: an ASCII wireframe of the key screen.
- **The one bold thing**: the single memorable move (an unusual type pairing, a strong colour field, a distinctive data display). Everything else stays quiet so it reads.

**5. Run the generic check before building.** Go through `design/generic-ai-look`; for every default you reject, write what you chose instead. Anthropic's cookbook notes that banning one default makes the model pick the next-most-common one (it names Space Grotesk), so name your choice, not only the ban.

**6. Validate cheaply, then lock.**
- Build one key screen with real content (real French and English strings, real amounts in FCFA).
- Critique it with screenshots against the rubric (`design/critique-rubric`), two rounds minimum.
- A human approves direction.md for a new product or a redesign. After that, change it only on purpose, in its own PR.

**Questions to ask the stakeholder** (answers go in direction.md): Who must trust this, and what makes them trust? What must it never look like? Which local references feel right? Which screens matter most? What brand assets and font licences exist already?

## Examples
```markdown
## Personality
- adjectives: dependable (tabular numbers, receipts), neighbourly ("vous" voice, real faces), brisk (one action per screen)
- anti: casino-like, bank-cold, startup-cute
- references: Douala bus-station signage (big numerals, two colours) → take the numeral scale;
  printed market receipts → take the monospace totals; one textile pattern → a thin border motif only
- anti-references: the stock shadcn dashboard; a purple-gradient fintech landing page
- one bold thing: oversized tabular amounts in a deep green field on the payment screen
```

## Anti-patterns
- Starting from a component kit or a template and "adding brand later": the template becomes the brand.
- Mood words with no on-screen consequence ("clean, modern, sleek").
- Copying a famous product's look (also a legal risk); moodboards made only of other apps.
- Five bold ideas at once; nothing stands out when everything does.
- Choosing fonts or photos without checking licences and French accent coverage.
- Skipping the human approval and letting the first generated screen become the direction.

## Checks
- `docs/design/direction.md` exists and has adjectives with consequences, references with "take this" notes, anti-references, tokens, the one bold thing and the rejected-defaults table.
- `eos design check` passes on the token files that encode the direction.
- One reference screen critiqued twice (`eos new critique "<screen>"`), screenshots in the PR, then human approval.

## Sources
- Anthropic, Improving frontend design through Skills: https://claude.com/blog/improving-frontend-design-through-skills
- Anthropic cookbook, Prompting for frontend aesthetics: https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb
- NN/g, Visual hierarchy: https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- Canada.ca Content Style Guide (audience needs, plain language): https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html
- DataReportal, Digital 2025: Cameroon: https://datareportal.com/reports/digital-2025-cameroon
