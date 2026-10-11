---
id: frontend/nextjs-rendering-data
title: Next.js App Router rendering and data (Server vs Client Components, fetching, caching in 16.x with and without Cache Components, revalidation, streaming, SSR/SSG/ISR/PPR/CSR per use case)
area: frontend
read_when: adding a page or layout, deciding where a component runs, fetching data in a Server Component, adding or debugging caching or revalidation, choosing static vs dynamic rendering, a page is slow to first byte
verified: 2026-10-10
revisit_days: 120
sources: ["https://nextjs.org/docs/app/getting-started/caching", "https://nextjs.org/docs/app/api-reference/config/next-config-js/cacheComponents", "https://nextjs.org/docs/app/api-reference/directives/use-cache", "https://nextjs.org/docs/app/guides/caching-without-cache-components", "https://nextjs.org/docs/app/getting-started/revalidating", "https://nextjs.org/docs/app/getting-started/server-and-client-components", "https://nextjs.org/docs/app/guides/streaming", "https://nextjs.org/docs/app/guides/static-exports", "https://react.dev/reference/rsc/use-client"]
---
# Next.js App Router: rendering and data

Checked against Next.js **16.4** docs. Caching changed twice in two majors, so first find out which model the project uses: `cacheComponents: true` in `next.config.*` means the Cache Components model below; otherwise it is the "previous model". Never apply advice from one model to the other.

## Decision guide

**1. Where a component runs.**
- Server Component (default): data access, secrets, heavy libraries, markdown rendering. Its code never ships to the browser.
- Client Component (`"use client"` at the top of a file): state, effects, event handlers, browser APIs. The directive marks a boundary: everything that file imports is client code too. Put it on small leaves (a button, a form), not on layouts.
- Props crossing the boundary must be serializable (React: plain data, Server Functions, JSX; no class instances or functions other than Server Functions). Pass Server Components to Client Components as `children` instead of importing them.
- `import "server-only"` in modules with secrets or DB access makes a client import fail the build.

**2. Fetching.** Fetch in Server Components close to where data is used; start independent requests together (`Promise.all`) to avoid waterfalls. Call your data layer or backend directly; do not call your own Route Handlers from Server Components (an extra HTTP hop). Client-side fetching is for data that changes while the page is open (`frontend/state-forms`).

**3. Caching with Cache Components** (`cacheComponents: true`; new `create-next-app` apps have it plus `partialPrefetching`):
- Data fetching is **dynamic by default**. Opt in with `"use cache"` at the top of an async function (data level) or component/page (UI level). Arguments and captured values form the cache key.
- Always pair it with `cacheLife(...)`; without one the implicit `default` profile applies (stale 5 min on the client, revalidate 15 min, no time expiry). Tag with `cacheTag` for targeted invalidation.
- Cached scopes cannot call `cookies()`, `headers()` or read `searchParams`, even in helpers they call. Read those outside and pass values in, or use `"use cache: private"`.
- Runtime cache entries live in memory (LRU) by default and may not survive between serverless requests; `"use cache: remote"` uses a platform cache handler.
- Uncached async work must sit inside `<Suspense>` with a fallback; the dev overlay flags a "blocking route" otherwise. `Math.random()`, `Date.now()`, `crypto.randomUUID()` need `await connection()` + Suspense (per request) or `use cache` (shared).
- Requires the Node.js runtime (`runtime = 'edge'` routes must migrate).

**4. Caching without Cache Components (previous model):** `fetch` is **not cached by default**; opt in per request with `cache: 'force-cache'` or `next: { revalidate, tags }`; `unstable_cache` for non-fetch work; route segment config (`export const revalidate`, `dynamic`). Reading `cookies()`/`headers()` makes the whole route dynamic.

**5. Revalidation after a mutation** (both models): `updateTag(tag)` in a Server Action when the user must see their own write immediately; `revalidateTag(tag, 'max')` for stale-while-revalidate in actions or Route Handlers; `revalidatePath` when tags are not set up. Personalised data is never cached in a shared entry: put the user id in the key or do not cache it.

**6. Rendering strategy per use case.**
| Page | Strategy | How (16.x) |
|---|---|---|
| marketing, docs, blog | static (SSG), CDN | no runtime APIs; `generateStaticParams` for known slugs |
| catalogue, prices that change hourly | ISR / cached | `use cache` + `cacheLife('hours')` + tags (or `revalidate` in the previous model) |
| product page with cart/user bits | PPR: static shell + streamed dynamic holes | Cache Components default; dynamic parts in `<Suspense>` |
| dashboard, account, payments history | dynamic SSR per request | runtime APIs inside Suspense; never shared cache |
| highly interactive tool behind login | CSR inside a server-rendered shell | Client Component + query library; still render the frame on the server |
| no server available (static hosting) | `output: 'export'` | no Server Actions, cookies, Proxy, ISR, default image optimisation, or dynamic routes without `generateStaticParams` |

**7. Streaming.** `loading.tsx` gives a route-level fallback; sibling `<Suspense>` boundaries stream independently. Put boundaries around slow, non-critical parts and keep the LCP element in the shell. Once streaming starts the status is already `200`: a later `notFound()` only injects a `noindex` meta tag and `redirect()` becomes a client-side redirect, so call them before any `await` or Suspense boundary when the status code matters.

## Examples
```tsx
// lib/catalog.ts — shared, cacheable data
import { cacheLife, cacheTag } from "next/cache";
export async function getProducts(category: string) {
  "use cache";
  cacheLife("hours");
  cacheTag(`products:${category}`);
  return db.product.findMany({ where: { category } });
}
// app/shop/[category]/page.tsx — cart is per user, so it streams outside the cache
export default async function Page({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params; // async in 16 (sync access removed)
  return (<><ProductGrid items={await getProducts(category)} />
    <Suspense fallback={<CartSkeleton />}><Cart /></Suspense></>);
}
```

## Anti-patterns
- `"use client"` on a layout or page "to make hooks work", pulling the whole tree into the bundle.
- Assuming fetch caching defaults from Next 13/14 tutorials, or mixing `use cache` advice into a project without Cache Components.
- Reading cookies inside a `use cache` function, or caching per-user data under a shared key.
- Sequential awaits for independent data; fetching your own API route from a Server Component.
- `export const dynamic = 'force-dynamic'` everywhere to silence errors instead of placing Suspense boundaries.

## Checks
- `next build` (CI full check) fails on blocking-route and serialization errors; read the route summary for static vs dynamic.
- eslint-config-next: `@next/next/no-async-client-component` (`eos scaffold eslint-next`).
- Review: every `use cache` has `cacheLife` and no user data in a shared key; every mutation revalidates something.
- E2E against `next build && next start` (`testing/e2e-playwright`).

## Sources
- Next.js, Caching (Cache Components): https://nextjs.org/docs/app/getting-started/caching
- Next.js, cacheComponents: https://nextjs.org/docs/app/api-reference/config/next-config-js/cacheComponents
- Next.js, use cache: https://nextjs.org/docs/app/api-reference/directives/use-cache
- Next.js, Caching and Revalidating (Previous Model): https://nextjs.org/docs/app/guides/caching-without-cache-components
- Next.js, Revalidating: https://nextjs.org/docs/app/getting-started/revalidating
- Next.js, Server and Client Components: https://nextjs.org/docs/app/getting-started/server-and-client-components
- Next.js, Streaming: https://nextjs.org/docs/app/guides/streaming
- Next.js, Static Exports: https://nextjs.org/docs/app/guides/static-exports
- React, 'use client': https://react.dev/reference/rsc/use-client
