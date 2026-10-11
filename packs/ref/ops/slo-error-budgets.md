---
id: ops/slo-error-budgets
title: SLIs, SLOs, error budgets and multiwindow burn-rate alerting
area: ops
read_when: defining or changing an SLO, choosing what to page on, writing or reviewing ops/slo.json or alert rules, deciding whether to freeze releases after an outage
verified: 2026-10-10
revisit_days: 180
sources: ["https://sre.google/sre-book/service-level-objectives/", "https://sre.google/workbook/implementing-slos/", "https://sre.google/workbook/alerting-on-slos/", "https://sre.google/workbook/error-budget-policy/", "https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/", "https://prometheus.io/docs/guides/opentelemetry/"]
---
# SLOs, error budgets and burn-rate alerts

An **SLI** is a measurement of what users feel, best written as a ratio: good events / total events. An **SLO** is the target for that ratio over a window (99.5% of requests succeed over 28 days). An **SLA** is a contract with consequences; keep it looser than the SLO. The **error budget** is what the SLO leaves over: 99.5% over 28 days allows 0.5% bad requests, or about 202 minutes of full outage (`eos ops budget`). The Google SRE books are linked, not quoted (CC BY-NC-ND).

## Decision guide

**1. Pick journeys, not components.** One to three SLOs per service at first: "API requests succeed", "API answers within 500 ms", "payment callbacks are processed within 2 minutes". Measure as close to the user as you can (load balancer or service edge), not CPU or pod restarts.

**2. Write SLIs as good/total ratios.** Availability: non-5xx / all requests. Latency: requests faster than a threshold / all requests (a histogram bucket, e.g. `le="0.5"`), not an average. Freshness, correctness and throughput work the same way for jobs and pipelines. Exclude what users did wrong (4xx) only if you are sure it is not your bug.

**3. Choose the objective on purpose.**
- 100% is the wrong target: it blocks change and costs a fortune.
- Do not copy current performance; users come to rely on whatever you deliver. Keep a safety margin: an internal SLO tighter than anything you promise.
- Each extra nine cuts the budget tenfold: 99% over 28 days ≈ 6.7 h of outage, 99.9% ≈ 40 min, 99.99% ≈ 4 min. A solo developer cannot respond fast enough to defend 99.99%; `eos ops check` warns above it.
- Window: 28 or 30 days is common; 28 keeps the same weekdays in every window.

**4. Alert on budget burn, not on symptoms of the moment.** The Workbook recommends multiwindow, multi-burn-rate alerts. Burn rate = how fast the budget is being spent (1 = exactly on budget over the window).
| Severity | Budget spent | Long window | Short window | Burn rate (30 d) |
|---|---|---|---|---|
| page | 2% | 1 h | 5 m | 14.4 |
| page | 5% | 6 h | 30 m | 6 |
| ticket | 10% | 3 d | 6 h | 1 |
The short window (1/12 of the long one) makes the alert stop soon after the problem stops. Fire only when both windows are over `burn × (1 − objective)`. `eos ops alerts` generates exactly this from `ops/slo.json`, scaled to your window (28 days: 13.44 / 5.6 / 0.93), with a runbook link on every alert.

**5. Test the alerts.** `promtool test rules` feeds synthetic series and asserts which alerts fire. The `ops` scaffold ships tests: 10% errors for an hour pages, 0.3% errors against a 99.5% SLO does not. Change the SLO, regenerate, rerun.

**6. Low traffic breaks ratio alerts.** With a few requests per hour, one failure can look like a 50% error rate. Options from the Workbook: synthetic traffic (a prober), combining small services into one SLO, longer windows, or making single failures harmless (retries, queues).

**7. Write an error budget policy and use it.** Agree up front what happens when the budget is gone: stop feature releases except urgent fixes and security patches until the SLO is met again; a postmortem when one incident burns more than 20% of the four-week budget (the Workbook's example policy). For a solo developer: "budget gone → next work is reliability".

**8. Metric names.** OpenTelemetry's `http.server.request.duration` (seconds) arrives in Prometheus via OTLP as `http_server_request_duration_seconds_count` / `_bucket`, and `service.name` becomes the `job` label. Check names in your backend before trusting a query; a typo yields an empty series and an alert that never fires (the promtool tests catch that).

## Anti-patterns
- SLOs on CPU, memory or pod restarts; averages instead of ratios or percentiles.
- An objective chosen because a dashboard showed 99.97% last month.
- Paging on "error rate > 1% for 5 minutes" with no link to a budget: noisy at night, blind to slow leaks.
- Alerts without a runbook or owner; SLO documents nobody reads; changing the objective mid-incident to silence a page.
- One SLO per endpoint (hundreds of alerts) instead of per journey.

## Checks
- `eos ops check` (and `eos check` in CI): schema, owner, objective range, runbook exists, `{{window}}` in PromQL; fails when generated rules are stale.
- `eos ops alerts [--check]`, `eos ops budget`, `eos ops runbook <name>`.
- `eos scaffold ops`: `ops/slo.json`, generated rules, promtool tests, ops workflow (`promtool check rules` / `test rules`). Edits to `ops/slo.json` count as a gate change for `eos test-integrity`.

## Sources
- Google SRE book, Service Level Objectives: https://sre.google/sre-book/service-level-objectives/
- Google SRE Workbook, Implementing SLOs: https://sre.google/workbook/implementing-slos/ · Alerting on SLOs: https://sre.google/workbook/alerting-on-slos/ · Example Error Budget Policy: https://sre.google/workbook/error-budget-policy/
- Prometheus, Unit testing for rules: https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/
- Prometheus, Using Prometheus as your OpenTelemetry backend: https://prometheus.io/docs/guides/opentelemetry/
