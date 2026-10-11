---
id: architecture/service-communication
title: Service decomposition and inter-service communication
area: architecture
read_when: splitting out a service, choosing sync vs async calls, designing a cross-service workflow, or publishing events from a DB write
verified: 2026-10-10
revisit_days: 365
sources: ["https://martinfowler.com/bliki/MicroservicePrerequisites.html", "https://martinfowler.com/articles/microservice-trade-offs.html", "https://microservices.io/patterns/data/saga.html", "https://microservices.io/patterns/data/transactional-outbox.html", "https://learn.microsoft.com/en-us/azure/architecture/patterns/saga", "https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html", "https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html", "https://docs.pact.io/", "https://grpc.io/docs/guides/deadlines/"]
---
# Service decomposition and inter-service communication

A service boundary is a network boundary: every call can be slow, fail, or succeed without you hearing back. Pay that cost only for a reason you can name (see `architecture/modular-monolith` for the reasons). Fowler's prerequisites before the first service: rapid provisioning, basic monitoring that spots problems fast, and rapid application deployment. His trade-off summary: you gain strong module boundaries, independent deployment and technology diversity; you pay with distribution, eventual consistency and operational complexity.

## Decision guide

**Decompose by business capability**, one owner per service, its own data store. Size: a service one team can own end to end. If two services always change together, or one cannot answer a request without the other's database, merge them back.

**Choose the call style per interaction:**

| Need | Use | Why |
|---|---|---|
| Caller needs the answer now to respond to a user (price, auth check) | sync request/response (HTTP+JSON, gRPC) | simple; but caller availability = product of both |
| Tell others something happened; they react in their own time | async event (broker, at-least-once) | decouples availability and load |
| Ask another service to do work later, maybe slowly | async command on a queue | load levelling, retries, DLQ |
| Bulk data for analytics | CDC / batch export to the warehouse | keeps OLTP services out of reporting |

Chains of sync calls multiply failure: three services each at 99.9% in series give at most about 99.7% for the whole call. Keep sync chains short (≤ 2 hops on a user request) and push the rest to events.

**Every sync call has:** a deadline that propagates (gRPC deadlines; an absolute time budget in a header for HTTP), retries only for idempotent operations with backoff and jitter, an idempotency key on writes, and a defined user-visible failure (see `architecture/resilience`).

**Contracts are the only coupling.** OpenAPI (HTTP), protobuf (gRPC), AsyncAPI (events). Change additively; break only with a new version that runs side by side. Between teams, consumer-driven contract tests (Pact) prove a provider change won't break known consumers before it deploys.

**Writing to your DB and publishing an event: use a transactional outbox.** Dual writes (commit DB, then publish) lose or invent events when the second step fails.
1. In the same transaction as the business change, insert a row into `outbox(id, aggregate_id, type, payload, created_at)`.
2. A relay publishes unsent rows and marks them sent, either by polling (`SELECT … FOR UPDATE SKIP LOCKED` in batches) or by change data capture (Debezium's outbox event router reads the table from the DB log).
3. Delivery is at-least-once, so every consumer is idempotent: store processed message ids (an "inbox" table) or make the effect naturally idempotent (upsert by key).
4. Order matters only per aggregate: partition or key messages by `aggregate_id`.

**Workflows across services: sagas, not distributed transactions.** A saga is a sequence of local transactions; when a step fails, earlier steps are undone by compensating actions.
- **Choreography** (each service reacts to events): fine for 2–3 steps with one team. Hard to see the whole flow beyond that.
- **Orchestration** (one coordinator tells each service what to do and records state): better for 4+ steps, money, or when you need to answer "where is order 123?". A durable workflow engine or a state table in the orchestrating service both work.
- Design compensations up front ("void authorisation", "release stock"). Order the steps: compensable steps first, then the pivot (the point of no return, e.g. capture payment), then steps that are retried until they succeed (send receipt). Steps that cannot be undone never go before the pivot.
- Sagas give no isolation: other requests can see intermediate states. Use semantic locks (status `PENDING`), commutative updates, or re-read before acting.

## Examples

- **Order placement (orchestrated):** `orders` creates order `PENDING` + outbox `OrderCreated` → `payments` authorises (idempotency key = order id) → `inventory` reserves → orders marks `CONFIRMED`. Reservation fails → payments voids the authorisation → order `REJECTED`, user sees "out of stock, you were not charged".
- **Sign-up side effects (choreographed):** `identity` emits `UserRegistered` through its outbox; `email` and `analytics` consume it independently. A broken analytics consumer never blocks sign-up.
- **Price lookup:** checkout needs the price now → sync gRPC with a 200 ms deadline, cached catalogue fallback for display only, never for charging.

## Anti-patterns

- Two-phase commit / XA across services or brokers (blocks on the coordinator; most managed brokers don't support it).
- Publishing events from inside the DB transaction (rollback leaves a published lie) or after it without an outbox (crash loses it).
- Shared database between services; "temporary" cross-service reads of another service's tables.
- Entity services (`customer-service`, `address-service`) that only do CRUD: every feature becomes a distributed transaction.
- Synchronous fan-out on the user path to 5+ services.
- Events that carry only an id, forcing every consumer to call back the producer (load + coupling); include the fields consumers need, versioned.

## Checks

- Contract breaking-change check per provider in CI (oasdiff, `buf breaking`); Pact verification in the provider pipeline where teams differ.
- A test that kills the relay or broker mid-flow and proves no event is lost and none is applied twice (consumer dedupe).
- Every outbound client has a timeout configured (Python: ruff `S113` is in the stack pack's `S` rules; review TS `fetch` calls for `AbortSignal.timeout`).
- ADR for each new service names the reason, the owner and the data it owns.

## Sources

- Martin Fowler, Microservice Prerequisites: https://martinfowler.com/bliki/MicroservicePrerequisites.html
- Martin Fowler, Microservice Trade-Offs: https://martinfowler.com/articles/microservice-trade-offs.html
- microservices.io, Saga pattern: https://microservices.io/patterns/data/saga.html
- microservices.io, Transactional outbox: https://microservices.io/patterns/data/transactional-outbox.html
- Azure Architecture Center, Saga pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/saga
- AWS Prescriptive Guidance, Transactional outbox: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- Debezium, Outbox event router: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html
- Pact documentation: https://docs.pact.io/
- gRPC, Deadlines: https://grpc.io/docs/guides/deadlines/
