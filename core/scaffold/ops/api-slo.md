# Runbook: API SLO burn (availability and latency)

Alerts: `SLOErrorBudgetBurnFast` (page) / `SLOErrorBudgetBurnSlow` (ticket) for `api-availability`, `api-latency`
Owner: @owner · Dashboard: <link to the RED dashboard> · Last reviewed: {{TODAY}}

## Symptoms
- Fast burn (page): 2% of the 28-day error budget gone in an hour. Users see errors or slowness now.
- Slow burn (ticket): 10% gone in three days. Something degraded quietly; fix it this week.

## Impact
Check which routes fail (`http.route` on the dashboard) and whether payments, sign-in or sync are affected.
Declare an incident (docs/ops/incident-response.md) if users cannot pay, sign in or lose data, or the fast burn
lasts more than 15 minutes.

## Diagnose
1. What changed? Last deploys (`git log --oneline -5 origin/main`), feature-flag edits (`ops/flags.json`),
   config and infrastructure changes.
2. Errors: group by route and status; open a failing trace and read its logs by `trace_id`.
3. Dependencies: database (connections, slow queries), cache, queues, third parties (payment and mobile-money
   provider status pages; their callbacks may be late, see the provider's polling endpoint).
4. Saturation: CPU, memory, connection pools, queue depth (USE dashboard).

## Mitigation
1. A deploy or flag change lines up with the start: roll back the deploy or turn the flag off first, debug later.
2. A dependency is down: switch to the degraded mode (queue the work, show a banner, stop retry storms).
3. Overload: scale out within the budget limits, or shed non-critical traffic.
Copy-pasteable commands for your platform go here. Never paste secrets; say where they live.

## Escalate
Phone the secondary (not chat) if the fast burn is not mitigated within 30 minutes, or immediately on data
loss, a security incident or a money mismatch.

## Afterwards
Keep the timeline (UTC). Postmortem (docs/postmortems/_template.md) when users were affected or more than 20%
of the monthly budget burned. Feed repeat causes into tests and checks.
