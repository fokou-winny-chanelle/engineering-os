---
id: architecture/resilience
title: Resilience patterns (timeouts, retries, circuit breakers, bulkheads, load shedding)
area: architecture
read_when: calling anything over a network, designing failure behaviour, after an incident caused by a slow dependency, or setting timeouts and retries
verified: 2026-10-10
revisit_days: 365
sources: ["https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter", "https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/", "https://sre.google/sre-book/handling-overload/", "https://sre.google/sre-book/addressing-cascading-failures/", "https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload", "https://builder.aws.com/content/3EuS9Sakq7L3VLQIF3qzfMfke1Y/avoiding-fallback-in-distributed-systems", "https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker", "https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead", "https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern", "https://docs.astral.sh/ruff/rules/request-without-timeout/"]
---
# Resilience patterns

The common outage is not a crash; it is a slow dependency that ties up threads, connections and retries until everything upstream falls over (a cascading failure). Resilience is mostly about bounding work: how long you wait, how often you retry, how much you accept, and what you do instead.

## Decision guide

**1. Timeouts on every network call** (HTTP, DB, cache, queue, DNS). No library default you have not read.
- Set connect and read/total timeouts separately. Amazon's method: pick an acceptable false-timeout rate (e.g. 0.1%) and set the timeout at the matching downstream latency percentile (p99.9), with extra allowance for clients far away over the internet.
- Propagate a deadline: each hop gets the remaining budget minus its own work, so a request the user abandoned stops consuming the backend (gRPC deadlines do this natively).
- DB: `statement_timeout`; cache calls: tens of milliseconds, then treat as a miss.

**2. Retries, carefully.** Retries help with brief, independent failures and hurt during overload.
- Retry only idempotent operations, or writes protected by an idempotency key (`architecture/data-consistency`).
- Exponential backoff with jitter. AWS's analysis: "Full Jitter" (sleep a random time between 0 and the exponential cap) uses the least client work; un-jittered backoff keeps clients synchronised.
- Cap attempts (often 2–3 total) and retry at one layer only. Retries at every layer of a 3-deep stack multiply: 3 × 3 × 3 = 27 calls to the bottom service per user request.
- Use a retry budget: Amazon's SDKs use a local token bucket so retries stop when many calls fail; the SRE book suggests a per-process budget (example: 60 retries per minute) and a per-request cap.
- Don't retry on 4xx (except 408/429 with `Retry-After`); do retry on connection errors, 502/503/504.

**3. Circuit breaker** around a dependency that fails or slows: after a failure threshold, fail fast for a cool-off period, then let a few trial requests through (half-open). It protects both sides and frees your threads. Amazon notes breakers add modal behaviour that is hard to test; keep thresholds simple and test the open state.

**4. Bulkheads.** Isolate resources so one bad dependency or tenant can't take all of them: separate connection pools / worker pools / queues for critical vs non-critical work (checkout vs recommendations), per-tenant concurrency limits, separate deployments for batch and interactive traffic.

**5. Load shedding and admission control.** When over capacity, reject early and cheaply (HTTP 503/429 with `Retry-After`) instead of queueing work you will finish too late.
- Bound in-process queues; drop requests that already waited longer than the client's timeout.
- Prioritise: shed analytics and prefetch before checkout. Amazon's load-shedding article separates throughput from goodput (responses that arrive in time to be useful): without shedding, goodput falls once load passes capacity; with it, goodput stays near flat.
- Client-side adaptive throttling (SRE book): each client tracks requests vs accepts over two minutes and starts rejecting locally once requests exceed K × accepts (K e.g. 2).

**6. Rate limiting** per user, API key and tenant at the edge (token bucket); return 429 with `Retry-After`. Protects you from one noisy client and from your own retry storms.

**7. Fallbacks: prefer static, tested ones.** Amazon's guidance is to avoid fallback logic that is rarely exercised: it fails when you need it and can make outages worse. Good degradations: serve stale cached data, hide a non-critical widget, queue the write and show "pending", read-only mode. Bad: switching to a different code path or datastore that only runs during incidents. Whatever you choose, exercise it regularly.

**8. Health checks** that mean something: liveness = the process can make progress (no dependency checks, or a dependency outage restarts every pod); readiness = can serve traffic now (warm, connected). Slow start new instances so they are not flattened by full load while cold.

**9. Test failure.** Fault injection in staging (latency, errors, dependency down), game days, and a load test past the limit to see how it degrades.

| Call type | Timeout | Retry | Breaker | Fallback |
|---|---|---|---|---|
| Payment provider charge | per provider SLA, then mark `PENDING` | only with idempotency key, 1–2× | yes | reconcile later, never auto-charge twice |
| Internal price lookup | short, from p99.9 | 1× with jitter | yes | cached price for display only |
| Recommendations widget | very short | none | yes | hide widget |
| Email send | job-level | queue retries + DLQ | n/a | send later |

## Anti-patterns

- No timeout (Python `requests` default waits forever); timeouts longer than the caller's own timeout.
- Retrying at every layer; retrying non-idempotent writes; retrying without jitter.
- Unbounded queues and thread pools ("it will catch up").
- Liveness probes that check the database.
- Fallbacks that never run outside incidents.
- One shared connection pool for critical and batch traffic.

## Checks

- Python: ruff `S113` (requests/httpx call without `timeout`) is on via the stack pack's `S` rules. TypeScript: review every `fetch` for `AbortSignal.timeout(...)` or a shared client with a default timeout.
- The architecture overview's "Failure modes" table lists each dependency with timeout, retry, breaker and user-visible fallback; `eos next` checks the table exists.
- Incident review asks: which bound was missing (timeout, retry cap, queue bound, rate limit)?

## Sources

- Amazon Builders' Library, Timeouts, retries and backoff with jitter: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- AWS Architecture Blog, Exponential backoff and jitter: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- Google SRE book, Handling overload: https://sre.google/sre-book/handling-overload/
- Google SRE book, Addressing cascading failures: https://sre.google/sre-book/addressing-cascading-failures/
- Amazon Builders' Library, Using load shedding to avoid overload: https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload
- Amazon Builders' Library, Avoiding fallback in distributed systems: https://builder.aws.com/content/3EuS9Sakq7L3VLQIF3qzfMfke1Y/avoiding-fallback-in-distributed-systems
- Azure Architecture Center, Circuit Breaker: https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- Azure Architecture Center, Bulkhead: https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead
- Azure Architecture Center, Rate Limiting: https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern
- Ruff rule S113, request-without-timeout: https://docs.astral.sh/ruff/rules/request-without-timeout/
