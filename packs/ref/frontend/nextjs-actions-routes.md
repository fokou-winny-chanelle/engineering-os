---
id: frontend/nextjs-actions-routes
title: Next.js Server Actions, Route Handlers, Proxy (formerly middleware), BFF and environment variables in 16.x
area: frontend
read_when: writing a Server Action or form submit, adding a Route Handler or webhook endpoint, editing proxy.ts or middleware.ts, deciding where auth checks go, adding an environment variable to a Next.js app
verified: 2026-10-10
revisit_days: 120
sources: ["https://nextjs.org/docs/app/guides/server-actions", "https://nextjs.org/docs/app/guides/data-security", "https://nextjs.org/docs/app/getting-started/route-handlers", "https://nextjs.org/docs/app/getting-started/proxy", "https://nextjs.org/docs/app/guides/upgrading/version-16", "https://nextjs.org/docs/app/guides/authentication", "https://nextjs.org/docs/app/guides/environment-variables", "https://nextjs.org/docs/app/getting-started/error-handling", "https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw"]
---
# Next.js Server Actions, Route Handlers and Proxy

Every Server Action and Route Handler is a public HTTP endpoint, whatever the UI shows. Proxy runs before routing and is for cheap request shaping, not for security decisions. Checked against Next.js 16.4.

## Decision guide

**1. Which server entry point.**
| Need | Use |
|---|---|
| a form or button in your own UI changes data | Server Action (`"use server"`), called from `<form action>` or `useActionState` |
| webhooks, mobile app or third-party clients, file downloads, non-mutation JSON for client libraries | Route Handler (`app/**/route.ts`, Web `Request`/`Response`) |
| redirects, rewrites, headers (CSP nonce, locale), coarse "is there a session cookie" redirects | `proxy.ts` (renamed from `middleware.ts` in 16) |
| the business logic itself | a server-only data/service layer both of the above call |
A backend in another language (FastAPI, Flask) stays the system of record; Next.js acts as a backend-for-frontend that calls it with server-side credentials (`api/contract-first` for the typed client).

**2. Server Actions: what the framework does and does not do.**
- It compiles each action to an encrypted ID that POSTs back to the page; unused actions are stripped; captured closure variables are encrypted (set `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` to one stable value when you run several instances or self-host).
- It rejects requests whose `Origin` differs from `Host`/`X-Forwarded-Host` (add proxy/CDN domains to `serverActions.allowedOrigins`) and caps bodies at 1 MB (`serverActions.bodySizeLimit`).
- It does **not** authenticate, authorize or validate. Inside every action: get the session, check permission on the object (not just "logged in"), parse `FormData` with a schema (`frontend/state-forms`), and return only what the UI needs, never the raw row. Accept an id from the client, never ownership or prices.
- Model expected failures (validation, "insufficient balance") as return values read by `useActionState`; throw only for bugs (caught by `error.tsx`).
- After the write, invalidate: `updateTag` (user sees it now), `revalidateTag(tag, 'max')`, `revalidatePath`, or `refresh()`; `redirect()` last.
- The client dispatches actions one at a time. Do not `Promise.all` several actions; do parallel work inside one action.
- Payments and other non-repeatable effects: send an idempotency key from the form (hidden input generated once per form render) and enforce it server-side (`security/payments`); disable the submit button while pending. Retries happen: double clicks, reconnects, and Next's experimental offline mode re-runs actions when the network returns (`frontend/low-bandwidth`).

**3. Route Handlers.** Supported methods GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS (others get 405). A `route.ts` cannot sit beside a `page.tsx` in the same segment. In the previous caching model only `GET` can be cached (`dynamic = 'force-static'`); with Cache Components `GET` follows the page model (prerendered when it reads no runtime data). Same rules as actions: auth, validation, rate limits, safe errors (`api/errors-problem-details`). Webhooks verify signatures on the raw body (`api/webhooks`).

**4. Proxy (`proxy.ts`).**
- One file per project, at the root or in `src/` next to `app/`; export `proxy` (the `middleware` name is deprecated; the v16 upgrade codemod migrates it). Its runtime is Node.js and cannot be changed; keep `middleware.ts` only if you still need the edge runtime.
- Use it for redirects that need request data, rewrites, A/B routing, headers, locale negotiation, and optimistic auth redirects. The docs say it is not for slow data fetching and not a full session or authorization solution; `fetch` cache options have no effect there.
- Narrow it with `config.matcher` (skip `_next/static`, `_next/image`, favicons and prefetches) so it does not run on every asset.
- Never rely on Proxy alone for authorization: a 2025 Next.js advisory (CVE-2025-29927) let attackers skip middleware with a crafted header. Repeat the check in the data layer.

**5. Environment variables.** `NEXT_PUBLIC_*` values are inlined into client JavaScript at `next build` and frozen; changing them later needs a rebuild, and anything there is public. Everything else is server-only and readable in Server Components, actions and handlers. `serverRuntimeConfig`/`publicRuntimeConfig` were removed in 16. Validate all variables once at startup in `env.ts` (`ops/runtime-config`).

## Examples
```ts
"use server";
import { z } from "zod";
import { updateTag } from "next/cache";
const Transfer = z.object({ toWallet: z.string().uuid(), amountXaf: z.coerce.number().int().positive(), key: z.string().uuid() });
export async function transfer(_: unknown, form: FormData) {
  const session = await getSession();                       // 1. who
  if (!session) return { error: "auth" } as const;
  const input = Transfer.safeParse(Object.fromEntries(form)); // 2. what
  if (!input.success) return { fieldErrors: z.flattenError(input.error).fieldErrors };
  const r = await wallets.transfer(session.userId, input.data); // 3. permission + idempotency inside the service
  if (!r.ok) return { error: r.code } as const;               // expected failure: a value, not a throw
  updateTag(`wallet:${session.userId}`);
  return { ok: true, balanceXaf: r.balanceXaf } as const;      // 4. minimal result
}
```

## Anti-patterns
- Checking auth only in the page, layout or proxy and trusting that the action "can only be called from there".
- Returning ORM objects from actions; accepting `userId` or `price` from the form.
- `middleware.ts` doing database queries on every request; no matcher.
- Secrets in `NEXT_PUBLIC_*`; expecting a `NEXT_PUBLIC_` change to apply without rebuilding.
- Calling your own Route Handler from a Server Component.

## Checks
- `.semgrep/eos-frontend.yml` (`eos scaffold web-security`): private `process.env` read in `"use client"` files; tokens in web storage.
- Unit tests for the service layer (auth and permission branches); one e2e per critical action (`testing/e2e-playwright`).
- Review checklist per action: session, object permission, schema, minimal return, invalidation, idempotency for money.
- `eos verify` puts files with money/auth words in the risky lane (line-by-line human review).

## Sources
- Next.js, Server Actions and Mutations: https://nextjs.org/docs/app/guides/server-actions
- Next.js, Data Security: https://nextjs.org/docs/app/guides/data-security
- Next.js, Route Handlers: https://nextjs.org/docs/app/getting-started/route-handlers
- Next.js, Proxy: https://nextjs.org/docs/app/getting-started/proxy
- Next.js, Upgrading to version 16: https://nextjs.org/docs/app/guides/upgrading/version-16
- Next.js, Authentication: https://nextjs.org/docs/app/guides/authentication
- Next.js, Environment variables: https://nextjs.org/docs/app/guides/environment-variables
- Next.js, Error handling: https://nextjs.org/docs/app/getting-started/error-handling
- GitHub advisory GHSA-f82v-jwr5-mffw (CVE-2025-29927): https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw
