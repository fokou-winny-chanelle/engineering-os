---
id: architecture/event-driven
title: Event-driven design and queues
area: architecture
read_when: adding a queue, background jobs, events between modules or services, a broker (Kafka, RabbitMQ, SQS, Pub/Sub), or a consumer
verified: 2026-10-10
revisit_days: 365
sources: ["https://martinfowler.com/articles/201701-event-driven.html", "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html", "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html", "https://www.rabbitmq.com/docs/reliability", "https://kafka.apache.org/documentation/", "https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling", "https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers", "https://www.postgresql.org/docs/current/sql-select.html", "https://cloudevents.io/", "https://www.asyncapi.com/"]
---
# Event-driven design and queues

Queues and events decouple *when* and *whether* work happens from the request that caused it. You gain load levelling, retries and independent consumers; you pay with eventual consistency, duplicates, ordering questions and harder debugging. Martin Fowler separates four things people call "event-driven": event notification, event-carried state transfer, event sourcing and CQRS. Say which one you mean.

## Decision guide

**Which mechanism:**

| Need | Use |
|---|---|
| Background jobs in one app (emails, exports), modest volume | a job queue on what you have: Postgres table with `FOR UPDATE SKIP LOCKED` (Postgres docs: suited to queue-like tables), or Redis-backed (Sidekiq, BullMQ, RQ, Celery) |
| Commands to another service, per-message retries, DLQ | a queue (SQS, RabbitMQ quorum queues, Cloud Tasks) |
| Facts many consumers read independently, replay, ordering per key, high throughput | a log (Kafka, Redpanda, Kinesis, Pub/Sub with ordering keys) |
| Long multi-step business process with timers and compensation | a workflow engine or an orchestrating saga (`architecture/service-communication`) |

Start with the database-backed queue or the managed queue you already run. A log platform like Kafka is worth its operational cost when you need replay, many independent consumer groups, or sustained high throughput.

**Delivery semantics.** Assume at-least-once everywhere. "Exactly-once" exists only inside specific boundaries (e.g. Kafka idempotent producers and transactions within Kafka); the effect on your database still needs idempotency. So:
- every consumer is idempotent: dedupe by message id in an inbox table written in the same transaction as the effect, or make the effect an upsert keyed by a business id;
- producers publish through an outbox when the event comes from a DB change;
- RabbitMQ: use publisher confirms and manual consumer acks; ack only after the effect commits.

**Retries and poison messages.**
- Retry with exponential backoff and jitter; cap attempts.
- After N failures move the message to a dead-letter queue (SQS: a redrive policy with `maxReceiveCount`; AWS warns that too low a value sends messages to the DLQ after one transient failure).
- Alert on DLQ depth > 0 for important queues, and have a redrive procedure (fix, then replay).
- SQS visibility timeout must exceed your processing time; extend it for long jobs (`ChangeMessageVisibility`); the hard maximum is 12 hours from first receipt. Longer work belongs in a workflow engine or smaller steps.

**Ordering.** Global order kills throughput. Get order per entity: Kafka partitions by key (`order_id`), SQS FIFO message groups, Pub/Sub ordering keys. Consumers must still tolerate out-of-order arrival across entities and replays: carry a version or timestamp and ignore older updates.

**Back-pressure and load levelling.** A queue absorbs spikes so a slow dependency can work at its own rate (Azure: queue-based load levelling). But a queue that only grows is an outage in slow motion: alert on age of oldest message (lag), not just depth; bound queue size or rate-limit producers; scale consumers on lag (competing consumers), up to what the downstream (often the DB) can take.

**Event design.**
- Name events as past-tense facts in the domain: `InvoicePaid`, not `UpdateInvoice`.
- Envelope: id, type, source, time, subject/aggregate id, schema version, correlation/trace id. CloudEvents standardises these attributes; AsyncAPI documents channels and payloads like OpenAPI does for HTTP.
- Payload: notification (id only, consumers call back) vs event-carried state (the fields consumers need). Prefer the second for cross-service events to avoid callback storms; keep PII minimal.
- Schemas evolve additively (new optional fields); breaking changes = new event type or version, both published during migration.

**Observability.** Propagate trace context through message headers; log message id, type and attempt; dashboards per queue: rate in/out, lag, DLQ depth, processing time.

## Examples

- **PDF invoice generation:** API writes `invoice` + outbox `InvoiceIssued` → relay → `pdf-jobs` queue → worker renders and stores in object storage, marks done (idempotent by invoice id). Five failures → DLQ + alert; the invoice page shows "PDF being prepared".
- **Postgres job table:** `SELECT id, payload FROM jobs WHERE status='ready' AND run_at <= now() ORDER BY run_at LIMIT 10 FOR UPDATE SKIP LOCKED`, process, update status, commit. Partial index on `(run_at) WHERE status='ready'`.
- **Inventory updates to search:** Kafka topic keyed by `product_id`; the search indexer consumer group upserts by id with a version check, so replays are harmless.

## Anti-patterns

- Publishing to the broker inside or after the DB transaction without an outbox.
- Non-idempotent consumers; acking before the work commits.
- Infinite retries with no DLQ; a DLQ nobody watches.
- One topic or queue for everything; or requiring global ordering.
- Using events for request/response where the caller waits for the answer anyway (an RPC with extra steps).
- Choreographing a 7-step money flow across 5 services with no owner of the overall state.
- Kafka as the first queue for a small app.

## Checks

- Contract: AsyncAPI (or schema registry) for every cross-service event, with a compatibility check in CI.
- A consumer test that delivers the same message twice and out of order; assert one effect and the latest state wins.
- Alerts: oldest-message age, DLQ depth, consumer error rate.

## Sources

- Martin Fowler, What do you mean by "Event-Driven"?: https://martinfowler.com/articles/201701-event-driven.html
- Amazon SQS, Visibility timeout: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- Amazon SQS, Dead-letter queues: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
- RabbitMQ, Reliability guide: https://www.rabbitmq.com/docs/reliability
- Apache Kafka documentation (delivery semantics): https://kafka.apache.org/documentation/
- Azure Architecture Center, Queue-Based Load Leveling: https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling
- Azure Architecture Center, Competing Consumers: https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers
- PostgreSQL, SELECT (FOR UPDATE SKIP LOCKED): https://www.postgresql.org/docs/current/sql-select.html
- CloudEvents: https://cloudevents.io/
- AsyncAPI: https://www.asyncapi.com/
