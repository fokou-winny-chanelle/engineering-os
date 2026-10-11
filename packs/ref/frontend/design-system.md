---
id: frontend/design-system
title: Implementing a design system in code (DTCG tokens, Tailwind v4 theme variables, CSS Modules, runtime CSS-in-JS limits, cva variants, headless primitives Radix/React Aria, shadcn/ui ownership model)
area: frontend
read_when: setting up styling for a new frontend, adding or renaming design tokens, building a Button/Input/Dialog component, choosing a component or headless library, adding dark mode or a second brand theme, a component has too many boolean props
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.designtokens.org/tr/2025.10/format/", "https://tailwindcss.com/docs/theme", "https://nextjs.org/docs/app/getting-started/css", "https://nextjs.org/docs/app/guides/css-in-js", "https://cva.style/docs", "https://www.radix-ui.com/primitives/docs/overview/introduction", "https://react-aria.adobe.com/", "https://ui.shadcn.com/docs", "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html"]
---
# Design system implementation

Visual direction and UX decisions live in the `design-direction` and `ux-design` packs. This ref is about turning those decisions into code that stays consistent: tokens, a styling approach, variant APIs and accessible primitives.

## Decision guide

**1. Tokens first.** Every colour, space, radius, font size, shadow and motion duration used by components comes from a named token; components never contain raw hex or pixel values.
- Two layers: primitive tokens (`green-600`, `space-4`) and semantic tokens (`color-action-primary`, `color-text-danger`, `space-inline-md`). Components use only semantic tokens; themes (dark mode, a partner brand) remap semantic to primitive.
- Store the source in the W3C Design Tokens Community Group format (first stable version 2025.10: JSON with `$value`, `$type`, aliases) when designers export tokens or several platforms (web + React Native) consume them; generate CSS variables and a TS object from it. For a single web app, CSS variables in one file are enough.
- Check contrast when defining semantic pairs: 4.5:1 for normal text, 3:1 for large text and UI component boundaries (WCAG 1.4.3 / 1.4.11, AA).

**2. Styling approach.**
| Approach | Good for | Watch out for |
|---|---|---|
| Tailwind CSS v4 | most Next.js apps; Next.js docs recommend it for most styling | tokens go in `@theme { --color-…: …; }` (theme variables become utilities and CSS variables); long class strings need variant helpers |
| CSS Modules | component-specific styles Tailwind can't express; teams that prefer CSS | name files `<name>.module.css`; keep global CSS imports in the root layout |
| runtime CSS-in-JS (styled-components, Emotion, MUI) | existing codebases | works only in Client Components with a style registry; Emotion support was still listed as in progress; adds client JS |
| zero-runtime CSS-in-TS (vanilla-extract, Panda, StyleX) | typed tokens without runtime cost | build-plugin setup; check Turbopack support for the version you pin |
| React Native web sharing | one design system for app + web | see `frontend/react-native-web` |
Pick one primary approach per app. Mixing two runtime systems doubles CSS and ordering bugs.

**3. Variants instead of boolean props.** Model visual options as a small enum API (`variant: primary | secondary | danger`, `size: sm | md | lg`) generated with `class-variance-authority` (0.7.x stable; `cva` 1.0 is in beta at the time of writing) or Tailwind Variants. Use compound variants for combinations, export the variant prop types, and merge caller classes with `tailwind-merge` so overrides win predictably.

**4. Behaviour from headless primitives.** Do not hand-build dialog, menu, combobox, tabs, tooltip, select or date picker; focus traps, keyboard handling and ARIA wiring are hard (`frontend/accessibility`).
| Library | Notes |
|---|---|
| Radix Primitives | "low-level UI component library with a focus on accessibility"; unstyled; base of shadcn/ui |
| React Aria Components (Adobe) | 50+ components, built-in i18n (localised date/number formatting and parsing, RTL); strong for date pickers and complex inputs |
| shadcn/ui | not a dependency: copies component source into your repo ("not a component library. It is how you build your component library"); you own upgrades and fixes |
| full kits (MUI, Mantine, Chakra) | fastest for internal tools; heavier bundles and harder to make look like your brand |
Wrap whatever you choose in your own `components/ui/*` so the app imports `Button` from you, not from the vendor.

**5. Component API rules.** Forward `ref` and spread remaining native props; `asChild`/slot pattern for polymorphism instead of `as` props that break types; controlled + uncontrolled support for inputs; no data fetching inside design-system components; every interactive component has keyboard and focus-visible styles; text comes in as props (translatable), never hard-coded.

## Examples
```css
/* app/globals.css: Tailwind v4 theme variables as the token source */
@import "tailwindcss";
@theme {
  --color-brand-600: oklch(0.55 0.15 150);
  --color-action-primary: var(--color-brand-600);
  --radius-control: 0.5rem;
}
```
```ts
// components/ui/button-variants.ts
import { cva, type VariantProps } from "class-variance-authority";
export const button = cva("inline-flex items-center justify-center rounded-control font-medium focus-visible:outline-2 disabled:opacity-50 min-h-11", {
  variants: {
    variant: { primary: "bg-action-primary text-white", secondary: "border", danger: "bg-red-700 text-white" },
    size: { sm: "px-3 text-sm", md: "px-4", lg: "px-6 text-lg" },
  },
  defaultVariants: { variant: "primary", size: "md" },
});
export type ButtonVariants = VariantProps<typeof button>;
```

## Anti-patterns
- Raw hex values and arbitrary Tailwind values (`bg-[#1a7f37]`, `mt-[13px]`) scattered through feature code.
- `<Button primary large outlined danger>` boolean soup with impossible combinations.
- Hand-rolled modal with a `div` and a click-outside handler; removing focus outlines without a replacement.
- Installing a second component kit for one widget.
- Treating shadcn/ui as an npm dependency that will be patched for you.

## Checks
- Lint for raw colours in components (stylelint `color-no-hex` in CSS Modules, or a review rule for arbitrary Tailwind values).
- Storybook or a `/dev/ui` route with every variant, plus axe in e2e (`testing/e2e-playwright`).
- Visual regression on the design-system page only, not every screen (`testing/flaky-speed`).
- Review: new component uses semantic tokens, a headless primitive for complex behaviour, and has keyboard support.

## Sources
- Design Tokens Format Module 2025.10 (DTCG): https://www.designtokens.org/tr/2025.10/format/
- Tailwind CSS, Theme variables: https://tailwindcss.com/docs/theme
- Next.js, CSS: https://nextjs.org/docs/app/getting-started/css
- Next.js, CSS-in-JS: https://nextjs.org/docs/app/guides/css-in-js
- cva docs: https://cva.style/docs
- Radix Primitives, Introduction: https://www.radix-ui.com/primitives/docs/overview/introduction
- React Aria: https://react-aria.adobe.com/
- shadcn/ui docs: https://ui.shadcn.com/docs
- WCAG 2.2 Understanding 1.4.3 Contrast (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
