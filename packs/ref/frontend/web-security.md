---
id: frontend/web-security
title: Frontend security in React/Next.js (XSS escape hatches, URL validation, Content Security Policy with nonces vs static vs SRI, Trusted Types, token storage, server-only code and env leaks, third-party scripts)
area: frontend
read_when: rendering user or CMS HTML, using dangerouslySetInnerHTML or href from data, adding or changing a Content-Security-Policy, storing tokens or session data in the browser, adding a third-party script, reviewing a Client Component that touches secrets
verified: 2026-10-10
revisit_days: 120
sources: ["https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html", "https://nextjs.org/docs/app/guides/content-security-policy", "https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config/instant", "https://nextjs.org/docs/app/guides/data-security", "https://react.dev/reference/react-dom/components/common", "https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API", "https://nextjs.org/docs/app/api-reference/config/next-config-js/taint"]
---
# Frontend security (React / Next.js)

React escapes text by default, so most XSS in React apps comes through escape hatches, URLs and third-party code. Server-side rules (authz, CSRF, headers, sessions) are in the security refs: `security/input-injection`, `security/web-api-hardening`, `security/authentication`, `security/oauth-oidc-jwt`, `security/secrets-keys`.

## Decision guide

**1. XSS escape hatches.** OWASP lists React's `dangerouslySetInnerHTML` without sanitising and unvalidated URL values as framework pitfalls.
- Avoid raw HTML. Render Markdown to React elements on the server; if you must inject HTML (CMS rich text), sanitise with DOMPurify (on the server with a DOM shim or in the browser) using an allowlist, and keep the sanitiser updated.
- React 19 blocks `javascript:` URLs in `src`/`href`, but OWASP notes that does not replace URL validation: parse with `new URL()`, allow only `https:` (and `mailto:`/`tel:` where intended) and known hosts for redirects (`?next=` open-redirects).
- Never build HTML strings, `eval`, `new Function`, `setTimeout(string)`, or inject into `<script>` with data. JSON-LD: serialise with escaping of `<` (`JSON.stringify(x).replace(/</g, '\\u003c')`).
- Server Components do not remove XSS: data they render is escaped the same way, and the hatches above still apply.

**2. Content Security Policy.** Choose per app:
| Option | Protection | Cost |
|---|---|---|
| Nonce-based strict CSP in `proxy.ts` (Next docs example: `script-src 'self' 'nonce-…' 'strict-dynamic'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`) | strongest; inline scripts need the per-request nonce, which Next applies to its own scripts automatically | every page must render dynamically: no static/CDN caching of HTML, slower first byte, higher hosting cost (Next docs) |
| Static CSP in `next.config` `headers()` | blocks third-party origins, framing, plugins | needs `'unsafe-inline'` for scripts, so it does little against injected inline script |
| Experimental hash-based SRI (App Router) | strict CSP while keeping static output | experimental; check the version you pin |
With Cache Components (on in `create-next-app` 16.4) a prerendered page or shell carries no nonce, so the browser blocks Next's own scripts: routes under a nonce CSP must render per request (`export const instant = false`; checked on a 16.4 app, where the header test caught it). `next/image` writes `style="color:transparent"`, which a style nonce does not cover: the scaffold allows exactly that hash with `'unsafe-hashes'`. Start in `Content-Security-Policy-Report-Only` with a reporting endpoint, fix violations, then enforce. `'unsafe-eval'` only in development (React needs it for dev error stacks). Every third-party script, font, image or API origin is a policy entry and a supply-chain trust decision (`security/supply-chain`). `eos scaffold web-security` provides `lib/csp.ts`, a nonce `proxy.ts` with the other security headers, and a Playwright test that asserts them and fails on any CSP violation in the console.

**3. Trusted Types.** `require-trusted-types-for 'script'` makes string assignments to DOM sinks (`innerHTML`) throw. MDN marks it Baseline 2026 (newly available since February 2026), so older browsers on low-end phones ignore it: use it as defence in depth after CSP, in report-only first, and expect third-party scripts to break.

**4. Tokens and browser storage.**
- Session or refresh tokens never go in `localStorage`/`sessionStorage`/IndexedDB: any XSS can read them (OWASP HTML5 sheet). Use an `HttpOnly; Secure; SameSite` cookie set by the server (a backend-for-frontend for third-party OAuth; `security/oauth-oidc-jwt`).
- Don't put personal or financial data in web storage or in URLs (logged by proxies and analytics).
- Treat data read from storage, `postMessage` (check `event.origin`) and URL params as untrusted input.

**5. Keeping server things on the server.**
- `import "server-only"` in modules that touch secrets, the DB or internal APIs; a client import then fails the build.
- Only `NEXT_PUBLIC_*` variables reach the browser, inlined at build; never name a secret that way (`frontend/nextjs-actions-routes`).
- Pass DTOs, not ORM rows, to Client Components (the Data Security guide's Data Access Layer); React taint APIs (`experimental.taint`) are experimental and not recommended for production yet.
- Browser source maps are off in production builds unless `productionBrowserSourceMaps: true`; if you need them for error tracking, upload them to the tracker rather than serving them publicly.

## Examples
```ts
// lib/safe-url.ts — validate user/CMS-provided links before rendering
const ALLOWED = new Set(["https:", "mailto:", "tel:"]);
export function safeHref(raw: string): string | undefined {
  try { const u = new URL(raw, "https://example.invalid"); return ALLOWED.has(u.protocol) ? u.href : undefined; }
  catch { return undefined; }
}
// redirect target after login: same-origin paths only
export const safeNext = (p: string | null) => (p && p.startsWith("/") && !p.startsWith("//") ? p : "/");
```

## Anti-patterns
- `dangerouslySetInnerHTML={{ __html: comment.body }}`; regex-based "sanitisers".
- `<a href={user.website}>` without protocol checks; `router.push(searchParams.get('next'))`.
- Access or refresh tokens in `localStorage` "because cookies are hard with our API".
- A CSP containing `'unsafe-inline' 'unsafe-eval' *` (no protection) or copied without testing, then disabled when it breaks.
- `NEXT_PUBLIC_STRIPE_SECRET`, `process.env.DATABASE_URL` read in a `"use client"` file.

## Checks
- semgrep: `eos-react-dangerously-set-inner-html` (security scaffold) and `.semgrep/eos-frontend.yml` (`eos scaffold web-security`): tokens written to web storage, non-public `process.env` in Client Components, `eval`-like sinks.
- `e2e/security-headers.spec.ts`: CSP has a nonce and `'strict-dynamic'` (or your chosen policy), `frame-ancestors`, `nosniff`, `Referrer-Policy`; no `X-Powered-By` (Next adds it unless `poweredByHeader: false`).
- ZAP baseline in CI for public apps (`security/security-testing`).
- Human review for any CSP change, sanitiser configuration and auth-cookie handling.

## Sources
- OWASP, Cross Site Scripting Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- OWASP, HTML5 Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- OWASP, Content Security Policy Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html
- Next.js, Content Security Policy: https://nextjs.org/docs/app/guides/content-security-policy
- Next.js, `instant` route segment config: https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config/instant
- Next.js, Data Security: https://nextjs.org/docs/app/guides/data-security
- React, Common components (dangerouslySetInnerHTML): https://react.dev/reference/react-dom/components/common
- MDN, Trusted Types API: https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API
- Next.js, taint: https://nextjs.org/docs/app/api-reference/config/next-config-js/taint
