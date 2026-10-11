---
id: performance-scale
title: Performance, capacity and scaling
kind: phase
mode: intent
when: planning capacity, load testing, fixing slowness, adding caches/queues/replicas/sharding, or setting SLOs
description: Use for slowness, capacity planning, load tests, caching, queues, DB scaling or SLOs.
globs: []
next: [operations, architecture]
---
# Performance, capacity and scaling

## Entry
A measured problem (slow endpoint, rising p95, DB CPU, queue lag), an expected traffic event, or a new product with a scale target in the "Product profile". No measurement yet → measure first.

## Standards
1. **Define "fast enough" before optimising.**
   - Write an SLO per user journey, e.g. "99% of checkout requests < 800 ms over 28 days".
   - Write an error-budget policy: what stops when the budget is spent.
   - Alert on burn rate, not on single spikes. Google's example: page at 2% of budget in 1 h or 5% in 6 h; ticket at 10% in 3 days.
2. **Measure, then change one thing.**
   - Profile or trace the slow path (OpenTelemetry), and look at the query plan (`EXPLAIN ANALYZE`).
   - Fix the biggest cost, re-measure, and keep the before/after numbers in the PR.
3. **Climb the scaling ladder in order.** Stop at the first step that meets the SLO with headroom:
   1. Fix queries: indexes for real filters and sorts, no N+1, pagination by cursor.
   2. Cache: HTTP or CDN for public data; app cache with TTL plus explicit invalidation. Never cache personalised data across users.
   3. Pool connections: one pool per process, limits sized to the DB, PgBouncer-style pooling for many workers.
   4. Move slow work to a queue: idempotent consumers, retries with backoff and jitter, a dead-letter queue, back-pressure (bounded queues, 429 + `Retry-After`).
   5. Read replicas: route only lag-tolerant reads.
   6. Partition: by time for big append-only tables, and by table group (vertical split).
   7. Shard horizontally on a tenant or owner key, once a single node truly can't keep up.
   8. Multi-region: only for a stated latency, availability or residency need.
4. **Don't scale prematurely.** A modular monolith on one well-indexed Postgres plus a cache serves most products for a long time. Microservices, sharding, Kafka and multi-region each need a measured reason, written in an ADR (decisions pack).
5. **Capacity model.**
   - Peak RPS = daily active users × actions per user per day ÷ 86,400 × peak factor (often 3–10×; measure yours).
   - Little's law: concurrent work = arrival rate × time in system. Use it to size pools, workers and queues.
6. **Load test like production.**
   - k6, Locust or Gatling with realistic data and think-times, production-like environment.
   - Run a ramp test, a soak test (hours) and a spike test.
   - Test to 2× the expected peak and record where it breaks.
7. **Protect the system.**
   - Set timeouts on every network call, and use circuit breakers.
   - Rate-limit per user and per key.
   - Use bulkheads (separate pools for critical paths) and graceful degradation (serve stale data, hide non-critical widgets).
8. **Cost is a metric.** Track cost per request or per active user next to latency. Note the cost of every new tier (replica, cache, queue) in the ADR, citing the pricing page.
9. **Clients and low-end devices.**
   - Budget JS size, image weight and API payloads; compress and paginate.
   - Test on a cheap Android phone and a slow (3G-class) network.

## Deliverables
- SLO doc (`docs/ops/slo.md`), before/after measurements, load-test script and results, and an ADR for any step ≥ 5 on the ladder.

## Automated checks
- Cheap budgets in CI (`eos bundle-size`, Lighthouse on key pages, query count per request). Load tests on demand or nightly, not per PR.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `architecture/database-scaling` · `data/postgres-queries` · `data/postgres-indexing` · `architecture/api-performance` · `architecture/caching` · `architecture/resilience` · `architecture/scaling-stages` · `architecture/cost` · `testing/performance-k6` · `frontend/web-vitals-budgets` · `frontend/low-bandwidth`.

## Exit checklist (Definition of Done)
- [ ] The SLO met with headroom, proven by numbers (not "feels faster").
- [ ] Each change justified by a measurement. No ladder step skipped without an ADR.
- [ ] Timeouts, retries (idempotent) and rate limits in place on the touched path.
- [ ] Dashboards and burn-rate alerts updated (operations pack).

## Handoff → operations / architecture
Pass the SLOs, load-test results, the capacity model and the new failure modes to watch.

## Stop & escalate
Stop before sharding, multi-region, changing the primary datastore, or any change that raises monthly cost noticeably. Those are one-way doors and need a human.
