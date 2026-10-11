---
id: frontend/web-vitals-budgets
title: Core Web Vitals (LCP, INP, CLS) and performance budgets (thresholds, field vs lab data, Lighthouse throttling, Lighthouse CI budget assertions, sourced byte budgets, client JS ratchet, Next.js 16 build output change)
area: frontend
read_when: setting performance targets or budgets, a page is slow on phones, adding Lighthouse CI, LCP/INP/CLS regress in field data, someone asks for the per-route JS size in Next.js 16, reviewing a change that adds client JavaScript
verified: 2026-10-10
revisit_days: 180
sources: ["https://web.dev/articles/vitals", "https://web.dev/articles/optimize-lcp", "https://web.dev/articles/inp", "https://web.dev/articles/cls", "https://web.dev/articles/tbt", "https://web.dev/articles/lab-and-field-data-differences", "https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md", "https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md", "https://infrequently.org/2024/01/performance-inequality-gap-2024/", "https://nextjs.org/docs/app/guides/upgrading/version-16", "https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals"]
---
# Core Web Vitals and performance budgets

Measure real users first (field data), use the lab (Lighthouse) to catch regressions before release, and fail CI on budgets so performance does not erode one dependency at a time. Hosting-side latency and caching are in `architecture/api-performance` and `ops/africa-connectivity`; asset tactics are in `frontend/assets-bundles`.

## Decision guide

**1. Targets.** Core Web Vitals "good" thresholds, judged at the 75th percentile of page loads, split by mobile and desktop:
| Metric | Good | Measures | Lab proxy |
|---|---|---|---|
| LCP Largest Contentful Paint | ≤ 2.5 s | loading of the main content | LCP in Lighthouse |
| INP Interaction to Next Paint | ≤ 200 ms | responsiveness to every tap/click/key (replaced FID as a Core Web Vital on 12 March 2024) | TBT (Total Blocking Time; aim < 200 ms on average mobile hardware); the lab cannot measure INP itself |
| CLS Cumulative Layout Shift | ≤ 0.1 | visual stability | CLS in Lighthouse (load only; field includes later shifts) |

**2. Field data (truth).** Report vitals from real users: in Next.js a small Client Component calling `useReportWebVitals` in the root layout (keep the callback reference stable to avoid duplicate reports), or the `web-vitals` library elsewhere; send with `navigator.sendBeacon` to your analytics/OTel collector (`frontend/errors-observability`). Segment by route, device class and connection; for a Cameroon audience the low-end Android p75 is the number that matters (`frontend/low-bandwidth`). CrUX/PageSpeed Insights only covers sites with enough Chrome traffic.

**3. Diagnose by subpart.**
- LCP = time to first byte + resource load delay + resource load duration + element render delay. Slow TTFB → server/cache/CDN (`frontend/nextjs-rendering-data`); load delay → LCP image not discoverable (lazy, CSS background, client-rendered) → `fetchPriority="high"` or `preload`; duration → image too large; render delay → render-blocking JS/CSS or fonts.
- INP: long tasks during interaction. Break up work (`startTransition`, yield to the main thread), avoid re-rendering large trees per keystroke, move work to the server, ship less JS.
- CLS: reserve space for images (width/height or `fill` + sized parent), ads, embeds, banners and font swaps; Suspense fallbacks should match final size.

**4. Lab settings.** Lighthouse mobile simulates "Slow 4G": 150 ms latency, 1.6 Mbps down / 750 Kbps up, with CPU throttling to emulate a mid-tier phone. Lab numbers vary between runs and machines: run 3–5 times and assert on an aggregate, and compare against the same runner.

**5. Budgets you can defend.**
| Budget | Default in `eos scaffold lighthouse` | Source |
|---|---|---|
| total transfer ≤ 730 KiB, script ≤ 365 KiB (compressed) for a JS-heavy page | `resource-summary:total:size` 747520 B, `resource-summary:script:size` 373760 B | Alex Russell, "Performance Inequality Gap 2024": 3 s at P75 device/network over two connections (5 s → 1.3 MiB / 650 KiB) |
| LCP ≤ 2500 ms, CLS ≤ 0.1, TBT ≤ 200 ms | `largest-contentful-paint`, `cumulative-layout-shift`, `total-blocking-time` maxNumericValue | web.dev thresholds above |
JavaScript costs at least three times more per byte than HTML, CSS or images on low-end devices (same source), so the script budget is the one to protect. Tighten these for markup-heavy pages; loosen only with a written reason in the PR.

**6. Next.js 16 removed per-route `size` and `First Load JS` from `next build` output** (the Next team found them inaccurate with Server Components and recommends Lighthouse or field analytics). So route budgets live in Lighthouse CI, and growth of the emitted client JS is caught by `eos bundle-size`: it sums gzip sizes under `.next/static` (also `out/`, Vite `dist/assets`, Expo web output), compares with a committed `.eos/bundle-baseline.json`, and fails when growth exceeds the tolerance or an absolute budget you set. `next analyze` (the Turbopack bundle analyzer) shows which modules grew.

## Examples
```json
{ "ci": {
  "collect": { "numberOfRuns": 3, "startServerCommand": "npm run start", "url": ["http://localhost:3000/"] },
  "assert": { "assertions": {
    "largest-contentful-paint": ["error", { "maxNumericValue": 2500, "aggregationMethod": "median" }],
    "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1, "aggregationMethod": "median" }],
    "total-blocking-time": ["error", { "maxNumericValue": 200, "aggregationMethod": "median" }],
    "resource-summary:script:size": ["error", { "maxNumericValue": 373760 }]
  } },
  "upload": { "target": "filesystem", "outputDir": ".lighthouseci" } } }
```

## Anti-patterns
- Optimising the Lighthouse score on a fast laptop while field p75 on Android stays poor.
- Asserting on a single Lighthouse run; LHCI's default aggregation is `optimistic` (most likely to pass), which hides flakiness in both directions, so name the method.
- `upload.target: temporary-public-storage` for private apps (reports are public).
- Raising budgets silently when a PR exceeds them; looking for the removed `First Load JS` column after upgrading to Next 16.

## Checks
- `eos scaffold lighthouse`: `lighthouserc.json` with the budgets above + a CI workflow running pinned `@lhci/cli` against `next start` (human review of the numbers).
- `eos bundle-size` (`--update` to accept a reviewed baseline); `eos verify` runs it on risky/`--full` lanes when a fresh build exists.
- Field vitals dashboard with p75 per route and an alert on regressions (`ops/dashboards-alerting`).

## Sources
- web.dev, Web Vitals: https://web.dev/articles/vitals
- web.dev, Optimize LCP: https://web.dev/articles/optimize-lcp
- web.dev, INP: https://web.dev/articles/inp
- web.dev, CLS: https://web.dev/articles/cls
- web.dev, TBT: https://web.dev/articles/tbt
- web.dev, Lab and field data differences: https://web.dev/articles/lab-and-field-data-differences
- Lighthouse, Throttling: https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md
- Lighthouse CI, Configuration: https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md
- Alex Russell, The Performance Inequality Gap, 2024: https://infrequently.org/2024/01/performance-inequality-gap-2024/
- Next.js, Upgrading to version 16: https://nextjs.org/docs/app/guides/upgrading/version-16
- Next.js, useReportWebVitals: https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals
