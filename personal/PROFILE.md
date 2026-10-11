<!-- Generic template (≤400 tokens, loaded everywhere). Your own: personal/PROFILE.user.md (git-ignored), then `eos bootstrap`. -->
# How I work (personal profile)

## Me
- Role and stacks: <fill in>. Explain new jargon briefly once.
- Language: answer in the language I write in.

## Answers
- Lead with the answer, then the reasoning. Keep it short; use tables for comparisons.
- Back claims with evidence: file:line, the check you ran and its result, links to official docs. Say "I don't know" rather than guess versions, prices or APIs.
- Flag risk early: money, security, data loss, irreversible steps.

## Defaults (unless the project says otherwise)
- PostgreSQL; money as integer minor units or exact decimals; UTC `timestamptz`; idempotency keys on payment writes; outbox for events.
- Contract-first APIs (OpenAPI) with RFC 9457 errors; tests first for domain logic; conventional commits; small PRs.
- Never deploy, apply or migrate against shared environments, or force-push, without me.
