---
id: frontend/errors-observability
title: Frontend error handling, observability and testing map for Next.js (expected vs unexpected errors, error.tsx retry/reset, global-error, catchError, not-found, client instrumentation, web vitals and error reporting, which tests cover what)
area: frontend
read_when: adding error, loading or not-found UI, an action fails and the user loses input, setting up client error tracking or RUM, users report blank pages, deciding how to test a component, Server Component or flow
verified: 2026-10-10
revisit_days: 120
sources: ["https://nextjs.org/docs/app/getting-started/error-handling", "https://nextjs.org/docs/app/api-reference/file-conventions/error", "https://nextjs.org/docs/app/api-reference/functions/catchError", "https://nextjs.org/docs/app/api-reference/file-conventions/instrumentation-client", "https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals", "https://nextjs.org/docs/app/guides/testing", "https://nextjs.org/docs/app/guides/testing/vitest"]
---
# Frontend errors, observability and tests

A user on a slow connection who hits an error should keep their input, see what to do next in their language, and give support an ID that leads to the server log. Server-side telemetry, SLOs and runbooks are in `ops/opentelemetry`, `ops/slo-error-budgets`, `ops/dashboards-alerting` and `ops/incident-runbooks`.

## Decision guide

**1. Expected vs unexpected errors (Next.js model).**
| Kind | Example | Handle with |
|---|---|---|
| expected | validation, "insufficient balance", not authorised for this object, upstream timeout you anticipate | return a value from the Server Action (`useActionState`), render a message from the Server Component; never throw |
| missing resource | unknown slug or id | `notFound()` → `not-found.tsx` (call before streaming starts for a real 404; `frontend/nextjs-rendering-data`) |
| unexpected | bugs, unhandled exceptions | throw; caught by the nearest `error.tsx` |

**2. Error boundaries.**
- `error.tsx` must be a Client Component. It wraps the segment's `page` and nested layouts, not the `layout.tsx` of the same segment; root-layout failures need `app/global-error.tsx`, which renders its own `<html>` and `<body>` and does not get your global styles or fonts (keep it simple and inline the essentials, localised).
- `retry()` re-fetches and re-renders the boundary's children (prefer it); `reset()` only clears the error state and re-renders without re-fetching.
- In production, errors from Server Components reach the client as a generic message plus `error.digest`; show the digest (or your trace ID, `ops/opentelemetry`) as a reference code users can quote, and log the full error server-side.
- `catchError` from `next/error` builds a component-level boundary (e.g. around one widget) that cooperates with `redirect()`/`notFound()` and clears on navigation, so one failing card doesn't blank the page.
- Put boundaries around independent widgets and next to `<Suspense>` boundaries; a failure in a recommendation rail should not take down checkout.

**3. Copy and recovery.** Say what happened and what to do ("Connexion perdue. Vos données sont conservées. Réessayer"), offer retry, keep form input (don't throw from actions), and for payments link to the transaction history rather than inviting a second attempt (`frontend/state-forms`). Distinguish offline from server errors (`frontend/low-bandwidth`).

**4. Client observability.**
- `instrumentation-client.ts` (root or `src/`) runs before the app becomes interactive: initialise error tracking and RUM there; export `onRouterTransitionStart` to time navigations.
- Report Core Web Vitals with `useReportWebVitals` (`frontend/web-vitals-budgets`) and unhandled errors/rejections, tagged with route, release (commit SHA), locale, connection type where available, and the trace ID from the server response when you have one.
- Send with `navigator.sendBeacon` or a batched `fetch(..., { keepalive: true })`; sample on high-traffic pages; keep the SDK small (it counts against the JS budget).
- Scrub personal data before it leaves the browser (`security/privacy`); never log tokens, form values of payment fields or full URLs with secrets.
- Upload source maps to the tracker at build time; don't serve them publicly (`frontend/web-security`).

**5. Which test covers what** (details in the testing refs).
| Layer | Tool | Notes |
|---|---|---|
| pure functions, formatters, schemas, hooks | Vitest/Jest unit tests (`testing/unit-design`) | include `lib/format.ts` XAF/date tests (`frontend/i18n-l10n`) |
| synchronous Client/Server Components | Vitest + Testing Library, query by role/label | Next docs: Vitest does not support async Server Components yet |
| async Server Components, actions, routing, caching | Playwright e2e against `next build && next start` (`testing/e2e-playwright`) | dev mode behaves differently |
| accessibility | axe in e2e + manual (`frontend/accessibility`) | |
| performance | Lighthouse CI budgets (`eos scaffold lighthouse`) | |
| flaky tests | quarantine with owner and expiry (`testing/flaky-speed`) | |
| React Native | `testing/mobile-qa` | |

## Examples
```tsx
// app/[locale]/orders/error.tsx
"use client";
import { useTranslations } from "next-intl";
export default function OrdersError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const t = useTranslations("errors");
  return (
    <div role="alert">
      <h2>{t("ordersTitle")}</h2>
      <p>{t("tryAgainHint")}</p>
      <button onClick={() => retry()}>{t("retry")}</button>
      {error.digest && <p>{t("reference", { code: error.digest })}</p>}
    </div>
  );
}
```

## Anti-patterns
- Throwing for validation errors, which wipes the form and shows a generic error page.
- One root `error.tsx` only; no `global-error.tsx`; English-only error pages.
- Showing `error.message` from the server or stack traces to users; logging nothing client-side.
- Ten analytics and replay SDKs in the root layout; session replay recording payment fields.
- Unit-testing async Server Components with mocks of Next internals instead of an e2e test.

## Checks
- Review: each route group has `error.tsx` and `not-found.tsx`; `global-error.tsx` exists; actions return expected errors.
- e2e: force an action error and a server error; assert input is kept and a reference code is shown.
- Client error rate and vitals per release on a dashboard with an alert (`ops/dashboards-alerting`).

## Sources
- Next.js, Error Handling: https://nextjs.org/docs/app/getting-started/error-handling
- Next.js, error.js: https://nextjs.org/docs/app/api-reference/file-conventions/error
- Next.js, catchError: https://nextjs.org/docs/app/api-reference/functions/catchError
- Next.js, instrumentation-client.js: https://nextjs.org/docs/app/api-reference/file-conventions/instrumentation-client
- Next.js, useReportWebVitals: https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals
- Next.js, Testing: https://nextjs.org/docs/app/guides/testing
- Next.js, Testing with Vitest: https://nextjs.org/docs/app/guides/testing/vitest
