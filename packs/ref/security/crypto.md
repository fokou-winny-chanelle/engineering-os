---
id: security/crypto
title: Cryptography do's and don'ts (for application developers)
area: security
read_when: encrypting data, hashing, signing, generating tokens/ids, choosing TLS settings, or anyone proposing custom crypto
verified: 2026-10-10
revisit_days: 365
sources: ["https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html", "https://developers.google.com/tink", "https://libsodium.gitbook.io/doc", "https://csrc.nist.gov/pubs/fips/203/final", "https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final", "https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html"]
---
# Cryptography do's and don'ts

Application developers should **compose high-level, misuse-resistant APIs**, not primitives. Cryptographic Failures is A04 in the OWASP Top 10:2025; almost all real failures are misuse (wrong mode, reused nonce, home-made protocol, fast hash for passwords, weak randomness), not broken algorithms. Any new cryptographic code needs a human security review.

## Decision guide

**Pick the job, then the tool:**

| Job | Use | Notes |
|---|---|---|
| Encrypt a field/blob at rest | a high-level AEAD API: Google **Tink** (AEAD), **libsodium** (`crypto_secretbox`/`crypto_aead_*`), or your cloud KMS SDK with envelope encryption | authenticated encryption only (OWASP: AES-GCM or CCM first; AES key ≥ 128 bits, ideally 256) |
| Encrypt lots of data under a managed key | **envelope encryption**: random data key (DEK) per object/tenant encrypts data; KMS key (KEK) wraps the DEK | rotate KEK without re-encrypting data; KEK at least as strong as DEK |
| Passwords | Argon2id / scrypt / bcrypt / PBKDF2 per `security/authentication` | never encryption, never fast hashes |
| Integrity/authenticity between your services or webhooks | HMAC-SHA-256 with a random 32-byte key; constant-time compare | `hmac.compare_digest`, `crypto.timingSafeEqual` |
| Signatures (tokens, releases, receipts) | Ed25519 or ECDSA P-256 via a library (Tink, libsodium, `cryptography`) | verify with an algorithm allow-list |
| Tokens, ids, reset codes, API keys | CSPRNG: Python `secrets`, Node `crypto.randomBytes`/`randomUUID`, Java `SecureRandom` | never `random`, `Math.random`, `uniqid`, timestamps; OWASP: session ids ≥ 64 bits of entropy (`secrets.token_urlsafe(32)` gives 256 bits) |
| Searchable encrypted field (e.g. phone lookup) | store an HMAC ("blind index") alongside the ciphertext | leaks equality; use a separate key |
| Transport | TLS 1.2+ (prefer 1.3) via platform defaults; HSTS | never disable certificate verification |
| Post-quantum | follow your platform's hybrid key exchange (ML-KEM, FIPS 203, published 13 Aug 2024) as it ships; inventory long-lived secrets and signatures now | ML-KEM protects key establishment; it does not replace AES for stored data (OWASP) |

**Key management (NIST SP 800-57, OWASP Key Management):** keys live in a KMS/HSM or secret manager, never in code or the database next to the data; one key per purpose (encryption vs MAC vs signing) and per environment; defined cryptoperiods and rotation that the code supports (key id stored with each ciphertext); access to decrypt is logged and least-privilege. See `security/secrets-keys`.

**Hashing vs encryption vs encoding:** base64/hex is encoding (no secrecy). SHA-256 is a hash (fine for checksums and content addressing, **not** for passwords or as a MAC by itself: use HMAC). Encryption is reversible with a key.

## Anti-patterns
- Inventing a scheme ("we XOR with the user id", "AES then base64 then reverse").
- AES-ECB; AES-CBC/CTR without a MAC; unauthenticated encryption of anything an attacker can modify.
- Reusing a nonce/IV with the same key in GCM or ChaCha20-Poly1305 (catastrophic); hard-coded IVs. Let the library generate nonces.
- MD5/SHA-1 for security; SHA-256 of a password; `==` to compare MACs or tokens (timing leak).
- RSA without OAEP for encryption (OWASP); rolling your own JWT signing/verification.
- Encryption keys in the same database or repo as the encrypted data; one key for everything forever.
- `random`/`Math.random` for anything secret (ruff `S311`; semgrep `eos-js-math-random-secret`).

## Checks
- [ ] ruff `S` passes (S311 weak random, S324 insecure hash, S501 TLS verify off, S413 legacy crypto imports).
- [ ] semgrep `eos-non-constant-time-compare` and `eos-js-math-random-secret` pass.
- [ ] Every ciphertext stores a key id/version; a test decrypts data written with the previous key after rotation.
- [ ] Keys come from KMS/secret manager in all non-local environments (config test).
- [ ] New crypto code has a named human reviewer in the PR.

## Sources
- https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html (AES ≥ 128/256, GCM/CCM first, ECB no, OAEP, CSPRNG table, envelope keys, ML-KEM note)
- https://developers.google.com/tink
- https://libsodium.gitbook.io/doc
- https://csrc.nist.gov/pubs/fips/203/final (ML-KEM, 13 August 2024)
- https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final (key management, cryptoperiods)
- https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
