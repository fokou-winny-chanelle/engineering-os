---
id: frontend/low-bandwidth
title: Building web frontends for low bandwidth and low-end devices (Cameroon/Central Africa context, JS cost, data saver signals, offline handling with Next.js useOffline and TanStack Query, PWAs and service workers, safe retries)
area: frontend
read_when: the audience is on mobile data or low-end Android (Cameroon, Central/West Africa, rural users), adding offline support or a PWA, a page is heavy, deciding what to load on slow connections, retries could duplicate a payment
verified: 2026-10-10
revisit_days: 120
sources: ["https://datareportal.com/reports/digital-2025-cameroon", "https://infrequently.org/2024/01/performance-inequality-gap-2024/", "https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Save-Data", "https://developer.mozilla.org/en-US/docs/Web/API/Network_Information_API", "https://nextjs.org/docs/app/guides/offline-support", "https://nextjs.org/docs/app/guides/progressive-web-apps", "https://tanstack.com/query/latest/docs/framework/react/guides/network-mode"]
---
# Low bandwidth and low-end devices

Design for the user who pays per megabyte on a mid-range Android phone with a weak signal. What helps them (less JavaScript, server rendering, small images, honest offline states) also helps everyone else. Network, hosting region and API resilience are in `ops/africa-connectivity`.

## Decision guide

**1. Know the context, measure your own users.** DataReportal (Digital 2025: Cameroon): 12.4 million internet users in January 2025 (41.9% of the population) and 25.5 million cellular connections (some voice/SMS only); Ookla's median fixed download speed was 9.48 Mbps (no mobile median was published there). Treat these as context, then get your own field data by device and connection (`frontend/web-vitals-budgets`). Test on a real low-end Android phone, not only an emulator.

**2. Ship less JavaScript.** It costs at least three times more per byte than HTML/CSS/images on low-end devices (Russell 2024), and it costs CPU and battery after download.
- Server-render by default; Client Components only for interactive leaves (`frontend/nextjs-rendering-data`).
- Script budget around 365 KiB compressed for a JS-heavy page at a 3 s target (the `eos scaffold lighthouse` default); much less for content pages.
- Every dependency and third-party script must earn its bytes (`frontend/assets-bundles`); no client-side analytics zoo.
- Forms must work before hydration (`<form action>`; `frontend/state-forms`).

**3. Fewer bytes on the wire.**
- Images: correct `sizes`, modern formats, lazy below the fold; consider lower quality for thumbnails. System fonts or one subset variable font.
- Cache static assets long (`_next/static` is content-hashed and immutable) and HTML/data smartly (`architecture/caching`); compress text (gzip/brotli at the CDN).
- Paginate and paginate again: small first page, "load more" rather than infinite prefetching. Prefetch less on slow connections (Next `<Link prefetch={false}>` for long lists of links).
- Test with Lighthouse's mobile preset (150 ms RTT, 1.6 Mbps down) and a slower custom profile in DevTools for the worst cases.

**4. Data-saver signals: progressive enhancement only.** The `Save-Data` request header and `navigator.connection` (`saveData`, `effectiveType`) have limited availability according to MDN (not Baseline; missing in some major browsers). Use them to skip autoplay video, high-res images and prefetching when present; never require them. Offer an explicit in-app "light mode / save data" setting stored in a cookie so the server can honour it.

**5. Offline and flaky connections.**
- Show the state: a visible offline banner, paused instead of endless spinners, and "saved locally / will send when online" only if that is true.
- Next.js `experimental.useOffline` (16.x) keeps failed navigations, RSC fetches, prefetches and Server Actions pending and retries them when the connection returns, with a `useOffline` hook for UI. The docs mark it experimental and not recommended for production yet; test it with `next build && next start`.
- Because pending Server Actions are retried automatically, every action with side effects must be idempotent (idempotency key per form render, enforced server-side; `security/payments`).
- TanStack Query: network mode `online` (default) pauses queries and mutations offline and resumes in order; `offlineFirst` when a service worker or HTTP cache may answer (`frontend/state-forms`).
- Real offline content needs a service worker. Next's PWA guide names Serwist as one option for service-worker caching. Cache the app shell and read-only data; don't cache personalised HTML or API responses with personal data in a shared cache; version and expire caches.

**6. PWA.** A web app manifest (`app/manifest.ts`) plus HTTPS lets browsers offer installation; Next's guide notes install prompts do not need offline support. Installation saves app-store downloads on constrained phones, but a PWA does not replace SMS/USSD for critical notifications (`ops/africa-connectivity`). Custom install buttons via `beforeinstallprompt` do not work on iOS Safari.

## Examples
```tsx
// Respect an explicit data-saver choice (cookie) or the Save-Data header when present
import { cookies, headers } from "next/headers";
export async function wantsLight() {
  const c = (await cookies()).get("data_saver")?.value;
  if (c) return c === "1";
  return (await headers()).get("save-data") === "on";
}
// in a Server Component: const light = await wantsLight(); render a static poster instead of a video if light
```

## Anti-patterns
- A 1–2 MB client bundle for a page that mostly shows text and prices.
- Spinners that never end offline; retrying payment requests without idempotency keys.
- Requiring `navigator.connection` or the Save-Data header for core behaviour.
- Service workers caching authenticated pages or never expiring old caches.
- Testing only on office Wi-Fi and a flagship phone.

## Checks
- Lighthouse CI budgets (`eos scaffold lighthouse`) and `eos bundle-size` ratchet.
- e2e with Playwright's `context.setOffline(true)` around one critical action: UI shows offline state, nothing is submitted twice (`testing/e2e-playwright`, `testing/mobile-qa`).
- Field vitals segmented by connection type and device class.

## Sources
- DataReportal, Digital 2025: Cameroon: https://datareportal.com/reports/digital-2025-cameroon
- Alex Russell, The Performance Inequality Gap, 2024: https://infrequently.org/2024/01/performance-inequality-gap-2024/
- Lighthouse, Throttling: https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md
- MDN, Save-Data header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Save-Data
- MDN, Network Information API: https://developer.mozilla.org/en-US/docs/Web/API/Network_Information_API
- Next.js, Offline support: https://nextjs.org/docs/app/guides/offline-support
- Next.js, Progressive Web Apps: https://nextjs.org/docs/app/guides/progressive-web-apps
- TanStack Query, Network Mode: https://tanstack.com/query/latest/docs/framework/react/guides/network-mode
