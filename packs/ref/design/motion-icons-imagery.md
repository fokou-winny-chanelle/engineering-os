---
id: design/motion-icons-imagery
title: Motion and micro-interactions (purpose, durations, easing, reduced motion), iconography and illustration (labelled icon sets, licences), imagery (authentic photos, alt text, weight)
area: design
read_when: adding animation, transitions or micro-interactions, a screen feels static or over-animated, choosing an icon set or illustrations, adding photos or hero images, writing alt text, eos design check warns about reduced motion or emoji
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.nngroup.com/articles/animation-duration/", "https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion", "https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html", "https://developer.apple.com/design/human-interface-guidelines/motion", "https://www.nngroup.com/articles/icon-usability/", "https://www.unicode.org/faq/emoji_dingbats.html", "https://lucide.dev/license", "https://github.com/phosphor-icons/homepage", "https://github.com/google/material-design-icons", "https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html"]
---
# Motion, icons and imagery

All three are easy to overdo and expensive on slow phones. Each should earn its place: motion explains a change, an icon speeds recognition next to a label, an image shows something words can't.

## Decision guide

**1. Motion has a job or it goes.** Good jobs: feedback (a press, a toggle, a saved state), continuity (where did this panel come from), orientation (a sheet slides from where it lives), drawing attention to one change. Apple's HIG: use motion "purposefully"; gratuitous or excessive animation can distract and make people "physically uncomfortable". Allow at most one orchestrated moment per product (an onboarding reveal, a payment success), not fade-up on every section.

**2. Durations and easing as tokens** (`duration.fast/base/slow`, `ease.standard/out`). NN/g: most UI animations belong in 100–500 ms; simple feedback such as a checkbox or toggle about 100 ms; "far more common for animations to be too long than too short". Use ease-out for things entering, ease-in for leaving, and never block input while an animation plays.

**3. Reduced motion is mandatory in practice.**
- CSS: wrap movement in `@media (prefers-reduced-motion: no-preference)` or remove it under `reduce` (MDN). Tailwind: `motion-safe:` / `motion-reduce:` variants. Framer Motion / Motion: `useReducedMotion()` or `<MotionConfig reducedMotion="user">`. React Native: `AccessibilityInfo.isReduceMotionEnabled()`; Reanimated has `ReduceMotion` settings.
- Under reduce: replace movement (slide, zoom, parallax) with a cross-fade or an instant change; keep essential feedback.
- WCAG 2.3.3 (AAA) asks that motion triggered by interaction can be disabled; NN/g notes parallax, scroll-jacking and big movements can make people with vestibular disorders dizzy or nauseated.
- `eos design check` warns when a project animates (keyframes, `animate-*`, motion libraries, transform transitions) and has no reduced-motion handling anywhere.

**4. Performance.** Animate `transform` and `opacity` only; avoid animating layout properties, large blurs and shadows on low-end Android. Lottie and video backgrounds cost data: load them only where they explain something, never autoplay large files.

**5. Icons: one set, labelled.**
- NN/g: few icons are universally recognised (home, print, the magnifier for search); most need a **text label**. Icon-only buttons are acceptable only for universal actions, and still need an accessible name (`aria-label`).
- Pick one set and one stroke weight; size on the type scale; colour from `currentColor` so tokens apply.
- Licensed, free sets: Lucide (ISC), Phosphor (MIT), Material Symbols (Apache-2.0). Record the licence in direction.md.
- Not emoji: Unicode leaves "a great deal of flexibility" in emoji glyphs, so they look different per phone brand and OS version and carry ambiguous meaning; the lint flags emoji in UI markup.
- For lower-literacy audiences pair icons with words, keep the same icon for the same meaning everywhere, and test recognition with users (`design/critique-rubric`, `design/cameroon-context`).

**6. Illustration.** Use a consistent style tied to the direction (line weight, palette from tokens, how people are drawn). Avoid generic "corporate blob people" and AI-generated scenes with wrong details (hands, text, local signage). Represent your users: local settings, skin tones, clothing, languages on signs.

**7. Imagery.**
- Real product screens and real places beat stock. Photos need a licence and model releases; record them.
- Alt text: describe the function or content in about 140 characters or less; decorative images get `alt=""` (Canada.ca guide). Never put essential text inside images (translation, zoom, contrast).
- Weight: responsive sizes, modern formats (AVIF/WebP), lazy-load below the fold, explicit dimensions to avoid layout shift (`frontend/assets-bundles`, `frontend/low-bandwidth`). Data plans and reliable network access vary (Canada.ca); for users paying per megabyte a hero photo is a real cost.

## Examples
```css
.sheet { transition: opacity var(--duration-base) var(--ease-out); }
@media (prefers-reduced-motion: no-preference) {
  .sheet { transition: transform var(--duration-base) var(--ease-out), opacity var(--duration-base) var(--ease-out); }
}
```
```tsx
<Button variant="secondary"><DownloadIcon aria-hidden className="size-5" /> Télécharger le reçu</Button>
<IconButton aria-label="Rechercher"><SearchIcon aria-hidden /></IconButton>  {/* universal icon: label still required */}
```

## Anti-patterns
- Fade-up or parallax on every section; scroll-jacking; looping decorative animations.
- Animations that delay the user (a 1-second success animation before the next step).
- Mixing icon sets; icons with no label for non-universal actions; emoji as icons.
- Stock photos of handshakes and laptops; AI images with garbled text or wrong local details.
- Text baked into images; 2 MB hero images.

## Checks
- `eos design check`: reduced-motion handling present, no emoji icons.
- Playwright with `page.emulateMedia({ reducedMotion: "reduce" })` (the critique screenshot spec does this).
- Lighthouse image and total-byte budgets (`frontend/web-vitals-budgets`); jsx-a11y `alt-text` rule.
- Critique rubric rows 9 and 11.

## Sources
- NN/g, Executing UX animations: duration and motion characteristics: https://www.nngroup.com/articles/animation-duration/
- MDN, prefers-reduced-motion: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- WCAG 2.2 Understanding 2.3.3 Animation from Interactions: https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- Apple HIG, Motion: https://developer.apple.com/design/human-interface-guidelines/motion
- NN/g, Icon usability: https://www.nngroup.com/articles/icon-usability/
- Unicode, Emoji and dingbats FAQ: https://www.unicode.org/faq/emoji_dingbats.html
- Lucide licence (ISC): https://lucide.dev/license
- Phosphor Icons (MIT): https://github.com/phosphor-icons/homepage
- Material Design icons / Symbols (Apache-2.0): https://github.com/google/material-design-icons
- Canada.ca Content Style Guide (images, alt text): https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html
