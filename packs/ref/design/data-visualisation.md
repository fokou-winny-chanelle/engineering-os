---
id: design/data-visualisation
title: Data visualisation in product UI (chart choice, palettes by data type, colour-blind and grayscale safety, labelling, tables, numbers and FCFA amounts, accessible charts)
area: design
read_when: adding a chart, dashboard, KPI tile or report, choosing chart colours, a chart is hard to read on a phone, showing money or percentages to non-specialists, making a chart accessible
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.datawrapper.de/blog/colors-for-data-vis-style-guides", "https://carbondesignsystem.com/data-visualization/color-palettes/", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html", "https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html", "https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html", "https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2014/03/Grameen-Presentation.pdf"]
---
# Data visualisation

A chart is for one question ("is my balance going up?", "which branch is late?"). Choose the chart for the question, label it so it can be read without a legend hunt, and make sure it survives a small screen, grayscale and a screen reader.

## Decision guide

**1. Start with the question and the reader.** Write the one-sentence takeaway as the chart title ("Ventes en hausse de 12 % depuis juin", not "Ventes"). For lay audiences, a single big number with a comparison often beats a chart; for experts, a dense table may beat both.

**2. Chart type by task.**
| Task | Use | Avoid |
|---|---|---|
| compare categories | horizontal bar (labels fit, also in French) | pie with > 3 slices, 3D |
| change over time | line (few series), column for few periods | dual axes |
| part of whole | stacked bar or a single proportion bar | donut grids |
| exact values, lookup | table (sortable, aligned numbers) | chart with data labels on every point |
| distribution | histogram, dot plot | averages alone |
Start bar axes at zero; label units; show the data source and date.

**3. Palettes by data type** (Carbon names: categorical, sequential, diverging, alert).
- Categorical: distinct hues for unrelated groups; Datawrapper advises not more than seven colours in one chart; group or switch chart type beyond that. Keep a category's colour the same across charts.
- Sequential: one hue from light to dark, consistent lightness steps, so it "should work in black and white, too"; avoid rainbow scales.
- Diverging: two clearly distinct hues around a meaningful midpoint, with a light grey centre (not white).
- Alert: reserve status colours for status; don't reuse danger red as a series colour.
- Highlight one series in the action colour and grey the rest instead of colouring everything.
- Store chart colours as tokens (`color.chart.1…7`, `color.chart.seq.*`) so dark mode remaps them; keep chart colour files in `design.allow_files` only if they must hold literals.

**4. Accessibility.**
- Colour is never the only encoding (WCAG 1.4.1): direct labels at line ends, patterns or markers, the value in text.
- Lines, bars and markers needed to read the chart need 3:1 against the background (WCAG 1.4.11).
- Different lightness per series lets readers with colour-vision deficiency tell them apart (Datawrapper); check with a simulator.
- Provide the numbers: a visible table toggle or a caption with the key figures; an SVG chart gets `role="img"` and a text summary, or a real `<table>`.
- Canada.ca for tables: simple structure, row and column headers, no blank cells (write "no data", "0" or "n/a").

**5. Numbers people trust.**
- Format with `Intl.NumberFormat` per locale (`frontend/i18n-l10n`): French uses a narrow no-break space for thousands and a comma for decimals.
- `Intl` formats `XAF` with zero decimals ("15 000 FCFA"); never add ",00". The GSMA/Grameen mobile-money research advises "Drop the decimals" in balances and withdrawal amounts for lower-literacy users.
- Round for display, keep exact values in tooltips or tables; tabular figures (`font-variant-numeric: tabular-nums`) for columns of numbers.
- Percent and percentage points are different; say which.

**6. Small screens and slow networks.** Charts must reflow: fewer ticks, horizontal bars, labels above bars, a summary number first. Prefer server-rendered SVG or a light library over a heavy charting bundle for one sparkline; lazy-load dashboards below the fold.

## Examples
```tsx
<figure>
  <figcaption>Encaissements en hausse de 12 % depuis juin (source : caisse, 10 oct. 2026)</figcaption>
  <LineChart data={d} stroke="var(--color-chart-1)" aria-hidden />
  <details><summary>Voir les chiffres</summary><table>{/* month | amount in FCFA */}</table></details>
</figure>
```

## Anti-patterns
- A dashboard of 12 KPI tiles with gradient accents and no question.
- Rainbow or stock-palette series colours chosen by the chart library.
- Legends far from the data; tooltips as the only way to read values (no hover on phones).
- Truncated bar axes; dual y-axes; 3D; pies with many slices.
- Decimals on FCFA amounts; numbers formatted with string concatenation.

## Checks
- Grayscale screenshot of each chart in the critique (rubric row 5) and a phone-width screenshot (row 6).
- Chart colours come from tokens; `eos design check` contrast pairs can include chart series against the surface (`min: 3`).
- axe on the page; the chart has a text or table alternative.

## Sources
- Datawrapper, What to consider when choosing colors for data visualization: https://www.datawrapper.de/blog/colors-for-data-vis-style-guides
- Carbon Design System, Data visualization color palettes: https://carbondesignsystem.com/data-visualization/color-palettes/
- WCAG 2.2 Understanding 1.4.11 Non-text Contrast: https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- WCAG 2.2 Understanding 1.4.1 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- Canada.ca Content Style Guide (tables): https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html
- GSMA / Grameen Foundation, Gender and usability (mobile financial services): https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2014/03/Grameen-Presentation.pdf
