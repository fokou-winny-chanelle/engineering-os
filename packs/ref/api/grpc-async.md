---
id: api/grpc-async
title: Internal and asynchronous APIs - gRPC and Protobuf (deadlines, retries, compatibility, buf breaking), AsyncAPI and CloudEvents event contracts
area: api
read_when: designing service-to-service APIs, choosing gRPC vs REST internally, evolving .proto files, defining event or message contracts for a broker, documenting topics with AsyncAPI
verified: 2026-10-10
revisit_days: 365
sources: ["https://grpc.io/docs/guides/deadlines/", "https://grpc.io/docs/guides/retry/", "https://grpc.io/docs/guides/error/", "https://grpc.io/docs/guides/status-codes/", "https://grpc.io/docs/guides/health-checking/", "https://protobuf.dev/best-practices/dos-donts/", "https://buf.build/docs/breaking/", "https://buf.build/docs/breaking/rules/", "https://www.asyncapi.com/docs/reference/specification/v3.1.0", "https://github.com/cloudevents/spec", "https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/180"]
---
# Internal and asynchronous APIs: gRPC, Protobuf, events

Internal APIs still need contracts. They change more often than public ones, but they break production just as hard: a renamed field in a message or event can stall a consumer you forgot existed. Architecture choices (sync vs async, outbox, sagas) are in `architecture/service-communication` and `architecture/event-driven`; this page covers the contracts.

## Decision guide

**1. Which style for which internal call.**
| Need | Choose |
|---|---|
| Low-latency request/response between services, polyglot, streaming | **gRPC** (Protobuf over HTTP/2) |
| Browsers, partners or simple tooling must call it too | REST + OpenAPI, or Connect / gRPC-Web / transcoding to expose the same proto as HTTP JSON |
| "Something happened", many consumers, decoupled timing | **events** on a broker (Kafka, NATS, RabbitMQ, SNS/SQS, Pub/Sub) with a schema |
| Work to do later, one consumer | a queue message (job) with a schema |
| One codebase, modular monolith | in-process interfaces; no network API at all (`architecture/modular-monolith`) |

**2. gRPC essentials.**
- **Always set a deadline.** By default gRPC sets none, so a client can wait effectively forever. Set a realistic per-call deadline and propagate the remaining deadline to downstream calls (automatic in Java and Go, opt-in in some languages such as C++). Servers check for cancellation and stop work.
- **Retries via service config, only for safe cases.** gRPC's documented example: `maxAttempts: 4`, `initialBackoff: 0.1s`, `maxBackoff: 1s`, `backoffMultiplier: 2`, `retryableStatusCodes: [UNAVAILABLE]`, with ±20% jitter applied. Retry non-idempotent RPCs only with a request id the server dedupes (`api/reliability`). Hedging (parallel attempts) only for idempotent reads.
- **Status codes:** map domain errors to canonical codes (`INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`, `FAILED_PRECONDITION`, `ABORTED` for concurrency conflicts, `RESOURCE_EXHAUSTED` for limits, `UNAVAILABLE` for retryable outages, `PERMISSION_DENIED`/`UNAUTHENTICATED`). Use the richer error model (`google.rpc.Status` with `ErrorInfo`, `BadRequest` field violations) for machine-readable details, the gRPC analogue of problem details.
- **Health checking:** implement `grpc.health.v1.Health` (`SERVING` / `NOT_SERVING`) for load balancers and orchestrators.
- **Security:** TLS or mTLS between services (mesh or library), per-RPC auth metadata (tokens with audience), authorisation per method and per object, message size limits, reflection off in production unless needed.
- **Observability:** interceptors for OpenTelemetry traces and metrics on every client and server.

**3. Protobuf compatibility rules (from the Protobuf dos and don'ts).**
- **Never reuse a field number**; when deleting a field, `reserved` its number (and name). Same for enum values.
- Don't change a field's type; don't add `required` fields (proto3 has none; keep it that way with validation in code instead).
- Every enum starts with `*_UNSPECIFIED = 0` so a missing value is distinguishable.
- Adding fields, messages, RPCs and enum values is compatible on the wire, but consumers must handle unknown enum values; semantic changes still break (AIP-180's rule applies).
- Package per major version (`acme.orders.v1`); a breaking change means a `v2` package served alongside `v1`.
- **Gate it in CI:** `buf breaking --against '.git#branch=main'` (categories: `FILE` default and strictest, `PACKAGE`, `WIRE_JSON`, `WIRE`). Use `WIRE_JSON` if any client uses JSON mapping, `WIRE` if only binary. Also `buf lint` and `buf format`.

**4. Event contracts.**
- **Envelope:** CloudEvents (v1.0.2 is the latest release) gives a common envelope: required `id`, `source`, `specversion`, `type`, plus optional `time`, `subject`, `datacontenttype`, `dataschema`. It has bindings for HTTP, Kafka, AMQP, NATS and others.
- **Types:** `com.acme.order.cancelled.v1` style names; a schema per type (JSON Schema, Avro or Protobuf) in a registry or the repo; compatibility mode set (backward at least) and checked in CI.
- **Event-carried state vs notification:** include the data consumers need (avoids call-back storms) but never secrets or more personal data than needed (Zalando: avoid sensitive data in events; `security/privacy`).
- **Delivery semantics:** assume at-least-once and reordering. Consumers are idempotent by event id and use an entity version or sequence to drop stale events (Zalando: consumers must be robust against duplicates; data-change events need explicit ordering, e.g. hash-partitioned by entity key).
- **Produce reliably:** transactional outbox, not dual writes (`architecture/service-communication`).
- **Evolution:** same rules as APIs: add optional fields; never rename or retype; new major type version for breaks, published in parallel until consumers move.

**5. Document async APIs with AsyncAPI.** AsyncAPI 3.x (3.1.0 latest) describes servers, `channels` (topics/queues), `operations` (`send`/`receive`) and `messages` with schemas, the async counterpart of OpenAPI. Keep it in the repo next to the producer, lint it with the AsyncAPI CLI, and generate docs. For outbound webhooks, OpenAPI 3.1 `webhooks` or AsyncAPI both work (`api/webhooks`).

## Anti-patterns
- gRPC calls without deadlines; retries at every layer with no budget.
- Reusing or renumbering proto fields; changing a field's type "because nobody uses it".
- Enums without an `UNSPECIFIED` zero value.
- Events with no schema, or schemas only in a wiki; consumers parsing producer-internal database rows (CDC without a contract).
- Assuming exactly-once or in-order delivery from a broker.
- Publishing events from application code after commit without an outbox.

## Checks
- CI: `buf lint` + `buf breaking --against '.git#branch=main'` when `.proto` files exist; schema-registry compatibility checks for event schemas; AsyncAPI validation.
- Tests: client calls set deadlines (grep or interceptor test); consumer handles a duplicate and an out-of-order event.
- Review: every new event type has an owner, schema, and listed consumers.

## Sources
- gRPC Deadlines: https://grpc.io/docs/guides/deadlines/ · Retry: https://grpc.io/docs/guides/retry/ · Error handling: https://grpc.io/docs/guides/error/ · Status codes: https://grpc.io/docs/guides/status-codes/ · Health checking: https://grpc.io/docs/guides/health-checking/
- Protobuf dos and don'ts: https://protobuf.dev/best-practices/dos-donts/
- buf breaking: https://buf.build/docs/breaking/ · rules and categories: https://buf.build/docs/breaking/rules/
- AsyncAPI 3.1.0 specification: https://www.asyncapi.com/docs/reference/specification/v3.1.0
- CloudEvents specification: https://github.com/cloudevents/spec
- Zalando RESTful API and Event Guidelines (event design): https://opensource.zalando.com/restful-api-guidelines/
- Google AIP-180 Backwards compatibility: https://google.aip.dev/180
