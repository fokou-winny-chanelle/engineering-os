---
id: ops/dashboards-alerting
title: Dashboards (RED, USE, golden signals), alerting and on-call for a solo developer or small team, alert fatigue, status pages
area: ops
read_when: building a dashboard, adding or reviewing an alert, setting up paging or an on-call rota, too many alerts or pages, deciding whether to run a status page
verified: 2026-10-10
revisit_days: 180
sources: ["https://sre.google/sre-book/monitoring-distributed-systems/", "https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/", "https://www.brendangregg.com/usemethod.html", "https://prometheus.io/docs/practices/alerting/", "https://sre.google/sre-book/being-on-call/", "https://response.pagerduty.com/during/external_communication_guidelines/"]
---
# Dashboards, alerting and on-call

Monitoring answers two questions: what is broken (symptoms users feel) and why (causes). Page on the first; use dashboards and traces for the second.

## Decision guide

**1. Three lenses, used together.**
| Method | Apply to | Signals |
|---|---|---|
| Golden signals (Google SRE) | each user-facing service | latency, traffic, errors, saturation |
| RED (Tom Wilkie) | each request-driven service | rate, errors, duration |
| USE (Brendan Gregg) | each resource: CPU, memory, disk, DB connection pool, queue, worker pool | utilization, saturation, errors |
RED tells you users are hurting; USE tells you which resource is the bottleneck.

**2. One service overview dashboard first**, top to bottom:
1. SLO status and budget remaining (from `ops/slo.json`).
2. RED: requests per second, error ratio by route and status, latency p50/p95/p99 (histogram, not averages).
3. Saturation: CPU, memory, DB connections in use vs pool size, queue depth and age of the oldest message.
4. Dependencies: payment and mobile-money provider error rate and latency, database query time.
5. Deploys and flag changes as annotations, so "what changed?" is one glance.
Link each panel to traces and logs filtered by route. Delete panels nobody looked at during the last incident.

**3. What deserves a page.** Page only for user-visible harm that needs a human now: SLO fast burn (`ops/slo-error-budgets`), payments failing, data loss risk, a security event. Everything else is a ticket (slow burn, a disk at 80%, a certificate expiring in 14 days) or a dashboard. Test every page against the SRE book's rules: it is actionable, urgent, needs intelligence (a robotic response should be automated), and is about a new problem.

**4. Alert hygiene rules** (Prometheus practices + SRE book):
- Alert on symptoms high in the stack (user-facing latency and errors), not on every cause.
- Every alert has `severity` (`page` or `ticket`) and a `runbook_url`; `eos ops check` enforces both and that the runbook file exists.
- Allow slack for blips (burn-rate windows, `for:` durations); never page on a single scrape.
- Route by severity: page → phone call or push that wakes you; ticket → issue tracker or a daily digest. Chat channels are not pagers.
- Review weekly: every page that fired, was it actionable? Delete, demote or fix the alert that was not.

**5. On-call for one person or a small team.**
- Solo: you cannot be awake 24/7. Decide hours of cover, say so (status page or terms), and make out-of-hours pages rare by design: fast-burn SLO alerts only, auto-rollback and kill switches (`ops/feature-flags`) so the first response is one command.
- Name a backup person who can at least roll back and post a status update, with access tested.
- Small team: a weekly rotation with primary and secondary, handover notes, and compensation or time off after night pages. Google caps on-call work at 25% of an SRE's time; use that as a ceiling, not a target.
- Track pages per week per person; rising numbers are a reliability bug, not a staffing plan.

**6. Alert fatigue is a reliability risk.** People who get paged for noise stop reacting. Signs: pages acknowledged and ignored, the same alert firing daily, "known noisy" in chat. Fix by deleting alerts, moving them to tickets, raising windows, or fixing the underlying problem; never by muting the rota.

**7. Status pages.** Run one once customers depend on you (payments, B2B, an API others build on). Host it separately from your infrastructure (a hosted status service or a static page on another provider), so it survives your outage. PagerDuty's guidance: first public message within minutes of declaring an incident, then updates on a fixed rhythm (they use at least every 20 minutes for the first two hours) and whenever impact changes. Templates live in `docs/ops/incident-response.md` (`eos scaffold ops`). Automated status from health checks is fine for "up/down"; humans write incident text.

## Anti-patterns
- Dashboards of 40 panels; averages hiding p99; CPU alerts that page at 3 a.m. while users are fine.
- Alerts with no runbook; alerts that only post to a busy chat channel.
- Paging on causes (one pod restarted) instead of symptoms (users get errors).
- A status page hosted on the same server it reports on; "all systems operational" during an outage.
- One person on call forever with no backup and no limit.

## Checks
- `eos ops check`: every `- alert:` in `ops/alerts`, `monitoring/alerts`, `prometheus/rules` has severity and a runbook that exists (warns without a Mitigation section).
- `promtool check rules` / `test rules` in the ops workflow (`eos scaffold ops`).
- Weekly page review (manual): count, actionable share, alerts deleted or demoted.

## Sources
- Google SRE book, Monitoring Distributed Systems (golden signals, paging philosophy): https://sre.google/sre-book/monitoring-distributed-systems/
- Tom Wilkie, The RED Method: https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
- Brendan Gregg, The USE Method: https://www.brendangregg.com/usemethod.html
- Prometheus, Alerting practices: https://prometheus.io/docs/practices/alerting/
- Google SRE book, Being On-Call: https://sre.google/sre-book/being-on-call/
- PagerDuty, External communication guidelines: https://response.pagerduty.com/during/external_communication_guidelines/
