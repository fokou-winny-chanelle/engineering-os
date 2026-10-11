---
id: security/secrets-keys
title: Secrets and key management
area: security
read_when: adding an API key, DB password, signing key or token; configuring CI/CD credentials; responding to a leaked secret
verified: 2026-10-10
revisit_days: 365
sources: ["https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html", "https://docs.github.com/en/code-security/concepts/secret-security/push-protection", "https://docs.github.com/en/actions/concepts/security/openid-connect", "https://docs.cloud.google.com/kms/docs/envelope-encryption", "https://github.com/gitleaks/gitleaks", "https://github.com/trufflesecurity/trufflehog"]
---
# Secrets and key management

A secret is anything that grants access: passwords, API keys, OAuth client secrets, signing keys, webhook secrets, database URLs with credentials, cloud keys, session-signing keys. The goal is: **no long-lived secret where a short-lived identity works; every remaining secret in one manager, scoped, rotated, audited, and never in git, logs, prompts or chat.**

## Decision guide

**Prefer identities over secrets:**

| Situation | Best | Acceptable | Avoid |
|---|---|---|---|
| CI deploys to cloud | GitHub Actions **OIDC** federation → short-lived cloud credentials (no stored secret) | environment-scoped secrets with required reviewers | org-wide long-lived cloud keys |
| App on cloud reads DB/storage | workload identity / instance role / managed identity | secret manager with auto-rotation | `.env` baked into the image |
| App calls a SaaS API | secret manager entry, least scope, per environment | encrypted env var injected at runtime | key in source, mobile app or frontend bundle |
| Developer laptop | `.env` (git-ignored) from a dev-only key; `direnv`/1Password CLI | | production keys on laptops |
| AI agents / MCP servers | per-agent, least-privilege, short-lived tokens; dev/test data only | | production credentials, owner-scope tokens, secrets in prompts or MCP config committed to git |

**Secret manager basics (OWASP Secrets Management):** centralise (Vault, AWS/GCP/Azure secret managers, Doppler, 1Password); least privilege per service; audit log of reads; automated rotation where the provider supports it; secrets injected at runtime, not built into images or bundles; separate per environment.

**Encryption keys:** keep in KMS/HSM; use envelope encryption (data keys wrapped by a KMS key) so rotation does not need re-encryption of all data. See `security/crypto`.

**Detection layers:**
1. Pre-commit: gitleaks (eos installs the hook).
2. Push: GitHub **push protection** blocks pushes containing supported secret types (enable on every repo).
3. CI: gitleaks/TruffleHog on the diff; TruffleHog can verify whether a found credential is live, which helps triage.
4. Runtime: log redaction for known secret patterns and `Authorization` headers.

**Leak response (in this order):** 1) **revoke/rotate** the secret at the provider (assume it was copied the moment it was pushed, even to a private repo); 2) check the provider's access logs for use; 3) remove from code and move to the manager; 4) clean history only after rotation (history rewriting does not un-leak forks, caches or clones); 5) write a short incident note and add a detection rule if one was missing.

## Anti-patterns
- "It's a private repo" as a reason to commit secrets; secrets in Docker build args/layers, Terraform state in git, notebooks, screenshots, tickets.
- Logging full request headers, connection strings or exception messages that include credentials.
- Sharing one API key across services and environments, so rotation breaks everything and attribution is impossible.
- `NEXT_PUBLIC_*`/`VITE_*`/mobile config holding a server-side secret (anything shipped to clients is public).
- Pasting secrets into AI chats, prompts, MCP configs or agent memory.
- Disabling push protection or adding broad gitleaks allow-lists to get a build green.

## Checks
- [ ] gitleaks runs in pre-commit and CI; push protection enabled (repo settings checklist).
- [ ] No secrets in the repo history scan (`gitleaks git`), `.env*` git-ignored except `.env.example` with placeholders.
- [ ] CI uses OIDC for cloud access where the provider supports it; remaining CI secrets are environment-scoped.
- [ ] Each secret has an owner, scope, and rotation method documented (`docs/security/secrets.md` or the manager's metadata).
- [ ] Log redaction test: a request with `Authorization: Bearer …` produces logs without the token.
- [ ] Leak-response runbook exists and names who can revoke each provider's keys.

## Sources
- https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html
- https://docs.github.com/en/code-security/concepts/secret-security/push-protection
- https://docs.github.com/en/actions/concepts/security/openid-connect
- https://docs.cloud.google.com/kms/docs/envelope-encryption
- https://github.com/gitleaks/gitleaks
- https://github.com/trufflesecurity/trufflehog (find, verify and analyze leaked credentials)
