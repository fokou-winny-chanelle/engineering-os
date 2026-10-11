---
id: api/reliability
title: Reliable writes - idempotency keys, retries, ETag/If-Match concurrency, long-running operations, bulk and batch
area: api
read_when: designing a create/update endpoint clients may retry, adding optimistic locking, an endpoint that takes more than about a second, bulk or batch endpoints, client retry policy
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.rfc-editor.org/rfc/rfc9110", "https://www.rfc-editor.org/rfc/rfc6585", "https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/", "https://docs.stripe.com/api/idempotent_requests", "https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/154", "https://google.aip.dev/155", "https://google.aip.dev/151", "https://google.aip.dev/233", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply"]
adapted_from: ["https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/154", "https://google.aip.dev/155", "https://google.aip.dev/151", "https://google.aip.dev/233", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply"]
---
# Reliable writes: idempotency, concurrency, long-running and bulk operations

Networks fail *after* the server has done the work. The client sees a timeout, retries, and without protection the order is placed twice. Two users edit the same record and the second save silently erases the first. This page covers the API-layer contract; the storage side (transactions, outbox, ledger) is in `architecture/data-consistency` and `security/payments`.

## Decision guide

**1. Which protection for which write.**
| Pattern | Contract | Protects against | Use for |
|---|---|---|---|
| Naturally idempotent method | PUT/DELETE at a known id | duplicate retries | client-chosen ids, upserts |
| **Idempotency key** | `Idempotency-Key: <uuid>` header; same key → same stored response | retries after timeout | every POST that creates or moves value (orders, payments, messages) |
| Secondary (natural) key | unique business field in the body (`external_ref`), unique index | duplicates from *different* clients or imports | imports, integrations |
| Conditional request | `If-Match: "<etag>"` | lost updates from concurrent edits | PATCH/PUT/DELETE on shared resources |
Zalando compares these three and notes they combine; the idempotency key is the strongest (identical responses).

**2. Idempotency keys (de-facto convention).** The IETF `Idempotency-Key` draft expired (last revision October 2025); the header name and behaviour are a widely shared convention (Stripe, Zalando), not a standard.
- Client: generate a random UUIDv4 per *logical* operation, reuse it on every retry of that operation, never put personal data in it. Stripe caps keys at 255 characters.
- Server, in one transaction with the business write:
  1. Look up `(tenant_id, key)`. Not found → insert a row with status `in_progress` and a hash of method + path + body.
  2. Found and complete → return the stored status and body (mark it, e.g. `Idempotent-Replayed: true`).
  3. Found with a **different request hash** → 422 (or 400; Zalando and Stripe reject the mismatch).
  4. Found `in_progress` (concurrent duplicate) → 409 with `Retry-After`; do not run it twice.
  5. On completion store status + body. Keep keys for at least 24 hours (Stripe's documented minimum; Zalando's example); purge with a job.
- Scope keys per tenant/user so one customer cannot replay another's.
- Decide which outcomes are stored. Stripe stores results once execution starts (including errors) but not validation failures or conflicts with a request still running, so those can be retried.
- Google AIP-155 does the same with a `request_id` field in the body; Azure uses `Repeatability-Request-ID` + `Repeatability-First-Sent`. Pick one per API and document it in the spec (Spectral `eos-post-idempotency-key`, info level).

**3. Client retry policy (document it for SDK and app authors).**
- Retry only: network errors, 408, 429, 502, 503, 504, and 500 if the call is idempotent or keyed. Never retry other 4xx unchanged.
- Exponential backoff with full jitter, capped (e.g. 0.5 s base, ×2, max 30 s, at most 3-5 attempts), honouring `Retry-After`.
- Overall deadline per user action; one retry layer only (the SDK *or* the gateway *or* the app, not all three). Retry budgets and circuit breakers: `architecture/resilience`.

**4. Optimistic concurrency with ETags.**
- `GET /orders/1` → `ETag: "v42"` (a version column or hash; strong validator). Also expose it as an `etag` field if clients cache bodies (AIP-154).
- `PATCH /orders/1` with `If-Match: "v42"` → server updates `WHERE id=1 AND version=42`; zero rows → **412 Precondition Failed** with the current ETag. RFC 9110: If-Match uses strong comparison.
- Require it for contended resources: missing If-Match → **428 Precondition Required** (RFC 6585 created it for exactly this "lost update" case).
- `If-None-Match: *` on PUT means "create only if absent" (412 if it exists).
- Conditional GET (`If-None-Match` → 304) saves bandwidth for mobile.
- Prefer ETags to `Last-Modified`/`If-Unmodified-Since`: one-second resolution cannot tell apart two updates in the same second (Azure guidelines).

**5. Long-running operations (LRO).** Azure: make it an LRO when p99 latency would exceed about 1 second. Pattern (Azure async request-reply):
1. Validate synchronously; bad input → 400/422 immediately, not later.
2. `202 Accepted` + `Location: /operations/op_123` (+ `Retry-After: 2`). The `POST` takes an idempotency key.
3. `GET /operations/op_123` → `200 {"id": "op_123", "status": "RUNNING", "percent_complete": 40}`.
4. Finished → `{"status": "SUCCEEDED", "result_url": "/reports/r_9"}` (or 303 See Other to it), or `FAILED` with an embedded problem-details `error`.
- Status enum: `NOT_STARTED, RUNNING, SUCCEEDED, FAILED, CANCELLED`; terminal states never change. Optional `POST /operations/{id}:cancel`.
- Keep operation records for a documented time (e.g. 24 h to 7 days); poll with backoff or offer a webhook on completion (`api/webhooks`). Google AIP-151 returns an `Operation` resource the same way.
- Do not make PATCH long-running (Azure); use a POST action.

**6. Bulk and batch.**
| Need | Design |
|---|---|
| Same operation on many items, independent | `POST /orders:batchCreate` (AIP-233) with `{"requests": [...]}`, max N items (e.g. 100); each item gets a result |
| All-or-nothing | say so: one transaction, one status code; reject if any item fails |
| Partial success | `207 Multi-Status` (Zalando) with per-item status and resource or problem, in request order |
| Very large (≥10k rows) | async import job (LRO) reading an uploaded file; report per-row errors as a downloadable result |
- One idempotency key covers the whole batch; per-item keys if items can be retried alone.
- Rate limits and authorisation apply per item (a batch must not bypass BOLA checks; `security/authorization`).
- Avoid generic "batch any request" endpoints: they hide errors and complicate auth and limits.

## Anti-patterns
- Retrying POST (client, proxy or job runner) with no idempotency key.
- Idempotency table updated in a separate transaction from the business write (crash between them = duplicate or lost effect).
- Keys global across tenants; keys accepted with a different body.
- Last-write-wins on shared records with no version check.
- A 30-second synchronous request behind a 30-second load-balancer timeout.
- LRO that validates only after 202 so clients learn of bad input minutes later.
- Batch endpoint returning 200 when half the items failed and not saying which.

## Checks
- `.spectral.yaml`: `eos-post-idempotency-key` (info; exempt read-only POSTs with an override and a comment).
- Test each keyed endpoint: same key twice (one effect, same response), same key + different body (rejected), two parallel requests (one runs, one 409).
- Test concurrency: two PATCHes with the same ETag → one 412.
- Schemathesis stateful checks exercise create-then-use flows (`api/testing`).

## Sources
- RFC 9110 (methods, conditional requests): https://www.rfc-editor.org/rfc/rfc9110 · RFC 6585 (428): https://www.rfc-editor.org/rfc/rfc6585
- Idempotency-Key header draft (expired): https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- Stripe idempotent requests: https://docs.stripe.com/api/idempotent_requests
- Zalando RESTful API Guidelines: https://opensource.zalando.com/restful-api-guidelines/
- Google AIP-154 etags: https://google.aip.dev/154 · AIP-155 request ids: https://google.aip.dev/155 · AIP-151 LRO: https://google.aip.dev/151 · AIP-233 batch create: https://google.aip.dev/233
- Microsoft Azure REST API Guidelines: https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- Azure Architecture Center, Asynchronous Request-Reply pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply

## Attribution
Adapted from "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/), "API Improvement Proposals" 151, 154, 155 and 233 by Google (https://google.aip.dev/151, https://google.aip.dev/154, https://google.aip.dev/155, https://google.aip.dev/233), "Microsoft Azure REST API Guidelines" by Microsoft (https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) and "Asynchronous Request-Reply pattern" by Microsoft, Azure Architecture Center (https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined with RFC and Stripe documentation, and eos defaults added. Not endorsed by the original authors.
