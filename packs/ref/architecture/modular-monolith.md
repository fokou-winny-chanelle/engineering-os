---
id: architecture/modular-monolith
title: Modular monolith and module boundaries
area: architecture
read_when: drawing module boundaries, adding a module, or deciding whether to extract a service
verified: 2026-10-10
revisit_days: 365
sources: ["https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity", "https://martinfowler.com/bliki/MonolithFirst.html", "https://import-linter.readthedocs.io/en/stable/", "https://github.com/sverweij/dependency-cruiser", "https://docs.spring.io/spring-modulith/reference/", "https://github.com/Shopify/packwerk", "https://github.com/kgrzybek/modular-monolith-with-ddd"]
---
# Modular monolith and module boundaries

One deployable, many modules, each owning its data and exposing a small public API. You get most of the team-scaling benefit of services without network calls, distributed transactions or a platform team. Shopify chose this path for its large Rails codebase ("keep all of the code in one codebase, but ensure that boundaries were defined and respected"). Martin Fowler's Monolith First note: almost all successful microservice stories he heard started as a monolith that got too big; almost all built as microservices from scratch ended in serious trouble. Layout and tool configs are in `.eos/packs/ref/topologies.md`; this file is about where to cut and how to keep the cuts.

## Decision guide

**Where to draw a boundary.** Cut along business capabilities, not technical layers. Good signals that code belongs in one module:
- it changes together (look at `git log` co-change for the last 6 months);
- it shares invariants that must hold in one transaction (an order and its lines);
- one person or team would own it and answer for it;
- it has its own vocabulary (in "billing" an account is a payer; in "identity" it is a login).

Bad cuts: `controllers/`, `services/`, `repositories/` as top-level modules (every feature touches all of them); one module per database table; a `common`/`shared` module that grows forever.

**Size.** Start with 3–8 modules for a typical product. Too many tiny modules turn every feature into a cross-module change; too few leave a monolith with folders.

**What a module exposes.**
- A public API: functions or a facade (`billing/api.py`, `billing/index.ts`), plain data types (DTOs) in and out. Never its ORM models.
- Domain events for side effects others care about (`InvoicePaid`), published in-process (and through an outbox when they leave the process).
- Nothing else. Internals are private by rule, checked in CI.

**Data ownership.** Each module owns its tables (a schema or a table prefix). Other modules never query or join them. Need data from another module? Call its API, or keep a local read copy updated by its events. Reporting that needs joins across modules goes to a read model or the warehouse, not to cross-module SQL.

**Transactions.** Inside one module: a normal DB transaction. Across modules in the same process: you can still share one transaction while you are a monolith, but design as if you couldn't (events after commit), so extraction stays possible.

**Dependency direction.** Allowed graph is a DAG written down in `docs/architecture/modules.md`. Lower-level modules (identity, catalog) never import higher ones (checkout). Break a cycle by moving the shared concept down, by inverting with an interface the lower module owns, or by switching to an event.

**When to extract a module into a service** (needs an ADR; see `architecture/service-communication`):
- it must scale or deploy on a very different profile (GPU work, a hot path at 100× the rest);
- a separate team needs its own release cadence and on-call;
- a compliance or fault-isolation boundary (card data, untrusted code);
- it already has a clean API, its own tables and events, and no shared transaction. If not, fix that inside the monolith first.

Not reasons: "microservices are modern", a slow build (fix the build), or a messy module (a network boundary makes mess more expensive, not less).

## Examples

- **Python (FastAPI):** `app/modules/{identity,catalog,orders,billing}/` each with `api.py`, `models.py` (private), `events.py`. import-linter `independence` contract over `app.modules.*` with `ignore_imports` for each `*.api`; `broken_contract_guidance` prints "import app.modules.billing.api, not billing.models".
- **TypeScript:** dependency-cruiser rule "no import of `src/modules/(x)/**` from outside `src/modules/$1/` except `index.ts`"; `depcruise-baseline` records today's violations so only new ones fail.
- **JVM:** Spring Modulith verifies that modules only use each other's API packages and can generate module documentation. **Ruby:** Packwerk's privacy and dependency checks.
- **Reference implementation:** kgrzybek/modular-monolith-with-ddd (C#) shows modules with their own database schemas, integration through an events bus (no direct calls), and the outbox/inbox pattern.

## Anti-patterns

- **Distributed monolith:** services that must deploy together or share a database. You pay network costs and keep the coupling.
- **Shared domain model library** used by every module: any change ripples everywhere.
- **Cross-module joins "just for this report".** They become the hidden contract that blocks every schema change.
- **Boundaries only in a diagram.** Without a CI check, agents and people take the shortest import path.
- **One giant `events` module** that everything imports: put event types in the publishing module's API.
- **Generic CRUD module APIs** (`get_entity(id)`): expose business operations (`issue_refund(order_id, amount)`).

## Checks

- Boundary lint in CI and pre-commit (import-linter / dependency-cruiser / ArchUnit / Spring Modulith / Packwerk); `eos scaffold boundaries` writes the config; new violations fail, old ones sit in a baseline that only shrinks (`eos ratchet`).
- `docs/architecture/modules.md` lists each module, owner, public API, tables and allowed dependencies; CODEOWNERS matches it.
- A grep check in review: no SQL or ORM query touches another module's tables.

## Sources

- Shopify Engineering, Deconstructing the monolith: https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity
- Martin Fowler, Monolith First: https://martinfowler.com/bliki/MonolithFirst.html
- import-linter documentation: https://import-linter.readthedocs.io/en/stable/
- dependency-cruiser: https://github.com/sverweij/dependency-cruiser
- Spring Modulith reference: https://docs.spring.io/spring-modulith/reference/
- Packwerk: https://github.com/Shopify/packwerk
- modular-monolith-with-ddd: https://github.com/kgrzybek/modular-monolith-with-ddd
