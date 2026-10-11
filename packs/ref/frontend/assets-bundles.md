---
id: frontend/assets-bundles
title: Images, fonts, third-party scripts, bundle size and code splitting in Next.js 16 (next/image sizes/preload/qualities, next/font, next/script strategies, next/dynamic, optimizePackageImports, bundle analyzer)
area: frontend
read_when: adding images or a hero banner, adding a web font, adding an analytics/chat/ads script, adding a large dependency, the client bundle grew, LCP is an image, CLS from images or fonts
verified: 2026-10-10
revisit_days: 180
sources: ["https://nextjs.org/docs/app/getting-started/images", "https://nextjs.org/docs/app/api-reference/components/image", "https://nextjs.org/docs/app/getting-started/fonts", "https://nextjs.org/docs/app/guides/scripts", "https://nextjs.org/docs/app/guides/lazy-loading", "https://nextjs.org/docs/app/guides/package-bundling", "https://nextjs.org/docs/app/guides/upgrading/version-16", "https://nextjs.org/docs/app/api-reference/config/eslint"]
---
# Images, fonts, scripts and bundles

Bytes and main-thread time are the budget (`frontend/web-vitals-budgets`). Images are usually the biggest bytes; JavaScript is the most expensive per byte. Checked against Next.js 16.4.

## Decision guide

**1. Images with `next/image`.**
- Always `alt`; `width`/`height` or static import (dimensions inferred, no CLS); `fill` only inside a positioned, sized parent.
- Set `sizes` whenever the image is responsive or uses `fill`. Without it the browser assumes `100vw` and downloads a far larger file than needed, which hurts most on mobile data.
- LCP/hero image: never lazy. The docs say most cases should use `fetchPriority="high"` or `loading="eager"`; use `preload` (which replaced the deprecated `priority` in 16) only when one known image is the LCP element on every viewport, and never together with `loading`/`fetchPriority`. Everything else stays lazy (the default).
- Next 16 defaults: `images.qualities` is `[75]` and requests for other qualities get 400 (list extra values explicitly); `minimumCacheTTL` default is 4 hours; output format follows `Accept` (`formats` default `['image/webp']`; add `'image/avif'` if your CPU budget for optimisation allows).
- Remote images need `remotePatterns` (narrow host and path). Static export (`output: 'export'`) cannot use the default loader; use a CDN loader or pre-sized files.
- Decorative backgrounds via CSS are not optimised or preloaded by `next/image`; don't make the LCP element a CSS background.

**2. Fonts with `next/font`.** It self-hosts Google or local fonts at build time (no request to Google at runtime, privacy and fewer connections) and sizes fallbacks to avoid layout shift. Use one variable font with the `latin` subset (French accents are in `latin`; add `latin-ext` only if content needs it), at most two families, set on `<html>` in the root layout. Don't use `<link>` to fonts.googleapis.com (lint rule `no-page-custom-font`). System font stacks are a valid zero-byte choice for low-bandwidth audiences (`frontend/low-bandwidth`).

**3. Third-party scripts with `next/script`.**
| strategy | Use for |
|---|---|
| `beforeInteractive` | almost never (consent manager that must run first) |
| `afterInteractive` (default) | tag managers, analytics you need early |
| `lazyOnload` | chat widgets, feedback, social embeds |
| `worker` | experimental (Partytown), not for production yet |
Load scripts only in the layouts/pages that need them. Each third party is also a CSP entry and a privacy question (`frontend/web-security`, `security/privacy`). Prefer a facade (static button that loads the chat widget on click).

**4. Code splitting.**
- Server Components are split automatically and their code never ships; keep heavy libraries (markdown, date math, charts' data prep, SDKs) in Server Components.
- Lazy-load heavy client-only pieces (editor, map, chart, modal content) with `next/dynamic` or `React.lazy` + Suspense; `ssr: false` is only allowed inside Client Components.
- Import narrowly (`import debounce from 'lodash/debounce'`), and add icon/utility packages with hundreds of exports to `experimental.optimizePackageImports` (some common libraries are already optimised automatically).
- `serverExternalPackages` keeps Node-only packages out of the server bundle.
- Prefer platform APIs over libraries: `Intl` instead of moment/date-fns locales (`frontend/i18n-l10n`), `fetch` instead of axios, CSS instead of animation libraries.

**5. Find what grew.** `next analyze` opens the Turbopack bundle analyzer (v16.1+; `@next/bundle-analyzer` for webpack builds), filterable by route and client/server. `eos bundle-size` tells you the total moved; the analyzer tells you why. Before adding a dependency, check its size and whether it is ESM/tree-shakeable (`security/supply-chain` for the trust side).

## Examples
```tsx
import Image from "next/image";
import hero from "@/public/hero-douala.jpg"; // static import: width/height/blur inferred
export function Hero() {
  return <Image src={hero} alt={t("home.heroAlt")} fetchPriority="high" placeholder="blur"
    sizes="(max-width: 768px) 100vw, 50vw" className="h-auto w-full" />;
}
// app/layout.tsx
import { Inter } from "next/font/google";
const inter = Inter({ subsets: ["latin"], display: "swap" });
// heavy client widget, loaded on demand
const MapView = dynamic(() => import("./map-view"), { ssr: false, loading: () => <MapSkeleton /> });
```

## Anti-patterns
- `<img>` for content images (lint `@next/next/no-img-element`), or `next/image` with `fill` and no `sizes`.
- `preload`/`fetchPriority="high"` on many images; lazy-loading the LCP image.
- Loading analytics, chat and A/B tools in the root layout with `beforeInteractive`.
- `"use client"` at the top of a page that imports a charting library, so the whole page ships it.
- Importing a whole icon set or `moment` with all locales.

## Checks
- `eos scaffold eslint-next`: `@next/next/no-img-element`, `no-page-custom-font`, `no-sync-scripts`, `no-css-tags` as errors.
- `eos bundle-size` ratchet; Lighthouse CI `resource-summary` budgets (`eos scaffold lighthouse`).
- Review: new dependency justified with size; images have `sizes`; at most one high-priority image per page.

## Sources
- Next.js, Image Optimization: https://nextjs.org/docs/app/getting-started/images
- Next.js, Image component API: https://nextjs.org/docs/app/api-reference/components/image
- Next.js, Font Optimization: https://nextjs.org/docs/app/getting-started/fonts
- Next.js, Scripts: https://nextjs.org/docs/app/guides/scripts
- Next.js, Lazy Loading: https://nextjs.org/docs/app/guides/lazy-loading
- Next.js, Optimizing package bundling: https://nextjs.org/docs/app/guides/package-bundling
- Next.js, Upgrading to version 16: https://nextjs.org/docs/app/guides/upgrading/version-16
- Next.js, ESLint plugin: https://nextjs.org/docs/app/api-reference/config/eslint
