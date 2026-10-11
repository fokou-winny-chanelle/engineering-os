---
id: architecture/scaling-stages
title: Scaling stages from 1k users to millions (and when not to)
area: architecture
read_when: planning for growth, someone proposes microservices/Kafka/sharding/multi-region, or a capacity limit is approaching
verified: 2026-10-10
revisit_days: 365
sources: ["https://martinfowler.com/bliki/MonolithFirst.html", "https://nickcraver.com/blog/2016/02/17/stack-overflow-the-architecture-2016-edition/", "https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/", "https://www.notion.com/blog/sharding-postgres-at-notion", "https://github.blog/engineering/infrastructure/partitioning-githubs-relational-databases-scale/", "https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity", "https://github.com/donnemartin/system-design-primer"]
---
# Scaling stages from 1k users to millions

User counts are a poor proxy: 10k users of a video product load a system more than 1M users of a monthly invoicing tool. Scale by measured limits (CPU, connections, p95, queue lag, storage growth, team contention) and by the capacity model in the performance-scale pack. The stages below are typical triggers, not a schedule. Skipping ahead costs money and speed every day until you actually need it.

## Decision guide

**Stage 0: proving the product (up to a few thousand users).**
- One deployable (modular monolith), one managed Postgres with automated backups and point-in-time recovery, object storage for files, a managed host (PaaS / containers), CDN for static assets.
- Background jobs in a DB-backed or Redis-backed queue. Error tracking, structured logs, uptime check.
- Do now (cheap, hard to retrofit): module boundaries, idempotency keys on payments, UUID/ULID ids if you might shard, tenant id on every multi-tenant table, timeouts on outbound calls, cursor pagination.
- Do not: microservices, Kafka, Kubernetes you operate yourself, multi-region, sharding, a separate search cluster.

**Stage 1: real traction (tens of thousands of users).** Triggers: p95 creeping up, DB CPU high at peak (set the threshold from your baseline), noisy jobs hurting web latency.
- Fix the top queries (`pg_stat_statements`), add indexes, connection pooling.
- Run 2+ app instances behind a load balancer (stateless app; sessions in DB/Redis or signed cookies).
- Separate worker processes from web; CDN caching for public pages; Redis for hot reads and rate limits.
- SLOs and burn-rate alerts; load test before launches.

**Stage 2: growth (hundreds of thousands of users).** Triggers: DB is the bottleneck after query work; read traffic dominates; reporting hurts production.
- Bigger DB instance first, then read replicas for lag-tolerant reads; analytics moves to a warehouse via CDC/batch.
- Partition the biggest append-only tables by time.
- Search moves to a dedicated engine if Postgres FTS no longer meets the SLO.
- Team contention appears: enforce module ownership (CODEOWNERS, boundary lint); consider extracting the first service only for a module with a clearly different scaling or ownership profile.

**Stage 3: large scale (millions of users).** Triggers: write throughput or data size exceeds one primary even after vertical splits; several teams blocked on one deploy pipeline.
- Vertical split of table groups into separate databases, then horizontal sharding on tenant/user key (Figma did vertical partitioning first; Notion sharded to 480 logical shards on 32 databases; GitHub moved table groups off its main cluster).
- Services for parts with distinct scaling or team ownership, with events through outboxes.
- Multi-region only for a stated need: latency to far-away users, regulatory residency, or an availability target one region cannot meet.

**Reality check: a monolith can go far.** Stack Overflow's 2016 write-up describes about 209 million HTTP requests per day served by 11 IIS web servers, 4 SQL Servers and 2 Redis servers, where a single multi-tenant application serves all the Q&A sites. Shopify kept one codebase and invested in a modular monolith. Scale is mostly about efficient queries, caching and good operations, not the number of services.

**Before adopting any big-step technology, answer in an ADR:**
1. What measured limit do we hit, and when (capacity model with growth rate)?
2. What cheaper step was tried or ruled out, with numbers?
3. What does it cost per month (cite pricing) and in people (on-call, expertise)?
4. How do we roll back?

| Proposal | Usually premature until | Cheaper step first |
|---|---|---|
| Microservices | several teams contend on one deployable, or a module has a very different scaling/compliance profile | modular monolith + boundary lint |
| Kafka | replay, many consumer groups, or sustained high event throughput are needed | DB queue / managed queue |
| Kubernetes (self-run) | many services with a platform team | PaaS / managed containers |
| Sharding | one primary can't hold writes or data after scale-up, partitioning and vertical splits | indexes, pooling, bigger box, partitions |
| Multi-region active-active | a stated latency/residency/availability need | multi-zone + tested restore + CDN |
| Separate read DB tech (CQRS everywhere) | specific screens need it | a read model for those screens |

## Examples

- **B2B SaaS at 300 customers proposing microservices "for scale":** capacity model shows 15 RPS peak; DB CPU 12%. Decision: stay modular monolith, add boundary lint, revisit when a second team forms.
- **Consumer app after a TV mention:** spike test reveals connection exhaustion at 4× normal load; fix with a pooler and CDN caching of the landing page; no architecture change.

## Anti-patterns

- Designing for "millions of users" before the first thousand ("resume-driven architecture").
- Scaling the app tier when the database is the bottleneck.
- Multi-region without tested failover (two regions, one untested runbook).
- Rewriting into services to fix code quality.
- Ignoring the cheap, hard-to-retrofit decisions at stage 0 (ids, tenant keys, idempotency).

## Checks

- Capacity model in `docs/ops/` updated each quarter or before a launch; the ADR for any stage-3 step cites it.
- Load test results show where the system breaks (target ≥ 2× expected peak).
- Dashboard of the leading indicators: DB CPU and connections, p95 per key journey, queue lag, storage growth.

## Sources

- Martin Fowler, Monolith First: https://martinfowler.com/bliki/MonolithFirst.html
- Nick Craver, Stack Overflow: The Architecture (2016 edition): https://nickcraver.com/blog/2016/02/17/stack-overflow-the-architecture-2016-edition/
- Figma, How Figma's databases team lived to tell the scale: https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/
- Notion, Herding elephants: sharding Postgres at Notion: https://www.notion.com/blog/sharding-postgres-at-notion
- GitHub, Partitioning GitHub's relational databases to handle scale: https://github.blog/engineering/infrastructure/partitioning-githubs-relational-databases-scale/
- Shopify Engineering, Deconstructing the monolith: https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity
- System Design Primer: https://github.com/donnemartin/system-design-primer
