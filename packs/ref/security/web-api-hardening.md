---
id: security/web-api-hardening
title: Web, API and mobile-backend hardening (headers, CORS, CSRF, rate limits)
area: security
read_when: exposing a web app or public/partner/mobile API, setting headers/CORS/cookies, adding rate limits, or reviewing an API against the OWASP API Top 10
verified: 2026-10-10
revisit_days: 365
sources: ["https://api-security.owasp.org/editions/2023/en/0x11-t10/", "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS", "https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html", "https://owasp.org/projects/automated-threats-to-web-applications", "https://mas.owasp.org/MASVS/", "https://developer.android.com/google/play/integrity", "https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity", "https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html"]
---
# Web, API and mobile-backend hardening

These are the configuration-level defences every exposed service needs. They do not replace authorization and injection defences (`security/authorization`, `security/input-injection`) but they remove whole classes of bugs cheaply. Treat the client (browser, mobile app, partner SDK) as fully attacker-controlled.

## Decision guide

**OWASP API Security Top 10 2023 as a review list:** API1 BOLA · API2 Broken Authentication · API3 BOPLA · API4 Unrestricted Resource Consumption · API5 BFLA · API6 Unrestricted Access to Sensitive Business Flows · API7 SSRF · API8 Security Misconfiguration · API9 Improper Inventory Management · API10 Unsafe Consumption of APIs.

**Response headers (OWASP HTTP Headers cheat sheet):**

| Header | Value | Notes |
|---|---|---|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | read the sheet's warning first: a broken cert + long HSTS locks users out; check hstspreload.org requirements before `preload` |
| `Content-Security-Policy` | strict nonce-based policy (`security/input-injection`) + `frame-ancestors 'none'` (or allowed parents) | `frame-ancestors` supersedes `X-Frame-Options: DENY` |
| `X-Content-Type-Options` | `nosniff` | plus correct `Content-Type` everywhere |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | set explicitly |
| `Cache-Control` | `no-store` on authenticated/PII responses | prevents shared-cache leaks |
| `X-XSS-Protection` | do not set (or `0`) | obsolete |
| `Server`, `X-Powered-By` | remove | less fingerprinting |
| COOP / CORP / `Permissions-Policy` | per the sheet | isolation; disable unused features (camera, geolocation) |

**CORS:** CORS relaxes the same-origin policy; it is not an access control for your API. Use an explicit allow-list of origins; **never reflect the request `Origin` back** with `Access-Control-Allow-Credentials: true`; `*` is acceptable only for truly public, credential-less APIs (browsers refuse `*` with credentials). Treat `null` origin as untrusted.

**CSRF (cookie-authenticated endpoints only):** use the framework's built-in protection first (OWASP CSRF sheet). Layers: `SameSite=Lax` or `Strict` cookies; synchronizer token or signed double-submit cookie; check `Sec-Fetch-Site` (Fetch Metadata) with an Origin/Referer fallback (the sheet says the fallback is mandatory); state changes never on GET. Bearer-token APIs that never read cookies are not CSRF-prone.

**Resource consumption and abuse (API4, API6):**
- Rate limits per credential, per IP/device and per expensive operation (login, OTP send, search, export, payment initiation); return 429 with `Retry-After`.
- Limits on page size, request body size, upload size, GraphQL depth/complexity, batch size, regex inputs and execution time.
- Business-flow abuse (OWASP Automated Threats: card cracking, credential stuffing, scalping, account creation; plus SMS pumping on OTP endpoints) needs flow-specific controls: velocity rules, device signals, CAPTCHA/step-up on risk, not just IP limits.

**Inventory (API9):** one OpenAPI spec per deployed API version, generated from code or tested against it; old versions and debug/admin endpoints are listed with an owner and a removal date; no undocumented "internal" endpoints on public hosts.

**Third-party APIs (API10):** validate and size-limit their responses like user input; TLS verification on; timeouts; do not follow redirects blindly; treat webhooks as untrusted until signature-verified (`security/payments`).

**Mobile backends (MASVS):**
- Everything the app enforces must also be enforced on the server: prices, limits, feature flags, KYC state.
- App/device attestation (Google Play Integrity API, Apple App Attest) raises the cost of scripted abuse and fake clients; use it as a risk signal on sensitive calls, not as authentication.
- Certificate pinning: the OWASP Pinning cheat sheet says there is "almost no situation" where you should pin because outage risk usually outweighs the benefit; if you must, pin with backup pins and a remote kill-switch plan.
- No secrets in the app binary (they can be extracted); per-user tokens only.

## Anti-patterns
- `Access-Control-Allow-Origin: <reflected origin>` with credentials; regex origin checks like `endsWith("example.com")` (matches `evilexample.com`).
- Disabling CSRF protection globally because "it's an API" while authenticating with cookies.
- Rate limiting only by IP (mobile carriers and CGNAT share IPs; attackers rotate them).
- Debug endpoints, Swagger UI with try-it-out, or GraphQL introspection exposed on production without auth.
- Relying on the mobile app to hide features or validate amounts.
- TLS verification disabled in HTTP clients (`verify=False`, `rejectUnauthorized: false`).

## Checks
- [ ] Header test (integration or ZAP baseline) asserts HSTS, CSP, `nosniff`, `Referrer-Policy`, `frame-ancestors`, and no `X-Powered-By`.
- [ ] semgrep `eos-cors-wildcard-credentials` and `eos-tls-verify-disabled` pass; ruff `S501` (requests `verify=False`) passes.
- [ ] Test: cross-site POST with a valid session cookie but no CSRF token is rejected.
- [ ] Rate-limit tests on login, OTP send/verify and payment initiation (expect 429).
- [ ] OpenAPI spec matches deployed routes (contract test or Schemathesis run, `security/security-testing`).
- [ ] Sensitive mobile calls check attestation verdicts server-side and log them as risk signals.

## Sources
- https://api-security.owasp.org/editions/2023/en/0x11-t10/
- https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html (Fetch Metadata, fallback mandatory)
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS
- https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- https://owasp.org/projects/automated-threats-to-web-applications
- https://mas.owasp.org/MASVS/
- https://developer.android.com/google/play/integrity
- https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity
- https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html
