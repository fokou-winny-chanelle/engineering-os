---
id: api/rate-limits-auth
title: Rate limits, quotas and authentication/authorisation at the API layer (RateLimit headers draft, API keys, OAuth scopes, gateways)
area: api
read_when: adding rate limits or usage quotas, choosing API keys vs OAuth tokens, designing scopes and per-endpoint permissions, putting an API gateway in front, exposing a partner or public API
verified: 2026-10-10
revisit_days: 180
sources: ["https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/", "https://www.rfc-editor.org/rfc/rfc6585", "https://www.rfc-editor.org/rfc/rfc9110", "https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api", "https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern", "https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling", "https://opensource.zalando.com/restful-api-guidelines/", "https://spec.openapis.org/oas/v3.1.2.html"]
adapted_from: ["https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern", "https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling", "https://opensource.zalando.com/restful-api-guidelines/"]
---
# Rate limits, quotas and auth at the API layer

Rate limits keep one client from hurting the others and cap abuse; quotas turn usage into a product (plans, billing). Authentication says who is calling; authorisation decides what they may touch, **per object**, inside the service. The security details live in the stage-2 refs; this page is the API contract side.

## Decision guide

**1. What to limit, keyed on what.**
| Limit | Key | Example |
|---|---|---|
| Request rate | credential (API key, OAuth client, user) first; IP only for unauthenticated routes | 100 req / 10 s burst, 5,000 / hour |
| Concurrency | credential | GitHub's secondary limits include max concurrent requests |
| Expensive operations | credential + operation | search, export, report generation, LLM calls: lower limits or cost units |
| Abuse-sensitive flows | account + device + IP | login, OTP/SMS send, password reset, payment initiation (`security/web-api-hardening`, `security/authentication`) |
| Quota (plan) | tenant / billing account | 1M calls / month; enforced softly with notices, then hard |
Numbers above are illustrations; set yours from load tests and plan design. Keying only by IP fails behind carrier NAT and against rotating IPs.

**2. Algorithm and placement.** Token bucket (allows bursts) or sliding window counter; fixed windows let clients double up at the boundary. Enforce at the edge or gateway for coarse per-key limits and in the service for per-operation and per-tenant business limits, backed by a shared store (Redis with atomic Lua/`INCR` + expiry; `data/search-redis`). Azure's throttling pattern also lists degrading non-critical features and prioritising important clients when overloaded.

**3. Telling clients (the headers).**
- Over the limit: **429 Too Many Requests** (RFC 6585) + `Retry-After` (seconds) + a problem body with `code: RATE_LIMITED`. Overload not caused by the client: 503 + `Retry-After`. Zalando: MUST use 429 with headers.
- Remaining quota on normal responses: the IETF **RateLimit header fields draft** (draft-ietf-httpapi-ratelimit-headers-11, May 2026) is an *active Internet-Draft, not yet an RFC*, so field syntax may still change:
  ```
  RateLimit-Policy: "burst";q=100;w=60,"daily";q=1000;w=86400
  RateLimit: "burst";r=42;t=17
  ```
  (`q` quota, `w` window seconds, `r` remaining, `t` seconds until reset.) If both are sent, `Retry-After` should not point earlier than the end of the window. Many APIs still send the legacy, non-standard `X-RateLimit-Limit` / `-Remaining` / `-Reset` (GitHub does). eos default: send `Retry-After` on 429 always; add either the draft fields or the legacy trio, document which, and do not promise exact semantics until the RFC is published.
- Document limits per plan and per endpoint, and how to request more.

**4. Client behaviour (put it in docs and SDKs).** Honour `Retry-After`; otherwise exponential backoff with jitter; spread batch jobs; cache; use webhooks instead of polling (`api/webhooks`); fewer, bigger requests where a batch endpoint exists (`api/reliability`).

**5. Authentication options at the API.**
| Caller | Mechanism | Notes |
|---|---|---|
| Your own web app (same site) | session cookie (`HttpOnly`, `Secure`, `SameSite`) + CSRF protection | simplest for Next.js and server-rendered apps |
| Your mobile app / SPA | OAuth 2 / OIDC authorization code + PKCE, short-lived access tokens, refresh token rotation | `security/oauth-oidc-jwt` |
| Third-party apps acting for users | OAuth 2 with scopes and consent | |
| Server-to-server, partners | API keys (prefixed, hashed at rest, scoped, rotatable, per environment) or OAuth client credentials; mTLS for high assurance | keys identify a client, not a user |
| Internal services | workload identity / mTLS via mesh, or signed service tokens with audience | not "trusted because inside the network" |
- Declare it in the spec: `components.securitySchemes` (`http` bearer, `apiKey`, `oauth2` with scopes, `openIdConnect`, `mutualTLS`) and `security` on every operation; Spectral `eos-security-declared` fails if an operation has none and there is no global one. Use `security: []` to mark intentionally public endpoints so reviews see it.
- 401 with `WWW-Authenticate` when credentials are missing or invalid (RFC 9110); 403 when authenticated but not allowed; 404 to hide objects the caller must not know exist.

**6. Authorisation at the API layer.**
- **Scopes are coarse** (what kind of action a token may do: `orders:read`). They never replace **object-level checks** (is this order in the caller's tenant?). OWASP API1 (BOLA) and API5 (function-level) are the most common API breaches: `security/authorization`.
- Enforce in one place per request (middleware/policy layer plus a query scope by tenant), deny by default, and test with two tenants.
- Never trust ids in the body for ownership (`tenant_id`, `user_id`): derive from the token.
- Response filtering: serialise with explicit allow-listed fields per role (mass assignment and excessive data exposure, OWASP API3).
- Gateways help (auth offload, limits, logging) but the service still authorises each object.

**7. Cross-links (stage 2 security refs).** `security/web-api-hardening` (OWASP API Top 10, CORS, headers, inventory) · `security/authorization` (BOLA, tenancy, policies) · `security/oauth-oidc-jwt` (token validation, PKCE, scopes) · `security/authentication` (passwords, MFA, sessions) · `security/secrets-keys` (API key storage, rotation) · `security/input-injection` (SSRF, injection) · `security/security-testing` (ZAP, authz tests).

## Anti-patterns
- No limits on login, OTP or export endpoints.
- 429 without `Retry-After`, or 500/503 for client over-use.
- Treating the RateLimit draft as a finished standard, or inventing a third header style.
- Long-lived bearer tokens in mobile apps; API keys in frontend bundles or URLs (they land in logs).
- Scope checks without object checks; tenant id taken from the request body.
- Operations missing from the spec's security model ("internal" endpoints on public hosts).

## Checks
- `.spectral.yaml`: `eos-security-declared`.
- Schemathesis `ignored_auth` check: calls declared-secured operations without credentials and fails if they succeed (`api/testing`).
- Tests: a burst above the limit gets 429 with `Retry-After`; cross-tenant access returns 404.
- Semgrep and authz tests from `eos scaffold security-tests` (`security/security-testing`).

## Sources
- RateLimit header fields for HTTP (draft-ietf-httpapi-ratelimit-headers, active Internet-Draft): https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/
- RFC 6585 (429): https://www.rfc-editor.org/rfc/rfc6585 · RFC 9110 (401, WWW-Authenticate, Retry-After): https://www.rfc-editor.org/rfc/rfc9110
- GitHub REST API rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Azure Architecture Center, Rate Limiting pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern · Throttling pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling
- Zalando RESTful API Guidelines (429 with headers): https://opensource.zalando.com/restful-api-guidelines/
- OpenAPI 3.1.2 security schemes: https://spec.openapis.org/oas/v3.1.2.html

## Attribution
Adapted from "Rate Limiting pattern" and "Throttling pattern" by Microsoft, Azure Architecture Center (https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern, https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling) and "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined with IETF and vendor documentation, and eos defaults added. Not endorsed by the original authors.
