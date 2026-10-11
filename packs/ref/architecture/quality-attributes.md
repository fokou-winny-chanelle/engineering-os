---
id: architecture/quality-attributes
title: Quality attributes and trade-offs
area: architecture
read_when: starting a design, writing the NFR table or overview, or comparing two options
verified: 2026-10-10
revisit_days: 365
sources: ["https://iso25000.com/index.php/en/iso-25000-standards/iso-25010", "https://quality.arc42.org/", "https://www.sei.cmu.edu/library/the-architecture-tradeoff-analysis-method/", "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html", "https://sre.google/sre-book/service-level-objectives/"]
---
# Quality attributes and trade-offs

Architecture is the set of choices that are expensive to change. You make them for quality attributes (how well the system does its job), not for features. The ISO/IEC 25010 product-quality model gives a shared vocabulary of nine characteristics (2023 revision): functional suitability, performance efficiency, compatibility, interaction capability (was usability), reliability, security, maintainability, flexibility (was portability) and safety. arc42's quality model adds concrete example requirements for each.

## Decision guide

**1. Write scenarios, not adjectives.** "Fast" and "scalable" cannot be tested. Use SEI's quality-attribute scenario (the input to an ATAM review): source, stimulus, environment, artifact, response, response measure.

| Attribute | Weak | Testable scenario |
|---|---|---|
| Latency | "fast checkout" | 99% of `POST /checkout` < 800 ms at 50 RPS, measured over 28 days |
| Availability | "always up" | 99.9% of minutes serve the home page; a zone loss recovers in < 5 min |
| Durability | "no data loss" | RPO ≤ 5 min, RTO ≤ 1 h; restore tested every quarter |
| Modifiability | "easy to change" | adding a payment provider touches 1 module and < 10 files |
| Security | "secure" | a stolen session token is useless after 15 min or on logout |
| Cost | "cheap" | infra ≤ a stated share of revenue per active user (fill in yours) |

Turn the latency and availability rows into SLOs (performance-scale pack). The SRE book's rule: pick targets from what users need, not from what the system does today.

**2. Rank them.** Every design has to give something up. Write the order once (e.g. correctness > security > availability > latency > cost > modifiability) so agents and reviewers resolve conflicts the same way. The order changes by product: a payments ledger puts correctness first; a feed puts latency and availability first.

**3. Know the usual tensions** and name the one you are choosing in the ADR:

| Choosing | Usually costs | Example |
|---|---|---|
| Strong consistency | latency and availability during partitions | one primary DB for balances |
| Low latency | freshness, money (caches, replicas, edge) | CDN with stale-while-revalidate |
| High availability | cost, complexity, consistency | multi-zone replicas; multi-region is a further big step |
| Modifiability (more seams) | latency per hop, more moving parts | splitting a module into a service |
| Security controls | usability, latency | step-up auth on payouts only |
| Low cost | headroom, availability | single instance + tested restore |

**4. Find sensitivity and trade-off points.** ATAM names two things worth hunting: a sensitivity point (one decision that strongly moves one attribute, e.g. pool size → latency under load) and a trade-off point (one decision that moves two attributes in opposite directions, e.g. cache TTL → latency up, freshness down). List them in the overview; they are where reviews should look.

**5. Use the cheapest analysis that settles it.** A back-of-envelope number (capacity model, Little's law) or a 1-day spike beats a week of debate. Run a load test only when the number is close to the limit.

**6. Check the pillars when the system runs in a cloud.** AWS Well-Architected (and Azure's) group the same concerns into pillars: operational excellence, security, reliability, performance efficiency, cost optimisation, sustainability. Use their question lists as a review checklist, not as a design method.

## Examples

- **Small B2B SaaS, 200 customers.** Rank: correctness > security > modifiability > availability (99.5%) > latency > cost. Result: modular monolith, one Postgres with daily backups plus point-in-time recovery, no cache yet.
- **Mobile money top-up.** Rank: correctness > availability > security > latency. Result: idempotency keys on every write, append-only ledger, outbox to the notification service, and a "pending" state the UI shows when a provider is slow.
- **Content site with spikes.** Rank: availability > latency > cost. Result: static pages at the CDN with `stale-if-error`, origin sized for cache misses only.

## Anti-patterns

- An NFR table with no numbers, or numbers nobody measures.
- "Five nines" without the budget, on-call and multi-region design it needs. Each extra nine costs a step change in effort.
- Optimising an attribute nobody ranked (e.g. building for millions of users before the first 100).
- Hiding a trade-off: the ADR lists only the upside of the chosen option.
- Treating all data the same: profile pictures and ledger entries need different durability and consistency.

## Checks

- `docs/architecture/overview.md` has a "Quality attributes" table (attribute, scenario, measure, design answer) and a "Failure modes" table; `eos next` checks both are filled.
- Every ADR names the attribute it serves and the one it costs.
- Latency and availability rows have an SLO and a dashboard (operations pack).

## Sources

- ISO/IEC 25010 product quality model: https://iso25000.com/index.php/en/iso-25000-standards/iso-25010
- arc42 quality model (examples per attribute): https://quality.arc42.org/
- SEI, Architecture Tradeoff Analysis Method: https://www.sei.cmu.edu/library/the-architecture-tradeoff-analysis-method/
- AWS Well-Architected Framework: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
- Google SRE book, Service Level Objectives: https://sre.google/sre-book/service-level-objectives/
