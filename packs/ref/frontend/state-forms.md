---
id: frontend/state-forms
title: Client state and forms (server state with Server Components vs TanStack Query, local and URL state with nuqs, global stores, offline network modes; forms with one schema for client and server, zod 4, OpenAPI/pydantic-generated schemas, useActionState vs React Hook Form, accessible errors, double-submit safety)
area: frontend
read_when: adding client-side data fetching or a state library, putting filters/tabs/pagination in state, building or changing a form or its validation, showing server errors in a form, wiring a FastAPI/pydantic schema into TypeScript, a payment or transfer form
verified: 2026-10-10
revisit_days: 180
sources: ["https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults", "https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr", "https://tanstack.com/query/latest/docs/framework/react/guides/network-mode", "https://nextjs.org/docs/app/guides/client-side-data-fetching/tanstack-query", "https://nuqs.dev/docs/options", "https://react.dev/learn/choosing-the-state-structure", "https://nextjs.org/docs/app/guides/forms", "https://zod.dev/json-schema", "https://zod.dev/error-formatting", "https://react-hook-form.com/docs/useform", "https://heyapi.dev/openapi-ts/plugins/zod", "https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html", "https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html"]
---
# Client state and forms

Most state bugs are server data copied into client stores; most form bugs are validation that exists in only one place. Classify state first, and write each validation rule once.

## Decision guide

**1. Where each piece of state lives.**
| Kind | Example | Home |
|---|---|---|
| server data read on load | product list, account page | Server Component fetch (`frontend/nextjs-rendering-data`), no client library |
| server data that changes while open, or client-driven queries | live order status, infinite scroll, search-as-you-type, React Native | TanStack Query |
| shareable view state | filters, sort, page, tab, open modal id | URL search params (nuqs) |
| ephemeral UI | disclosure open, hover, draft text | `useState`/`useReducer` in the nearest component |
| app-wide client state | theme, locale (also cookie/URL), cart before checkout | context for rarely-changing values; a small store (Zustand, Jotai) only when many distant components write often |
Derive values during render instead of syncing copies with effects (React: avoid redundant and duplicated state).

**2. TanStack Query (v5) defaults.** `staleTime` 0 (refetch on mount, focus, reconnect; set it per query family, the SSR guide uses 60 s); inactive queries garbage-collected after 5 min (`gcTime`); failed queries retry 3 times with backoff; mutations do not retry by default (never add retries to non-idempotent mutations without an idempotency key). Query keys carry every input; build them in one factory per resource; after a mutation `invalidateQueries` or `setQueryData`. With the App Router: a new `QueryClient` per server request and one in the browser (never a module-level server client: it leaks data between users); prefetch on the server, `dehydrate` + `<HydrationBoundary>`, `staleTime` > 0.

**3. URL state with nuqs.** Typed parsers; by default updates are client-only (no server request), replace the history entry and are throttled. `shallow: false` when Server Components must re-render; `history: 'push'` only when Back should step through changes. Validate params server-side.

**4. Offline.** Network mode `online` (default) pauses queries and mutations offline (`fetchStatus: 'paused'`); paused mutations resume in order on reconnect. `offlineFirst` when a service worker or HTTP cache may answer (`frontend/low-bandwidth`).

**5. One schema, client and server.** The server always validates; client validation is only for the user.
| Backend | Source of truth | Frontend gets it by |
|---|---|---|
| Next.js only | zod schema in `lib/schemas/`, imported by form and action | import |
| FastAPI/pydantic, NestJS, other OpenAPI backend | backend models → committed `openapi.json` | generate types + zod with `@hey-api/openapi-ts` (zod plugin) or Orval; CI regenerates and fails on drift (`api/contract-first`) |
| JSON Schema | the JSON Schema | generate at build time; `z.fromJSONSchema()` is experimental |
Business rules (balance, stock, ownership) stay on the server and come back as field or form errors.

**6. Form mechanism.** Simple Next.js forms: `<form action>` + `useActionState` (works before JS loads). Complex client forms (field arrays, wizards): React Hook Form + zod resolver; its `errors` prop (7.49+) feeds server errors into fields; `progressive: true` keeps native attributes before hydration. React Native: RHF `Controller`, same schema package.

**7. Errors that everyone can use.** Return `{ fieldErrors, formError }` (`z.flattenError(err).fieldErrors` for flat schemas, `z.treeifyError` for nested; map Problem Details `errors[]` the same way, `api/errors-problem-details`). WCAG 3.3.1: text next to the field naming the problem and fix, `aria-describedby`, `aria-invalid`, focus to an error summary or first invalid field, never colour alone (`frontend/accessibility`). Messages are translation keys (`frontend/i18n-l10n`). Right `type`/`inputMode`/`autoComplete` (`tel`, `one-time-code`, `inputMode="numeric"` for amounts and PINs); visible labels; allow paste and password managers on login/OTP (3.3.8).

**8. Money and double submits.** XAF amounts are integers (`data/keys-money-time`): strip spaces (U+202F/U+00A0) and separators, then `z.coerce.number().int().positive()`. Disable submit while pending, send an idempotency key generated once per form render, enforce it server-side (`security/payments`), and after a dropped connection show "check your history" instead of inviting a second payment.

## Examples
```tsx
const [page] = useQueryState("page", parseAsInteger.withDefault(1));        // URL state
const orders = useQuery({ queryKey: orderKeys.list({ page }), queryFn: () => api.orders({ page }), staleTime: 30_000 });
const [state, action, pending] = useActionState(createInvoice, null);       // form → server action
const err = state?.fieldErrors?.amountXaf?.[0];
<input id="amount" name="amountXaf" inputMode="numeric" aria-invalid={err ? true : undefined}
  aria-describedby={err ? "amount-err" : undefined} />
```

## Anti-patterns
- Fetched data copied into Redux/Zustand/context with hand-written loading and refetch logic; `useEffect` + `fetch` + `setState`.
- A module-level `QueryClient` on the server; `staleTime: 0` with SSR prefetching.
- Filters in `useState`, so refresh, share and Back lose them.
- Validation only in the browser, or two hand-kept copies of the rules; throwing on validation failure (input lost).
- Placeholder as label; errors only in red or a vanishing toast; floats for money; automatic retries of payments.

## Checks
- Unit tests for schemas (each invalid branch, boundaries; `testing/unit-design`, `testing/property-fuzz`), query-key factories and URL parsers.
- `@tanstack/eslint-plugin-query` when TanStack Query is used; CI regenerates generated schemas and runs `git diff --exit-code`.
- e2e: reload/Back keep filters; form error state passes axe (`eos scaffold e2e-node`, `testing/e2e-playwright`).
- Review: action re-validates; errors linked to fields; submit disabled while pending; mutations invalidate the cache.

## Sources
- TanStack Query, Important Defaults: https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults
- TanStack Query, Advanced Server Rendering: https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr
- TanStack Query, Network Mode: https://tanstack.com/query/latest/docs/framework/react/guides/network-mode
- Next.js, TanStack Query guide: https://nextjs.org/docs/app/guides/client-side-data-fetching/tanstack-query
- nuqs, Options: https://nuqs.dev/docs/options
- React, Choosing the State Structure: https://react.dev/learn/choosing-the-state-structure
- Next.js, Forms: https://nextjs.org/docs/app/guides/forms
- Zod, JSON Schema: https://zod.dev/json-schema
- Zod, Formatting errors: https://zod.dev/error-formatting
- React Hook Form, useForm: https://react-hook-form.com/docs/useform
- Hey API, Zod plugin: https://heyapi.dev/openapi-ts/plugins/zod
- WCAG 2.2 Understanding 3.3.1 Error Identification: https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
- WCAG 2.2 Understanding 3.3.8 Accessible Authentication (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html
