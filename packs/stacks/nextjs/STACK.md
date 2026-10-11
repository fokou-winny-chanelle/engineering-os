---
id: nextjs
title: Next.js (App Router)
kind: stack
mode: files
when: editing a Next.js app (app/, server actions, route handlers, middleware/proxy)
description: Next.js App Router conventions - server vs client components, data fetching and caching, server actions security, route handlers, env vars, images/fonts, performance and testing.
globs: ["**/app/**", "**/next.config.*", "**/middleware.ts", "**/proxy.ts", "**/instrumentation*.ts", "**/src/app/**"]
markers: ["next.config.js", "next.config.mjs", "next.config.ts"]
contains: []
requires: ["typescript"]
fast_check: ""
full_check: "{pm} run build"
ci: ""
---
# Stack: Next.js App Router (adds to TypeScript pack)

## Ground truth
Read the docs for the installed version (check `next` in package.json and use the docs MCP). Next.js changes quickly. For example, `next lint` was removed in v16, so use ESLint or Biome directly. Prefer the official codemods (`npx @next/codemod`) for upgrades.

## Rules
1. Server Components are the default. Add `"use client"` only for interactivity, browser APIs or client state, and push it to the leaves. Never import server-only code (DB, secrets) into client components; mark it with `import "server-only"`.
2. Data fetching on the server.
   - Call the backend through the generated typed client from Server Components or route handlers.
   - Be explicit about caching and revalidation per fetch or segment, as described in the docs for your version. Never rely on defaults you haven't checked.
   - Personalised or authenticated data must not be cached across users.
3. Server Actions and route handlers are public HTTP endpoints. Treat them that way:
   - authenticate and authorise inside each one;
   - validate input with a schema;
   - rate-limit;
   - return safe errors;
   - add idempotency for payments.
   Hiding a button is not authorisation.
4. BFF pattern. The browser talks to Next.js; Next.js talks to the API (FastAPI/Flask/…) with server-side credentials. Tokens go in httpOnly, Secure, SameSite cookies, never localStorage.
5. Env vars.
   - `NEXT_PUBLIC_*` is inlined into the client bundle at build time, so put nothing secret there.
   - Validate env in a single `env.ts` module.
6. UX states.
   - `loading.tsx` / Suspense for loading; `error.tsx` (a client component) with retry; `not-found.tsx`.
   - Forms show pending state via `useFormStatus`/`useActionState` and disable resubmission.
7. Performance.
   - Use `next/image` with sizes, `next/font`, and dynamic import for heavy client widgets.
   - Avoid client-side data waterfalls.
   - Next 16 build output has no JS sizes: use `eos bundle-size`, Lighthouse CI or `next analyze`.
8. Security headers. Set CSP (nonce-based if you need inline scripts), HSTS, frame-ancestors and Referrer-Policy in config or the proxy/middleware layer. Keep the middleware/proxy layer thin: no DB calls, and auth checks that also exist in the server code.
9. i18n. Use locale routing via a maintained library, `Intl` formatting, and `lang` on `<html>`.

## Testing
- Vitest + Testing Library for client components and utilities. Test async Server Components through Playwright e2e (unit tooling support is limited).
- Playwright projects for desktop and mobile viewport, `@axe-core/playwright` on key pages, and a trace on first retry.
- Run e2e against `next build && next start` (production mode), not the dev server.

## Pitfalls the AI often makes
- Writes Pages Router code (`getServerSideProps`) in an App Router app. Adds `"use client"` at the top of the tree.
- Assumes a caching default from an old version. Exposes secrets via `NEXT_PUBLIC_`.
- Calls its own route handlers from Server Components, which adds a needless hop. Call the function or the backend directly.
