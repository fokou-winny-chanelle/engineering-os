---
id: testing/performance-k6
title: Performance and load testing with k6 - test types, open vs closed scenarios, thresholds as pass/fail, realistic data, where to run
area: testing
read_when: writing or running a load test, choosing a k6 executor, setting latency/error thresholds, deciding where load tests run and how to read the results
verified: 2026-10-10
revisit_days: 180
sources: ["https://grafana.com/docs/k6/latest/testing-guides/test-types/", "https://grafana.com/docs/k6/latest/using-k6/scenarios/", "https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/", "https://grafana.com/docs/k6/latest/using-k6/thresholds/", "https://grafana.com/docs/k6/latest/using-k6/checks/", "https://github.com/grafana/setup-k6-action"]
---
# Performance and load testing (k6)

A load test answers one question you wrote down first: "does checkout stay under 400 ms p95 at 20 requests per second with under 1% errors?". Without the question and a pass/fail threshold, it is just a graph. What to optimise, SLOs and capacity planning are in the `performance-scale` pack (and `architecture/api-performance`); this ref is how to test. k6 is licensed AGPL-3.0: ask a human before modifying, embedding or redistributing it.

## Decision guide

**1. Pick the test type** (k6 test-type guide).
| Type | Load | Duration | Run when |
|---|---|---|---|
| Smoke | minimal | seconds to a minute | every script change; weekly against staging |
| Average-load | typical production | 5-60 min | before releases that touch hot paths |
| Stress | above average | 5-60 min | before an expected peak |
| Soak | average | hours | after changes to memory, pools, caches, queues |
| Spike | very high, sudden | a few minutes | launches, campaigns, seasonal peaks |
| Breakpoint | rising until it breaks | as long as needed | a few times, to find the limit |

**2. Open or closed model.** Closed (VU-based executors such as `ramping-vus`): each virtual user waits for a response before sending the next, so a slow system receives *less* load and hides its own slowness. Open (`constant-arrival-rate`, `ramping-arrival-rate`): requests arrive at a set rate regardless, like real users. Use open for APIs and web traffic (the scaffold does); watch `dropped_iterations`, which means k6 lacked VUs or the system is saturated.

**3. Thresholds are the test.** A failed threshold makes k6 exit non-zero, which fails CI; failed checks alone do not fail the run, so pair them with a `checks: ["rate>0.99"]` threshold. Set thresholds per endpoint with tags (`http_req_duration{name:checkout}: ["p(95)<400"]`), use percentiles not averages, and `abortOnFail` on error rate so a broken target does not get hammered for 30 minutes. Derive the numbers from your SLOs (`performance-scale` pack), not from what the first run happened to show.

**4. Realistic data and behaviour.**
- Model traffic from real metrics: endpoint mix, request rate, payload sizes, think time (`sleep` between steps).
- Vary inputs: load ids/users from a `SharedArray` file (synthetic or anonymised, `testing/test-data`); one id repeated measures only the cache.
- Use dedicated test accounts and tokens; seed a production-sized dataset (`data/postgres-queries` on why small tables lie).
- Group URLs with dynamic ids under one `name` tag so metrics stay readable.

**5. Where to run.**
| Place | Good for | Not for |
|---|---|---|
| Laptop | writing scripts, smoke against local | numbers you will quote |
| GitHub-hosted runner (`grafana/setup-k6-action`, SHA-pinned in the scaffold) | smoke and regression trends on a schedule or manual dispatch | capacity claims (shared hardware, one region) |
| Dedicated load machine or k6 Operator / cloud service near the target | average, stress, soak, breakpoint | PR checks |

Target staging sized like production, or production only in an agreed window with the team watching. Never on every PR: slow, noisy and needs a deployed target.

**6. Read the results with server metrics.** Correlate k6 latency and errors with CPU, DB connections, slow queries and queue depth. Change one thing at a time and re-run the same script with the same data to compare.

## Anti-patterns
- No thresholds, or thresholds on averages; "it felt fast".
- Closed-model tests that report great latency because the system throttled the load generator.
- The same request with the same id in a loop; no think time; an empty database.
- Load testing production unannounced, or from the same small machine as the app.
- Quoting capacity from a shared CI runner; comparing runs with different data or environments.

## Checks
- `eos scaffold load-k6`: `load/smoke.js`, `load/load.js` (ramping arrival rate, per-endpoint thresholds, abortOnFail, dropped iterations, SharedArray data) and `.github/workflows/load.yml` (manual dispatch plus weekly smoke when `LOAD_BASE_URL` is set; never on pull requests).
- Run locally: `k6 run -e BASE_URL=http://127.0.0.1:8000 load/smoke.js`; exit code 0 means every threshold passed.
- Release checklist (`testing/mobile-qa`): a load run for changes on hot paths, results linked in the PR.

## Sources
- k6 test types: https://grafana.com/docs/k6/latest/testing-guides/test-types/
- Scenarios: https://grafana.com/docs/k6/latest/using-k6/scenarios/ · executors: https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/
- Thresholds: https://grafana.com/docs/k6/latest/using-k6/thresholds/ · checks: https://grafana.com/docs/k6/latest/using-k6/checks/
- setup-k6-action: https://github.com/grafana/setup-k6-action
