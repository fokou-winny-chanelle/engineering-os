---
id: ops/capacity-cost
title: Capacity planning, overload handling and cost monitoring (FinOps basics for small teams)
area: ops
read_when: planning for a launch or traffic peak, a service is near its limits, setting autoscaling or connection-pool sizes, setting up cloud budgets and cost alerts, investigating a surprise bill
verified: 2026-10-10
revisit_days: 180
sources: ["https://sre.google/sre-book/handling-overload/", "https://sre.google/workbook/managing-load/", "https://www.finops.org/framework/phases/", "https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html", "https://cloud.google.com/billing/docs/how-to/budgets", "https://www.brendangregg.com/usemethod.html"]
---
# Capacity planning and cost monitoring

Capacity planning answers "will it hold at the next peak, and what does that cost?" Do it with measurements, not guesses, and revisit it when traffic or architecture changes. Cost design (tiers, managed vs self-run, unit cost) lives in `architecture/cost`; this ref is about operating against limits and watching the bill.

## Decision guide

**1. Know your limits before users find them.**
- Find the first bottleneck with the USE method: for each resource (CPU, memory, DB connections, worker pool, queue, third-party rate limit) record utilization, saturation (waiting work) and errors.
- Measure capacity with a load test against staging (`testing/performance-k6`): the request rate where p95 latency or error ratio breaks the SLO. That number, not the instance size, is your capacity.
- Write it down per service: "holds N req/s at p95 < 500 ms on 2 instances; first limit = DB pool of 20". Re-measure after big changes.

**2. Plan for the peak, not the average.** Peaks: month-end salary days and mobile-money payday traffic, campaigns, school terms, public holidays, a viral post. Keep headroom so the busiest expected hour stays well under measured capacity, and so you can lose one instance or zone and still serve. Use your own history (requests per minute by hour and weekday) to forecast.

**3. Limits you set yourself.**
- Connection pools sized from the database's `max_connections` across all instances (and PgBouncer if used, `data/postgres-operations`).
- Autoscaling min/max: a minimum that covers the base load plus one failure, a maximum that your database and budget can survive. Autoscaling more app instances against a saturated database makes things worse.
- Timeouts and concurrency limits on every outbound call; queue length limits with a visible rejection.

**4. Overload: degrade, shed, do not collapse** (SRE book, Handling Overload; Workbook, Managing Load).
- Serve degraded responses (cached or partial data) when expensive work is overloaded.
- Shed load early with a clear error (429/503 with `Retry-After`) rather than letting every request time out.
- Retries count as new load: cap them, use backoff with jitter, and use retry budgets (`architecture/resilience`). Clients that retry instantly turn a blip into an outage.
- Prioritise: payments and sign-in before reports and exports.

**5. Cost monitoring from day one.** Cost problems are reliability problems with a delay.
- Turn on budgets with alerts in every cloud account: AWS Budgets and Google Cloud budgets both alert on actual and forecasted spend thresholds.
- Budgets alert; most do not stop spending. Google states that an alerts-only budget does not cap usage or spending; AWS notes billing data lags usage (updated up to three times a day), so you may overshoot before the alert arrives. Put hard limits where the provider offers them (spend caps, quotas, max instances) on anything that can scale without bound, especially paid AI/LLM APIs and egress.
- Tag or label every resource with service, environment and owner so the bill can be split. Untagged spend is a weekly review item.
- Watch unit cost (cost per active user, per 1,000 requests, per payment) next to the bill (`architecture/cost`). A flat bill with rising unit cost is a warning.
- Clean up: preview environments on merge, old snapshots and images by lifecycle rules, idle databases, unattached disks and IPs.

**6. FinOps in one paragraph.** The FinOps Foundation describes three repeating phases: **Inform** (see and allocate costs), **Optimize** (remove waste first, then buy commitments for the steady baseline), **Operate** (budgets, reviews, ownership as routine). For one developer this is: tags + budgets + a 15-minute monthly bill review + a written reason for every new always-on component.

**7. Prices are not in this ref on purpose.** Never quote a price from memory; read the provider's pricing page and record the date, or write "unknown".

## Anti-patterns
- Capacity numbers from instance sizes instead of load tests; planning for average traffic.
- Unlimited autoscaling in front of a fixed-size database; unbounded retries.
- No budget alerts until the first surprise bill; believing a budget alert is a spending cap.
- Untagged resources; previews and test clusters left running for months.
- Quoting prices or savings without a dated source.

## Checks
- `eos scaffold load-k6`: smoke and load scripts with thresholds (manual or weekly, never per PR).
- Monthly (manual): bill review by tag, budget thresholds still sensible, unit cost trend, orphaned resources.
- Review: new always-on component has a cost note in an ADR; outbound calls have timeouts and retry caps.

## Sources
- Google SRE book, Handling Overload: https://sre.google/sre-book/handling-overload/ · Workbook, Managing Load: https://sre.google/workbook/managing-load/
- FinOps Foundation, Phases (CC BY 4.0): https://www.finops.org/framework/phases/
- AWS Budgets: https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html
- Google Cloud, Create, edit, or delete budgets and budget alerts: https://cloud.google.com/billing/docs/how-to/budgets
- Brendan Gregg, The USE Method: https://www.brendangregg.com/usemethod.html
