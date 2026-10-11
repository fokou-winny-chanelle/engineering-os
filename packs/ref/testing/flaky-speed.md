---
id: testing/flaky-speed
title: Flaky test management (detection, quarantine with expiry, retry policy) and test suite speed (parallelism, affected-test selection, sharding, caching)
area: testing
read_when: a test fails intermittently, deciding on retries, adding or removing a quarantine entry, the suite or CI is too slow, setting up sharding, test selection or caches
verified: 2026-10-10
revisit_days: 180
sources: ["https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html", "https://martinfowler.com/articles/nonDeterminism.html", "https://docs.pytest.org/en/stable/explanation/flaky.html", "https://wix.github.io/Detox/docs/troubleshooting/flakiness", "https://playwright.dev/docs/test-retries", "https://playwright.dev/docs/test-sharding", "https://vitest.dev/guide/cli", "https://vitest.dev/guide/improving-performance", "https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching", "https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations"]
---
# Flaky tests and test speed

A flaky test passes and fails on the same code. Flakes compound: at 0.5% flakiness per test, a 100-test suite fails about 40% of runs (Detox docs: 1 − 0.995^100). Google measured about 1.5% of all test runs flaky, almost 16% of tests with some flakiness, and about 84% of pass→fail transitions involving a flaky test. Once people learn to re-run until green, real failures get ignored too.

## Decision guide

**1. Detect.**
- Playwright marks a test that fails then passes on retry as **flaky** in the report; pytest-rerunfailures reports reruns. Read these, do not just count green builds.
- Reproduce with repetition: `npx playwright test --repeat-each=20 file.spec.ts`, pytest-flakefinder, or a shell loop. Shuffle order (pytest-randomly, Vitest `--sequence.shuffle`) and run in parallel (pytest-xdist) to expose order and shared-state bugs.

**2. Common causes** (Fowler, pytest docs): lack of isolation (shared DB rows, globals, files, ports), async waits (bare sleeps instead of polling with a timeout or web-first assertions), remote services (stub them or use a container, `testing/integration`), time and time zones (inject a clock, `page.clock`), resource leaks, random data without a seed, test order dependence, floats compared with `==` (`pytest.approx`).

**3. Quarantine with an owner and an end date** (`eos quarantine`).
- `eos quarantine add "<test id>" --reason "…" --owner @you --issue <url> --days 7` writes `tests/quarantine.json`. Max 14 days by default (`.eos/config.json` → `testing.quarantine_max_days`); Fowler suggests a limit such as a week.
- While active, the pytest conftest template marks the test `xfail(strict=False)` (it still runs and reports), and the Playwright config skips it via `grepInvert`.
- `eos check` (CI) and `eos verify` (standard lanes and up) fail when an entry is expired or missing fields. When it expires, the test counts again: fix it, delete it, or renew it in a reviewed PR. Edits to the file count as a test-gate change for `eos test-integrity`.
- pytest's docs call permanent `xfail(strict=False)` quarantine "rather dangerous"; that is why entries expire.

**4. Retry policy.**
| Layer | Retries | Why |
|---|---|---|
| Unit | 0 | a flaky unit test is a bug in the test or code |
| Integration | 0, or 1 in CI with reporting | real deps can blip; the retry must be visible |
| E2E (Playwright) | 1 in CI with `trace: 'on-first-retry'` | collect a trace of the flake; once the suite is clean, add `--fail-on-flaky-tests` |
Never raise retries or timeouts to make a test pass; never retry silently.

**5. Speed: order of attack.**
1. Measure: the slowest tests (`pytest --durations=20`, reporter timings); usually a few tests or one fixture dominate.
2. Push tests down the pyramid/trophy (`testing/strategy`): a slow E2E check of a rule becomes a unit test.
3. Share expensive setup: one container per session, transactions rolled back per test (`testing/integration`); worker-scoped fixtures in Playwright.
4. Parallelise in-process: pytest-xdist `-n auto`, Vitest and Playwright workers (`fullyParallel`). Fix the isolation bugs this exposes instead of turning it off.
5. Select affected tests locally: `vitest --changed`, `playwright test --only-changed=main`, `--last-failed`; in monorepos the build tool's affected graph. CI on main still runs everything.
6. Shard across machines: a matrix job with `--shard=${{ matrix.shard }}/4` (Playwright, Vitest), then merge reports (blob reporter + `merge-reports`).
7. Cache dependencies: built-in caching in `setup-node`/`setup-python`/`setup-uv`, or `actions/cache` keyed on the lockfile. Entries unused for 7 days are evicted. Do not restore caches written by untrusted pull-request workflows into privileged jobs.

**6. Lanes keep the fast path fast.** `eos verify` on trivial changes runs nothing new; standard adds the in-process quarantine check (milliseconds); risky adds changed-line coverage from an existing report. Mutation, load and long property runs live in CI or on schedules.

## Anti-patterns
- Re-run the pipeline until it is green; "known flaky" comments with no ticket.
- `@skip` or `xfail` with no expiry, owner or issue; quarantine as a permanent home.
- Global retries of 3 on every test; raising timeouts to hide slowness.
- `sleep(2)` to wait for async work; tests that need a fixed order.
- Selecting tests on main or on release builds (affected-test selection is for fast feedback, not the final gate).

## Checks
- `eos quarantine check` / `list`; part of `eos check` and `eos verify` (standard and up).
- `eos scaffold quarantine` adds the file and `docs/testing/flaky-tests.md`; the tests-python and e2e-node scaffolds honour it.
- Playwright CI defaults in the scaffold: `retries: 1`, traces on first retry, `forbidOnly`.

## Sources
- Google Testing Blog, Flaky Tests at Google (2016): https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html
- Martin Fowler, Eradicating Non-Determinism in Tests: https://martinfowler.com/articles/nonDeterminism.html
- pytest, Flaky tests: https://docs.pytest.org/en/stable/explanation/flaky.html · Detox, flakiness: https://wix.github.io/Detox/docs/troubleshooting/flakiness
- Playwright retries: https://playwright.dev/docs/test-retries · sharding: https://playwright.dev/docs/test-sharding
- Vitest CLI: https://vitest.dev/guide/cli · performance: https://vitest.dev/guide/improving-performance
- GitHub Actions dependency caching: https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching · matrix jobs: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
