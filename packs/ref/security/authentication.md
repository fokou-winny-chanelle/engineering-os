---
id: security/authentication
title: Authentication (passwords, sessions, MFA, passkeys)
area: security
read_when: building or changing login, signup, password reset, sessions/cookies, MFA, passkeys/WebAuthn or account recovery
verified: 2026-10-10
revisit_days: 365
sources: ["https://pages.nist.gov/800-63-4/sp800-63b.html", "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html", "https://www.w3.org/TR/webauthn-3/", "https://passkeys.dev/"]
---
# Authentication (passwords, sessions, MFA, passkeys)

Prefer not to build authentication at all: use your framework's auth module or a maintained identity provider, and spend the effort on the parts that stay yours (authorization, recovery, session handling). Whatever you use, the rules below are what reviewers check. Numbers are from NIST SP 800-63B-4 and the OWASP cheat sheets as of 2026-10-10.

## Decision guide

**Factor choice (strongest first):**

| Option | Phishing-resistant | Use for | Notes |
|---|---|---|---|
| Passkeys / WebAuthn (platform or security key) | yes (origin-bound) | default for new products; required for admins and money movers | synced passkeys (cloud keychain) vs device-bound (security key); NIST AAL3 needs a non-exportable key |
| TOTP app | no | second factor where passkeys are not available | store seeds encrypted; allow 2+ authenticators |
| Push approval | no (fatigue attacks) | consumer second factor | require number matching; rate-limit prompts |
| SMS / voice OTP | no | last resort only (common in mobile-money markets) | NIST 800-63B-4 marks PSTN OTP as **restricted**; OWASP: not for apps with PII or financial risk; SIM-swap risk; rate-limit sends (SMS pumping costs money) |
| Email link/OTP | no | sign-up verification, low-risk login | NIST: email SHALL NOT be used for out-of-band authentication |

**Passwords (NIST SP 800-63B-4):** minimum 15 characters when the password is the only factor, minimum 8 when it is used only as part of MFA; allow at least 64 characters, spaces and all Unicode; **no composition rules** ("one symbol…"), **no periodic forced changes** (force a change only on evidence of compromise); check new passwords against a blocklist of common and breached passwords; no hints or knowledge questions; allow paste and password managers. Limit consecutive failed attempts per account to at most 100 (NIST upper bound), and add throttling and bot defences well below that.

**Password storage (OWASP Password Storage cheat sheet), pick one:**
- Argon2id: minimum 19 MiB memory, 2 iterations, parallelism 1 (or the other equal-strength settings the sheet lists).
- scrypt: N=2^17, r=8, p=1.
- bcrypt (legacy): work factor 10 or more; inputs over 72 bytes are truncated, so do not pre-concatenate secrets.
- PBKDF2-HMAC-SHA-256 with 600,000+ iterations only where FIPS-140 is required.
Use your library's `needs_rehash()` to upgrade hashes on login. Never encrypt passwords, never use fast hashes (MD5/SHA-*), never log them.

**Sessions (OWASP Session Management):**
- Session IDs from a CSPRNG with at least 64 bits of entropy; opaque, server-side state for web apps.
- Cookie: `Set-Cookie: __Host-session=…; Secure; HttpOnly; SameSite=Lax|Strict; Path=/` (the `__Host-` prefix forbids `Domain` and requires `Secure` and `Path=/`).
- **Regenerate the session ID on login and on every privilege change** (password change, role switch, MFA step-up); destroy it server-side on logout.
- Timeouts: NIST AAL2 says reauthenticate at most every 24 hours overall and after at most 1 hour of inactivity (SHOULD); AAL3 is 12 hours overall (SHALL) and 15 minutes inactivity (SHOULD). Pick per risk and write it down.
- Step-up: require fresh authentication (passkey or second factor) for changing email/phone/password/MFA, adding payees, large transfers and exporting data.

**Account enumeration and recovery:**
- Login, sign-up and reset respond with the same message and similar timing whether or not the account exists (OWASP Authentication and Forgot Password sheets).
- Reset tokens: random, stored hashed, single use, expire after a short period, and invalidated when used or when the password changes. Revoke all sessions after a reset.
- Recovery is the real attack surface (SIM swap, support desk social engineering). Offer single-use recovery codes and multiple authenticators; make support-desk resets require stronger proof and leave an audit trail.

**Mobile apps and APIs:** use the system browser (ASWebAuthenticationSession / Custom Tabs) with OAuth + PKCE, never an embedded WebView login; store tokens in Keychain/Keystore. See `security/oauth-oidc-jwt`.

## Anti-patterns
- Rolling your own password hashing, session IDs or "remember me" tokens.
- Password rules that force symbols and 90-day rotation (both reduce security per NIST).
- Session ID in URLs or `localStorage`; long-lived JWTs used as sessions with no revocation.
- Not rotating the session ID at login (session fixation) or leaving old sessions alive after password reset.
- MFA that can be skipped by calling the API directly, or a recovery flow that bypasses MFA entirely.
- Different error messages or response times for "no such user" vs "wrong password".
- SMS OTP as the only factor for moving money, with no SIM-swap or velocity signals.

## Checks
- [ ] Hash algorithm and parameters match the list above; tests assert hashes are never logged or returned.
- [ ] Tests: session ID changes after login and after privilege change; logout invalidates server-side; cookie has `Secure`, `HttpOnly`, `SameSite` (and `__Host-` where possible).
- [ ] Tests: identical response for existing vs unknown account on login/reset/sign-up.
- [ ] Rate limit and lockout policy on login, OTP verification and OTP sending (per account and per IP/device).
- [ ] Step-up authentication is enforced server-side for sensitive actions (test calls the API without it and expects 401/403).
- [ ] Reset tokens: single use, short expiry, hashed at rest (tests).
- [ ] Admin and money-moving roles require phishing-resistant MFA.

## Sources
- https://pages.nist.gov/800-63-4/sp800-63b.html (passwords, throttling ≤ 100, PSTN restricted, email not OOB, AAL2/AAL3 timeouts)
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html (Argon2id/scrypt/bcrypt/PBKDF2 parameters)
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html (64-bit entropy, `__Host-`, regenerate on privilege change)
- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html (generic error messages)
- https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html (SMS restricted, recovery codes)
- https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html (consistent message, single-use expiring tokens)
- https://www.w3.org/TR/webauthn-3/
- https://passkeys.dev/
