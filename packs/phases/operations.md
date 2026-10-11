---
id: operations
title: Observability, operations & incident response
kind: phase
mode: both
when: adding logging/metrics/tracing, SLOs, alerts, runbooks or handling an incident
description: Use for logs, metrics, traces, SLOs, alerts, dashboards, runbooks, incidents or postmortems.
globs: ["**/runbooks/**", "**/alerts/**", "**/dashboards/**", "**/otel*", "**/*telemetry*", "**/*logging*", "**/slo*", "**/monitoring/**", "**/postmortems/**"]
next: [maintenance, documentation]
---
# Observability, operations & incident response

## Entry
The service is deployed or about to be, the NFRs and SLO targets exist, and an on-call owner is named.

## Standards
1. SLOs first. For each user journey, pick an SLI (e.g. % of successful payment requests under 1 s), an SLO target and an error budget. Alerts fire on burn rate (fast and slow windows), not on raw CPU usage.
2. Three signals, correlated.
   - Structured logs (JSON, trace ID, no PII or secrets).
   - Metrics: RED for services, USE for resources, plus business KPIs.
   - Traces via OpenTelemetry with context propagated across HTTP and queues.
3. Every alert is actionable. It has an owner, a severity, a dashboard link and a runbook link. An alert that never needs action should be deleted or turned into a ticket.
4. Runbooks (`docs/runbooks/<alert>.md`): symptoms → checks → mitigation steps → escalation → rollback. Copy-pasteable commands go in the runbook; secrets do not.
5. Incident response.
   - Declare early and assign roles: incident commander, communications, ops.
   - Keep a timeline in UTC.
   - Mitigate first (rollback or flag off) and find the root cause later.
   - Communicate on a fixed cadence.
6. Blameless postmortems within 5 working days.
   - Impact (users, money, duration)
   - Timeline
   - Contributing factors
   - What went well
   - Action items, each with an owner and a due date
   Repeat causes feed `docs/ai/lessons.md` and new automated checks.
7. Track the DORA metrics: deployment frequency, lead time for changes, change failure rate, failed-deployment recovery time, and deployment rework rate. Use them to improve the system, never to rank individuals.
8. AI in operations.
   - The AI reads logs and dashboards (read-only MCP/tools) and drafts the timeline and postmortem.
   - It never runs production-mutating commands. It proposes them, and a human runs them.
   - Production data accessed during an incident stays out of prompts unless it is masked.

## Deliverables
- An SLO doc, alert rules as code, dashboards as code (where possible), runbooks, and postmortems in `docs/postmortems/`.

## Automated checks
- Alert-rule lint/validation (e.g. promtool or the vendor CLI); a "runbook link exists" check on alerts.
- Synthetic checks on critical journeys.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `ops/slo-error-budgets` (SLIs, burn-rate alerts, budget policy) · `ops/opentelemetry` (traces, metrics, logs, sampling) · `ops/dashboards-alerting` (RED/USE, paging hygiene) · `ops/incident-runbooks` (severity, roles, comms, postmortems) · `ops/dr-chaos` (RPO/RTO, restore drills, game days) · `ops/capacity-cost` (capacity, budgets, FinOps) · `llm/observability-otel` (GenAI spans, token cost) · `ops/africa-connectivity` (outages, regions, mobile-money callbacks) · `data/postgres-operations` (backups/PITR, upgrades) · `data/postgres-concurrency` (locks, vacuum).

## Exit checklist (Definition of Done)
- [ ] Each critical journey has an SLI, an SLO and burn-rate alerts with runbooks.
- [ ] Logs, metrics and traces are correlated by trace ID. No PII appears in telemetry.
- [ ] On-call knows the new alerts. Dashboards are linked from the service README.
- [ ] Postmortem actions are tracked to closure.

## Handoff → maintenance / documentation
Pass postmortem actions, tech-debt items, and runbook or doc updates.

## Stop & escalate
Escalate immediately on data loss, a security incident, a money mismatch or a breach of the SLA. Wake the human on-call; don't wait.
