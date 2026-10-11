---
id: testing-qa
title: Testing & QA
kind: phase
mode: files
when: writing or changing tests, fixtures, test config, load or e2e suites
description: Use when writing or changing tests or test infrastructure - unit, integration, contract, e2e, performance, mutation. Test pyramid, AC traceability, determinism, anti-cheating rules.
globs: ["**/tests/**", "**/test/**", "**/__tests__/**", "**/*.test.*", "**/*.spec.*", "**/test_*.py", "**/*_test.py", "**/*_test.go", "**/e2e/**", "**/load/**", "**/conftest.py", "**/fixtures/**"]
next: [code-review, security]
---
# Testing & QA

## Entry
A story with AC IDs. The code under test exists or is being written test-first.

## Test portfolio (each layer has a job)
| Layer | Proves | Typical tools (stack pack decides) |
|---|---|---|
| Unit | domain rules and edge cases, fast (<1 s each) | pytest/Vitest/go test + property-based (Hypothesis/fast-check) |
| Integration | real DB/queue/cache adapters work | Testcontainers or compose; never mock the DB you own |
| Contract | implementation ↔ spec, consumer ↔ provider | schemathesis, Pact, buf |
| E2E | the main AC paths through the UI/API | Playwright (+ axe) |
| Performance | NFR latency/throughput at target load | k6 (thresholds = NFRs) |
| Mutation | the tests actually catch bugs (for critical modules) | mutmut, Stryker |

## Standards
1. Name tests after behaviour and AC ID, e.g. `test_AC12_duplicate_payment_returns_original_receipt`. Every AC has at least one test.
2. Arrange-Act-Assert. One behaviour per test. Assert outcomes, not implementation details.
3. Deterministic.
   - No real network, clock or randomness without injection or seeding.
   - No sleeps; poll with a timeout instead.
   - Flaky tests are quarantined with a ticket, not retried forever.
4. Unhappy paths outnumber happy paths for money, auth and integrations: duplicates, timeouts, partial failure, concurrency (run two requests in parallel), boundary values.
5. Test data. Use builders/factories with no shared mutable fixtures. Use synthetic data only, never production PII.
6. Coverage is a floor, not a goal. Keep the project threshold (e.g. ≥80% lines on changed code). For critical modules (money, auth), use a mutation score target instead of chasing coverage.
7. Anti-cheating (non-negotiable for AI):
   - Never delete, skip, xfail or loosen a test, assertion or threshold to get green.
   - Never special-case test inputs in production code.
   - Never mock the unit under test.
   - If a test is wrong, stop, explain and get approval. Use `eos test-integrity` in CI to flag these changes.
8. Performance tests use thresholds taken from the NFRs and run against a production-like environment on a schedule or before a release, not on every commit.

## Deliverables
- Tests per layer as appropriate, fixtures/builders, and CI wiring. Starters: `eos scaffold tests-python` (testcontainers fixture, factories, strategy doc), `eos scaffold e2e-node` (Playwright smoke + axe).
- For releases: a performance report and a mutation report for critical modules.

## Automated checks
- The stack test commands (unit and integration) on every PR, plus coverage on the diff.
- `eos test-integrity` (skips, assert removal and threshold changes need a human label).
- E2E on PR for critical paths; performance and mutation tests nightly or pre-release.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `testing/strategy` (pyramid/trophy/honeycomb, what not to test) · `testing/unit-design` (doubles, over-mocking) · `testing/integration` (Testcontainers) · `testing/e2e-playwright` (+visual, a11y) · `testing/property-fuzz` · `testing/mutation` · `testing/performance-k6` · `testing/test-data` · `testing/flaky-speed` (quarantine, retries, sharding) · `testing/coverage-ai-code` (diff coverage, test cheating) · `testing/llm-evals` · `testing/mobile-qa` (devices, charters, release checklist) · `api/testing` (contracts) · `security/security-testing` · `data/orm-sql-testing` · `frontend/errors-observability` (frontend test map).

## Exit checklist (Definition of Done)
- [ ] Each AC is mapped to a passing test, and unhappy paths are covered.
- [ ] No new skips or loosened assertions (or they're approved with a ticket).
- [ ] Tests are deterministic locally and in CI. No sleeps, no real external calls.
- [ ] Coverage and mutation targets are met for critical code.

## Handoff → code-review / security
Pass the test report, the coverage diff and the list of known gaps with tickets.

## Stop & escalate
Stop when a test fails for reasons outside the change, when the spec and the test disagree, or when you are tempted to edit a test only to pass.
