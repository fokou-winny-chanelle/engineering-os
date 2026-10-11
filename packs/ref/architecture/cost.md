---
id: architecture/cost
title: Cost as an architecture attribute
area: architecture
read_when: estimating infra cost, adding a tier (replica, cache, queue, region), choosing managed vs self-run, or reviewing a cloud bill
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html", "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/design-principles.html", "https://www.finops.org/framework/", "https://www.finops.org/framework/phases/", "https://world.hey.com/dhh/we-stand-to-save-7m-over-five-years-from-our-cloud-exit-53996caa"]
---
# Cost as an architecture attribute

Cost is a quality attribute with a number, ranked like the others (`architecture/quality-attributes`). The big cost decisions are architectural: how many always-on components you run, where data moves, and how much people time the system needs to operate. Never invent prices: cite the provider's pricing page with the date you read it, or write "unknown".

## Decision guide

**1. Estimate before you build** (back-of-envelope, per environment):
- list each component (app instances, DB, replicas, cache, queue, storage, CDN, logs/metrics, third-party APIs);
- for each, the pricing dimension (hours, vCPU/GB, requests, GB stored, GB transferred, per seat) and your expected quantity from the capacity model;
- multiply with the cited unit price, and add an explicit contingency line marked as an assumption;
- write it in the ADR or `docs/architecture/overview.md` with the date and links.

**2. Track unit cost, not just the bill.** Cost per active user, per order, per 1k requests, per tenant. AWS's cost pillar calls this measuring overall efficiency: business output against the cost of delivering it. A rising bill with falling unit cost is growth; a flat bill with rising unit cost is a problem. FinOps Foundation frames the practice as three repeating phases: Inform (visibility, allocation), Optimize (rates and usage), Operate (continuous governance).

**3. Know the usual cost drivers** (check your provider's pricing for each):
- **Always-on capacity:** idle instances, oversized DBs, replicas nobody reads from, non-production environments running all week. AWS's example: dev/test used 40 of 168 hours a week can save about 75% by stopping outside working hours.
- **Data transfer:** internet egress, cross-zone and cross-region traffic, NAT and load balancer processing. Chatty services across zones and multi-region replication show up here.
- **Observability:** log ingestion and retention, high-cardinality metrics, trace volume. Sample traces, drop debug logs in production, set retention per data class.
- **Managed service premiums vs people:** managed DB/queue/search costs more per unit than self-run, but self-run costs on-call, upgrades, backups and expertise. For small teams the managed option is usually cheaper in total.
- **Per-request and per-seat SaaS:** auth, email/SMS, monitoring, AI APIs scale with users; model them per active user.
- **Storage growth:** logs, events and media grow forever unless you set lifecycle rules (tier to cold storage, expire).

**4. Every new tier pays for itself in an ADR.** Replica, cache cluster, queue, search cluster, second region: write the monthly cost (cited), the operational cost (who runs it), and the measured problem it solves. "Might need it" is not a reason.

**5. Rate optimisation after usage optimisation.** First remove waste (rightsize, stop idle, delete orphans, lifecycle rules), then commit (reserved capacity / savings plans / committed-use discounts) for the steady baseline only. Spot/preemptible capacity for interruptible batch work.

**6. Revisit the hosting model when the load is stable and large.** 37signals reported spending $3.2m on cloud in 2022 and estimated saving about $7m over five years by moving stable workloads to their own hardware without growing the ops team. That fits steady, predictable load and an experienced ops team; it is not evidence for a small or spiky product. Run the comparison with your own numbers, including people.

**7. Design patterns that save money:** static generation + CDN for public content; scale-to-zero for spiky low-traffic services; queues to smooth peaks instead of provisioning for them; batch over per-item calls to paid APIs; caching responses of expensive third-party APIs (within their terms); keeping services in the same zone/region as their database.

## Examples

- **Early SaaS estimate:** one PaaS app (2 instances), managed Postgres with PITR, object storage, CDN, error tracking, email API. Each line with the pricing link and date; total plus "unknown" for the email volume until the beta measures it.
- **Bill review:** log ingestion is the second-largest line; set production log level to INFO, sample traces at 10%, 14-day retention for debug data, 1 year for audit logs in cold storage.
- **Replica proposal:** the read replica would cost as much as the primary; `pg_stat_statements` shows two report queries cause the load; moving them to a nightly summary table removes the need.

## Anti-patterns

- Prices typed from memory into a design doc; estimates without a date.
- Multi-region or Kubernetes "for the future" with no stated need.
- Non-production environments identical to production and running 24/7.
- Unlimited log retention; debug logging in production.
- Committing to reserved capacity before rightsizing.
- Choosing self-hosting to save money without counting on-call and upgrade time.

## Checks

- Cost-allocation tags/labels on every resource (service, environment, owner); untagged resources reported weekly.
- Budget alerts per environment at 50/80/100% of the monthly budget.
- Unit-cost metric (cost per active user or per 1k requests) on the main dashboard next to latency and errors.
- ADRs that add a tier include a "Cost" section with cited prices.

## Sources

- AWS Well-Architected, Cost Optimization Pillar: https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html
- AWS Well-Architected, Cost Optimization design principles: https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/design-principles.html
- FinOps Foundation, FinOps Framework: https://www.finops.org/framework/
- FinOps Foundation, FinOps Phases: https://www.finops.org/framework/phases/
- David Heinemeier Hansson (37signals), We stand to save $7m over five years from our cloud exit: https://world.hey.com/dhh/we-stand-to-save-7m-over-five-years-from-our-cloud-exit-53996caa
