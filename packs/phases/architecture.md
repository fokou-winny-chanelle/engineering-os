---
id: architecture
title: Architecture & system design
kind: phase
mode: both
when: designing systems, choosing tech, writing ADRs or changing module boundaries
description: Use when changing system architecture, module boundaries, integrations or tech choices, or writing an ADR.
globs: ["docs/architecture/**", "docs/adr/**", "**/ARCHITECTURE.md", "**/*.puml", "**/*.mmd"]
next: [data-modeling, api-design, infra-devops, security]
---
# Architecture & system design

## Entry
Approved requirements with a quantified NFR table, and the UX flows if there is a UI.

## Standards
1. Drive the design from quality attributes. Rank the NFRs (e.g. correctness > security > availability > latency > cost). Each design choice cites the NFR it serves.
2. Start boring. Use a modular monolith, one primary database (PostgreSQL by default) and managed services. Split into services only when you have a named reason: independent scaling, separate team ownership, or a compliance boundary. Write that reason in an ADR.
3. Boundaries. Use modules or bounded contexts with explicit public interfaces. There must be no circular dependencies. Enforce boundaries with a tool (import-linter, dependency-cruiser, ArchUnit, etc. via the stack pack). These are fitness functions: write each failure message as the fix ("move X to Y"), so agents can correct themselves.
4. Failure modes for every external call:
   - timeout and retry with backoff and jitter;
   - idempotency;
   - circuit breaker or fallback;
   - what the user sees when it fails.
   Use an outbox for "DB write + publish" and never rely on dual writes.
5. Data consistency. Name the consistency level per flow (strong or eventual). Money ledgers are append-only, use double-entry where relevant, and never delete or update in place.
6. C4 views (system context and containers, components only when useful) as Mermaid in `docs/architecture/`. Diagrams-as-code live next to the ADRs.
7. ADRs. One decision per file (`docs/adr/NNNN-title.md`) with context, options (≥2), decision, consequences, and a revisit trigger, plus a one-line entry in `docs/adr/INDEX.md`. Accepted ADRs are never rewritten; a new ADR supersedes them.
8. Reversibility. Mark one-way doors (data model, public API, vendor lock-in) and get human review on them; use the decisions pack. Two-way doors can be decided fast.
9. Operability by design. Define health checks, config through env vars, structured logs, traces, feature flags, and a backup/restore plan.
10. Cost. Do a back-of-envelope estimate per environment. Use only sourced prices, or write "unknown".

## Deliverables
- `docs/architecture/overview.md`: context, containers, quality-attribute table, key flows (sequence diagrams for money and auth flows), failure-mode table.
- ADRs for each significant choice. BMAD: `bmad-architecture` (Winston).

## Automated checks
- Architecture-boundary lint configured in CI (stack pack command).
- ADR index check: every ADR file is listed in INDEX.md.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `architecture/quality-attributes` (NFR scenarios, trade-offs) · `architecture/modular-monolith` (where to cut) · `architecture/service-communication` (sync/async, outbox, sagas) · `architecture/data-consistency` (stores, isolation, idempotency) · `architecture/event-driven` (queues) · `architecture/resilience` (failure modes) · `architecture/scaling-stages` (when not to) · `architecture/cost` · `ops/platforms` (PaaS vs Kubernetes) · `ops/africa-connectivity` (regions, residency, weak networks) · `data/multi-tenancy` · `data/nosql-analytics` · `api/grpc-async` (proto, event contracts).

## Exit checklist (Definition of Done)
- [ ] Every NFR has a design answer, and every external dependency has a failure mode.
- [ ] Module boundaries are written and enforced by a tool (or a ticket exists to add one).
- [ ] ADRs exist for the DB, framework, hosting, auth, messaging and any one-way door.
- [ ] Security review of the design (threat model started; see the security pack).
- [ ] Human architect/tech lead approval.

## Handoff → data-modeling, api-design, infra-devops, security
Pass the overview, ADRs and the boundary rules.

## Stop & escalate
Stop when an NFR can't be met within the constraints, or when a choice is a one-way door. Present the options; don't decide alone.
