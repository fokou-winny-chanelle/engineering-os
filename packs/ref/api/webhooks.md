---
id: api/webhooks
title: Outbound webhooks - event design, signing (Standard Webhooks), delivery, retries, ordering, replay, SSRF-safe sending
area: api
read_when: building a webhook system that notifies customers or partners, choosing a payload and signature scheme, retry and disable policy, event ordering, letting customers replay events
verified: 2026-10-10
revisit_days: 365
sources: ["https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md", "https://www.standardwebhooks.com/", "https://docs.stripe.com/webhooks", "https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks", "https://github.com/cloudevents/spec", "https://opensource.zalando.com/restful-api-guidelines/"]
---
# Outbound webhooks

A webhook is an HTTP POST you send to a URL a customer gave you when something happens. It is a public API with the roles reversed: you must sign it, retry it, never let it reach your own network, and give receivers a way to catch up. Receiving webhooks (verifying a provider's signature, dedupe, re-fetch) is covered in `security/payments`, with a tested verifier in `eos scaffold security-tests`.

## Decision guide

**1. Use the Standard Webhooks spec (v1.0.0, Apache-2.0) instead of inventing a scheme.** Libraries exist for many languages for both sending and verifying, and receivers already know it.
```
POST https://customer.example/hooks
webhook-id: msg_2KWPBgLlAfxdpx2AI54pPJ85f4W
webhook-timestamp: 1791651600
webhook-signature: v1,K5oZfzN95Z9UVu1EsfQmfVNQhnkZ2pj9o9NDN/H/pI4=
content-type: application/json

{"type":"invoice.paid","timestamp":"2026-10-10T17:00:00Z","data":{"id":"inv_123","status":"PAID"}}
```
- Signature: HMAC-SHA256 over `"{webhook-id}.{webhook-timestamp}.{body}"` with a per-endpoint secret (24-64 random bytes, shown as `whsec_<base64>`). Asymmetric `v1a` (ed25519) is available if receivers must not hold a shared secret.
- The signature header is a space-separated list so you can sign with old and new secrets during rotation (zero-downtime rotation).
- Receivers check the timestamp tolerance (replay protection) and use `webhook-id` to dedupe. Document both in your guide with a code sample.
- Unique secret per endpoint; let customers roll it from the dashboard or API.

**2. Event and payload design.**
| Choice | Option A | Option B |
|---|---|---|
| Payload | **thin**: type + id; receiver fetches the current state via the API (always fresh, permissions re-checked) | **full**: snapshot of the resource (fewer calls; can be stale or leak fields) |
| Size | Standard Webhooks recommends keeping payloads small, usually under 20 KB | |
| Envelope | own small envelope (`type`, `id`, `timestamp`, `data`) | CloudEvents (`specversion`, `id`, `source`, `type`), useful if events also go to brokers |
- Event types: `resource.past_tense_verb` (`invoice.paid`, `order.cancelled`), catalogued with a schema per type, versioned like any API (adding fields is fine; renaming is breaking; see `api/evolution`). Describe them in the spec (OpenAPI 3.1 `webhooks` section) or AsyncAPI.
- Never include secrets, full card or ID numbers, or data the endpoint owner is not entitled to.
- Customers subscribe to specific event types per endpoint; filter on your side.

**3. Delivery pipeline.**
1. Write the event to an outbox table in the **same transaction** as the business change (`architecture/service-communication`).
2. A worker fans out one delivery per subscribed endpoint and queues it.
3. Send with short timeouts (connect ~5 s, total ~10-15 s). GitHub asks receivers to answer within 10 seconds, so receivers should queue work and return 2xx fast; say the same in your docs.
4. Record every attempt (status, latency, response snippet) and show it to customers in a delivery log.

**4. Retries and disabling.**
- Treat 2xx as success; 3xx as failure (do not follow redirects; ask the customer to update the URL); 410 Gone as "disable this endpoint"; 429/502/503/504 as throttle signals; honour `Retry-After` (Standard Webhooks status guidance).
- Exponential backoff with jitter over roughly three days. Standard Webhooks' example schedule: immediately, 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 14 h, 20 h, 24 h (about 75 hours in total). Stripe retries live-mode events for up to three days.
- After persistent failure, disable the endpoint and email the owner; offer one-click re-enable plus replay.
- Per-endpoint concurrency limits and a circuit breaker so one slow customer cannot block others' deliveries.

**5. Ordering and duplicates.** Promise **at-least-once, unordered** delivery, like Stripe ("no ordering guarantee"). Receivers must be idempotent by `webhook-id` and must not assume order: include the resource's `updated_at` or a version so they can ignore stale events, or send thin events so they fetch current state. Strict per-resource ordering needs a single-flight queue per resource key and blocks behind a failing delivery; offer it only when truly needed.

**6. Replay and catch-up.**
- Events API: `GET /events?type=…&created_after=…` (cursor-paginated) for reconciliation, kept for a documented window (e.g. 30 days).
- Manual redeliver in the dashboard/API, bulk "resend all failed since T".
- Test events (`POST /webhook-endpoints/{id}:test`) and a sandbox mode.

**7. Security of the sender (SSRF).** Customer-supplied URLs are SSRF by design. Standard Webhooks recommends sending through an egress proxy that blocks internal addresses (such as Stripe's smokescreen) and running webhook workers in their own subnet with no route to internal services. Also: https only in production, resolve and check the IP at send time (DNS rebinding), block link-local and metadata addresses (169.254.169.254), cap response size, never send cookies or internal auth headers. Details: `security/input-injection` (SSRF).

## Anti-patterns
- Sending webhooks inline in the request handler (slow requests, lost events on crash).
- One global signing secret, or unsigned webhooks "protected" by an obscure URL.
- Retrying forever, or never; retrying on 3xx by following redirects into your network.
- Promising ordering you cannot keep; receivers updating state from out-of-order events.
- Full payloads containing fields the receiver's role cannot see via the API.
- No delivery log, so customers cannot debug and support cannot answer.

## Checks
- Unit test: signature matches the Standard Webhooks test vectors of the library you use; rotation sends two signatures.
- Integration test: a receiver returning 500 then 200 sees exactly one processed event (dedupe by `webhook-id`).
- SSRF test: endpoint URLs resolving to 127.0.0.1, 10.0.0.0/8, 169.254.169.254 and IPv6 equivalents are refused at registration and at send time.
- Review: event catalogue entries have a schema and an owner.

## Sources
- Standard Webhooks specification v1.0.0: https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md · site and libraries: https://www.standardwebhooks.com/
- Stripe webhooks (retries, no ordering guarantee): https://docs.stripe.com/webhooks
- GitHub webhook best practices (10 s, delivery id): https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
- CloudEvents specification: https://github.com/cloudevents/spec
- Zalando RESTful API and Event Guidelines (events robust against duplicates): https://opensource.zalando.com/restful-api-guidelines/
