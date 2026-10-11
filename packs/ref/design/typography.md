---
id: design/typography
title: Typography for product UI (type scale, pairing, line length and height, fluid sizes, variable fonts, French accents and spacing, Cameroonian names, font performance)
area: design
read_when: choosing fonts, defining or changing the type scale, body text feels hard to read, French text overflows or breaks badly, adding a web font, fonts slow the first render, text must hold names in Cameroonian languages
verified: 2026-10-10
revisit_days: 180
sources: ["https://practicaltypography.com/line-length.html", "https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html", "https://web.dev/articles/variable-fonts", "https://utopia.fyi/type/calculator/", "https://nextjs.org/docs/app/getting-started/fonts", "https://fonts.googleapis.com/css2?family=Inter", "https://fr.wikipedia.org/wiki/Espace_ins%C3%A9cable", "https://www.academie-francaise.fr/questions-de-langue", "https://en.wikipedia.org/wiki/General_Alphabet_of_Cameroon_Languages", "https://www.w3.org/International/articles/article-text-size.en"]
---
# Typography

Type carries most of a UI's personality and most of its readability. Decide families, roles and a scale once, encode them as tokens (`font.*`, `text.*`, `leading.*` in `eos scaffold design-tokens`), and never set ad-hoc sizes in components.

## Decision guide

**1. Pairing: one or two families, each with a job.**
- Display (headings, big numbers, the "one bold thing") may have character; text (body, labels, inputs) must be calm and legible at 14–16 px on a cheap phone.
- A common safe structure: a distinctive display face + a neutral text face, or one superfamily with optical sizes. A mono only for codes, receipts or tabular data.
- Avoid the default-only set (Inter/Roboto/Arial/system/Geist alone; see `design/generic-ai-look`). Check the licence (desktop, web, app embedding) before the font appears in a mock.

**2. Scale: few steps, used consistently.**
- Pick one ratio from a 16 px base (the scaffold uses about 1.25) and stop at 6–8 steps (`sm, base, lg, xl, 2xl, 3xl`). Every size in code is a token.
- Fluid sizes: `clamp(min, preferred, max)` between two viewport widths (Utopia's calculator generates the scale). Keep `rem` units so user zoom and browser font settings work.
- Line height: around 1.5 for body (the value WCAG tests with), tighter for large headings. WCAG 1.4.12 requires that content still works when users force line height 1.5, paragraph spacing 2× the font size, letter spacing 0.12em and word spacing 0.16em: never fix heights on text containers.
- Line length: 45–90 characters for body text (Butterick); set `max-width` in `ch` (about `65ch`) on prose, not on the whole page.

**3. Variable fonts.** One variable file can replace several static weights (web.dev: "can significantly reduce font file sizes"); five registered axes (`wght`, `wdth`, `ital`, `slnt`, `opsz`), with `wght` the one reliably set from CSS via `font-weight`. Use `opsz` where available for small labels vs big headings. Still subset and limit to the weights you use.

**4. French is not English with accents.**
- Accented capitals are correct and required ("l'accent a pleine valeur orthographique", Académie française): `À`, `É`, `Ç` in titles and ALL-CAPS buttons. Test `text-transform: uppercase` with French strings.
- Spacing: a narrow no-break space (U+202F) before `; ? !` and as the thousands separator; a no-break space (U+00A0) before `:` and inside `« »`. Many sites use U+00A0 everywhere; either way the punctuation must never wrap alone to the next line. `Intl.NumberFormat("fr-FR")` already emits U+202F in `1 234 567`, and `fr-CM` currency output is `15 000 FCFA` with a no-break space before FCFA: format with Intl, never by hand (`frontend/i18n-l10n`).
- Text translated from English is typically longer, and short labels expand the most (W3C: a 300% English-to-Italian expansion is "not at all surprising" for a short string). Let buttons and tabs wrap or grow; test with the longest real string.
- Use `lang="fr"` / `lang="en"` on the document (and on mixed-language spans) so hyphenation, screen readers and quotes behave.

**5. Glyph coverage for local names.** Google Fonts' "latin" subset covers U+0000–00FF, œ (U+0152–0153), general punctuation (U+2000–206F, which includes U+202F) and €; French needs nothing more. Names written with the General Alphabet of Cameroon Languages use letters such as ɛ ɔ ŋ ə and combining tone marks (á à â ǎ ā), which need **Latin Extended** subsets and good combining-mark support. Test a sample line ("ɛ ɔ ŋ ə Ɛ Ɔ Ŋ ɛ́ ɔ̀ ǎ ā") in the chosen font before committing; a missing glyph falls back to another font mid-word.

**6. Performance.**
- Self-host (Next.js `next/font` self-hosts Google Fonts: "no requests are sent to Google by the browser"; for other stacks, ship WOFF2 from your origin).
- Load only needed subsets and weights; prefer one variable file; `font-display: swap` (or `optional` for non-brand text) so text shows immediately.
- Preload only the font used above the fold. Measure with Lighthouse (`frontend/web-vitals-budgets`); on slow networks fonts compete with content.
- Native apps: bundle fonts with the app (Expo `expo-font`, Flutter `pubspec.yaml`), respect the OS text-size setting (Dynamic Type / font scale).

## Examples
```css
@theme {
  --font-display: "Your Display", ui-serif, serif;   /* licensed, Latin Extended subset */
  --font-body: "Your Text", system-ui, sans-serif;
  --text-base: clamp(1rem, 0.96rem + 0.2vw, 1.125rem);
}
.prose { max-width: 65ch; line-height: 1.5; }
```
```ts
new Intl.NumberFormat("fr-CM", { style: "currency", currency: "XAF" }).format(15000); // "15 000 FCFA" (no-break spaces)
```

## Anti-patterns
- More than two families, or a new size per component (`text-[15px]`).
- Fixed-height text boxes and buttons that clip French or enlarged text.
- Unaccented capitals ("ETAPE SUIVANTE"), straight quotes for «  », thousands with a plain space that wraps.
- Light weights (300) for body text on low-contrast backgrounds.
- Loading 6 static weights of 2 families from a third-party CDN on a 3G connection.

## Checks
- Type tokens exist and components use only them (raw sizes show up in review; `eos design check` flags default-only fonts).
- Screenshot critique row 4: longest French string, 200% zoom, 320 px width.
- A WCAG 1.4.12 text-spacing bookmarklet or Playwright style injection on key pages.
- Lighthouse font requests and LCP within budget.

## Sources
- Butterick's Practical Typography, Line length: https://practicaltypography.com/line-length.html
- WCAG 2.2 Understanding 1.4.12 Text Spacing: https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
- web.dev, Introduction to variable fonts on the web: https://web.dev/articles/variable-fonts
- Utopia, Fluid type scale calculator: https://utopia.fyi/type/calculator/
- Next.js, Fonts: https://nextjs.org/docs/app/getting-started/fonts
- Google Fonts CSS API (subset unicode ranges): https://fonts.googleapis.com/css2?family=Inter
- Wikipédia, Espace insécable: https://fr.wikipedia.org/wiki/Espace_ins%C3%A9cable
- Académie française, Questions de langue (accentuation des majuscules): https://www.academie-francaise.fr/questions-de-langue
- Wikipedia, General Alphabet of Cameroon Languages: https://en.wikipedia.org/wiki/General_Alphabet_of_Cameroon_Languages
- W3C Internationalization, Text size in translation: https://www.w3.org/International/articles/article-text-size.en
