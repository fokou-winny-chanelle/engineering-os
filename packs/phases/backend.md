---
id: backend
title: Backend implementation
kind: phase
mode: files
when: writing or changing server-side code
description: Use when writing or changing server-side code - handlers, services, jobs, integrations. Layering, validation, errors, transactions, idempotency, concurrency, logging.
globs: ["**/*.py", "**/*.go", "**/*.rs", "**/*.java", "**/*.php", "**/*.rb", "**/*.cs", "**/*.ex", "**/server/**", "**/api/**", "**/services/**", "**/*.service.ts", "**/*.controller.ts"]
next: [testing-qa, code-review]
---
# Backend implementation

## Entry
An approved story with ACs. The contract and migration exist or are part of the plan. You know which stack pack applies.

## Standards
1. Plan the slice. List the files you'll touch, the tests you'll write first, and the risks. Keep the change small (one story, about 500 changed lines or fewer). Write the test first for the logic and for each AC ID.
2. Layering:
   - transport (HTTP/CLI/consumer), which handles parsing and auth only;
   - application/service, where use-cases and transactions live;
   - domain (pure rules, no I/O);
   - infrastructure (DB, HTTP clients, queues).
   Dependencies point inward, and boundaries are enforced by a tool.
3. Validate at the edge. Parse input into typed objects (schemas) once. Inner code trusts types. Bound every input (size, length, range).
4. Errors. Use typed domain errors, mapped to a protocol error in exactly one place. Never swallow exceptions, never use a bare catch-all without logging plus rethrowing, and never let an error message expose internals.
5. Transactions. One unit of work per use-case. No network calls inside a DB transaction. Use an outbox for events, and choose locking explicitly for balances and stock.
6. Idempotency and retries. Externally triggered writes take an idempotency key. Outbound calls have a timeout and retry only idempotent operations (with backoff and jitter). Handle duplicate deliveries.
7. Concurrency. Never block the event loop in async code. Thread pools and connection pools are sized and bounded. Background jobs are idempotent and resumable, and have a dead-letter path.
8. Config and secrets. Read config from env through one typed settings object and fail fast at startup. Secrets come from env or a secret manager and are never logged.
9. Observability. Use structured JSON logs that carry a request/trace ID, a domain event name and IDs, but no PII or secrets. Add metrics for RED (rate, errors, duration) and spans around external calls.
10. Money. Use exact decimal or integer minor units, round explicitly, and have a test for each rounding and currency case. Money and auth code is flagged for human review.
11. Dependencies. Before adding a library, check its maintenance, licence and size. Prefer the standard library or existing dependencies. Pin through the lockfile.

## Deliverables
- Code plus tests (unit tests for domain logic; integration tests for DB and adapters), updated contract and generated types, and log/metric additions.
- A PR summary with AC IDs covered, risks and checks run.

## Automated checks (commands come from the stack pack)
- format, lint, type-check, unit tests and integration tests (real DB in a container, not mocks of the DB), plus the boundary lint.
- Dependency audit, and secrets scan on commit.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `architecture/resilience` (timeouts, retries) · `architecture/api-performance` (N+1, pagination) · `architecture/event-driven` (jobs, consumers) · `data/orm-sql-testing` (ORM pitfalls, test data) · `data/postgres-queries` (EXPLAIN, upserts, batching) · `data/search-redis` · `security/input-injection` · `security/payments` (webhooks, ledger) · `security/secrets-keys` · `api/errors-problem-details` · `api/reliability` (idempotency keys, ETags).

## Exit checklist (Definition of Done)
- [ ] Every AC has a passing test named with its AC ID, and unhappy paths are tested.
- [ ] The stack fast and full checks are green (paste the command and its result).
- [ ] No TODOs without a ticket, and no debug prints or commented-out code.
- [ ] Logs, metrics and errors follow the standards. No PII appears in logs.
- [ ] Money, auth or crypto changes are flagged for human review.

## Handoff → testing-qa / code-review
Pass the PR with summary, AC coverage, risks, and anything deferred (with tickets).

## Stop & escalate
Stop after 3 failed attempts on the same failure, when the design needs to change (re-plan), or when tests seem wrong. Explain; don't edit them to pass.
