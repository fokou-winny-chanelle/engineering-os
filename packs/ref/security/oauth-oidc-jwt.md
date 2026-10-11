---
id: security/oauth-oidc-jwt
title: OAuth 2.0, OpenID Connect and JWT pitfalls
area: security
read_when: adding "log in with…", an API that accepts bearer tokens, SPA/mobile token handling, service-to-service tokens, or any JWT parsing
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.rfc-editor.org/rfc/rfc9700", "https://datatracker.ietf.org/doc/rfc10017/", "https://www.rfc-editor.org/rfc/rfc8725", "https://www.rfc-editor.org/rfc/rfc9449", "https://www.rfc-editor.org/rfc/rfc9068", "https://openid.net/specs/openid-connect-core-1_0.html", "https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html"]
---
# OAuth 2.0, OpenID Connect and JWT pitfalls

OAuth 2.0 is for **delegated access** (an app acting on a user's behalf at an API). OpenID Connect (OIDC) adds **login** (an ID token saying who the user is). JWT is just a token format. Most bugs come from using the wrong one, using old grant types, or validating tokens by hand. Current rules: RFC 9700 (OAuth 2.0 Security BCP, 2025), RFC 10017 (OAuth 2.0 for Browser-Based Applications, BCP, August 2026), RFC 8725 (JWT BCP).

## Decision guide

**Do you need OAuth at all?** RFC 10017 §7.1: a single-domain web app talking to its own backend should usually use a **server-side session cookie**, not access tokens. Use OIDC only to outsource login, then create your own session.

**Pick the architecture (RFC 10017 §6):**

| Client | Pattern | Tokens live in | Notes |
|---|---|---|---|
| Server-rendered web app | confidential client, code flow + PKCE | server | simplest and strongest |
| SPA with a backend you control | **Backend for Frontend (BFF)** §6.1 | BFF only; browser holds an `HttpOnly` session cookie | stolen-token attacks from XSS are mitigated; XSS can still act through the session ("client hijacking"), so CSP still matters |
| SPA, token-mediating backend §6.2 | backend gets tokens, hands access token to JS | access token in JS memory | refresh token stays server-side |
| Pure browser client §6.3 | public client, code + PKCE | JS memory | short-lived, narrowly scoped tokens; refresh rotation; consider DPoP |
| Native/mobile app | public client, code + PKCE via system browser | Keychain / Keystore | claimed HTTPS redirect (universal/app links) preferred |
| Service to service | client credentials, or workload identity (cloud IAM, GitHub OIDC) | secret manager | no user context; scope per service |

**RFC 9700 MUSTs to enforce:**
- Authorization code grant with **PKCE** (S256). Public clients MUST use PKCE; confidential clients should too.
- **Exact string matching** of registered redirect URIs (only the port of localhost may vary for native apps). No wildcards, no open redirectors.
- **No implicit grant** (`response_type=token`) and **no resource-owner password grant** (MUST NOT).
- Refresh tokens for public clients MUST be **sender-constrained or rotated** (rotation: each use issues a new one, reuse of an old one revokes the family).
- Defend against mix-up when talking to several authorization servers (issuer identification, RFC 9207 `iss` parameter, or distinct redirect URIs).
- Access tokens should be **audience-restricted** to one resource server and narrowly scoped; prefer sender-constrained tokens (mTLS RFC 8705 or DPoP RFC 9449) for high-value APIs.
- Use `state` (or PKCE) against CSRF on the redirect; use `nonce` with OIDC.

**Validating tokens at an API (RFC 8725, RFC 9068, OIDC Core §3.1.3.7):**
1. Use a maintained library with an **explicit algorithm allow-list** (e.g. `["RS256"]` or `["EdDSA"]`); never accept `alg: none`, never let the token header pick the algorithm or key type (RS/HS confusion).
2. Fetch keys from the issuer's JWKS over HTTPS, cache with rotation, match `kid`; never load a key from a token header URL (`jku`, `x5u`) you did not configure.
3. Check `iss` (exact), `aud` (contains your API), `exp`/`nbf` with small clock skew, and for access tokens the explicit type (`typ: at+jwt`, RFC 9068) so ID tokens cannot be replayed as access tokens (RFC 8725 §3.11–3.12).
4. Authorize from `scope`/claims **and** your own database (roles change; tokens are stale snapshots).
5. ID tokens are for the client that requested them; never send them to APIs as bearer credentials.

**JWT vs opaque tokens:** JWTs cannot be revoked before expiry without a lookup. Keep access-token lifetimes short (minutes) and revocation via refresh-token revocation; use opaque tokens plus introspection when instant revocation matters (admin, money).

## Anti-patterns
- `jwt.decode(token, verify=False)` / `options={"verify_signature": False}` / `algorithms` taken from the header.
- Long-lived JWTs (days) as browser sessions stored in `localStorage`.
- Wildcard or prefix redirect URI matching; reflecting `redirect_uri` from the query string.
- Using the access token's presence as "logged in" without checking `aud`; accepting tokens issued for another API.
- Implementing OAuth/OIDC protocol code by hand instead of a certified library.
- Embedded WebView login in mobile apps (the app can read the password; no shared SSO; phishing-prone).

## Checks
- [ ] Semgrep rule `eos-jwt-verify-disabled` passes (no signature verification disabled, no `none` algorithm) — `eos scaffold security`.
- [ ] Tests: token with wrong `aud`, wrong `iss`, expired, `alg: none`, HS256-signed with the public key, and an ID token used as access token are each rejected (401).
- [ ] Redirect URIs registered exactly; a test or config assertion checks no wildcard.
- [ ] PKCE enforced at the authorization server for all clients; implicit and password grants disabled.
- [ ] Refresh tokens rotate (reuse detection test) or are sender-constrained; access-token lifetime is short and written down in the design.
- [ ] SPA design names the RFC 10017 pattern used and why.

## Sources
- https://www.rfc-editor.org/rfc/rfc9700 (OAuth 2.0 Security BCP)
- https://datatracker.ietf.org/doc/rfc10017/ (browser-based apps: BFF, token-mediating backend, browser client; §7.1 sessions instead of OAuth)
- https://www.rfc-editor.org/rfc/rfc8725 (JWT BCP: algorithm verification, audience, explicit typing)
- https://www.rfc-editor.org/rfc/rfc9449 (DPoP)
- https://www.rfc-editor.org/rfc/rfc9068 (JWT access token profile, `at+jwt`)
- https://openid.net/specs/openid-connect-core-1_0.html (ID token validation)
- https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html
