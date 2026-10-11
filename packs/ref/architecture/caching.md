---
id: architecture/caching
title: Caching layers
area: architecture
read_when: adding or debugging a cache (HTTP/CDN, app cache, Redis, query cache) or setting cache headers
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.rfc-editor.org/rfc/rfc9111", "https://www.rfc-editor.org/rfc/rfc5861", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching", "https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside", "https://redis.io/docs/latest/develop/reference/eviction/", "https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala", "https://aws.amazon.com/caching/best-practices/"]
---
# Caching layers

A cache trades freshness and complexity for latency and load. Add one only after the query itself is fixed (indexes, no N+1; see `architecture/database-scaling`) and you have a measured hot path. Every cache needs three answers written down: what is the key, when does an entry become wrong, and what happens when the cache is empty or down.

## Decision guide

**Pick the layer closest to the user that is still correct:**

| Layer | Good for | Invalidation | Watch out |
|---|---|---|---|
| Browser (HTTP `Cache-Control`) | static assets, per-user GETs with `private` | fingerprinted URLs (`app.3f9a.js`) + `immutable`; short `max-age` for HTML | you cannot purge a browser |
| CDN / shared cache | public pages, images, API GETs identical for all users | purge API, `s-maxage`, versioned URLs | never cache responses that vary by cookie/auth unless keyed correctly |
| App in-process (LRU map) | tiny hot config, feature flags | TTL seconds; restart clears | each instance differs; memory per pod |
| Distributed (Redis/Valkey/Memcached) | DB query results, rendered fragments, sessions, rate limits | TTL + delete on write | stampedes, hot keys, cache as single point of failure |
| DB-side (materialized view, summary table) | expensive aggregates | `REFRESH MATERIALIZED VIEW [CONCURRENTLY]` on schedule or trigger | refresh cost; staleness window |

**HTTP caching (RFC 9111) essentials:**
- `Cache-Control: public, max-age=31536000, immutable` for fingerprinted assets.
- `Cache-Control: private, no-cache` for personalised HTML: the browser may store but must revalidate (ETag / `If-None-Match` → 304).
- `no-store` for sensitive responses (account pages with PII, tokens).
- `s-maxage` sets the shared-cache (CDN) lifetime separately from browsers.
- `stale-while-revalidate=N` serves the old copy while fetching a new one; `stale-if-error=N` serves it when the origin fails (RFC 5861). This is the cheapest availability win for public content.
- `Vary` must list every request header that changes the body (e.g. `Accept-Encoding`, `Accept-Language`). `Vary: Cookie` usually destroys hit rate; split public and private data instead.

**Application cache patterns:**
- **Cache-aside (default):** read cache → miss → read DB → set with TTL. On write: update DB, then delete the key (not set it: deleting avoids racing writers leaving an old value). Azure's guidance: match expiry to access pattern; too short thrashes, too long serves stale data.
- **Write-through:** write to cache and DB together; fresher reads, slower writes, caches data nobody reads.
- **Write-behind:** write to cache, flush later. Risk of data loss: avoid for anything you can't lose.
- **Refresh-ahead:** refresh hot keys before they expire; for a known small hot set.

**Keys and TTLs.** Include everything the value depends on: `v3:product:{id}:{locale}:{currency}`. A version prefix lets you invalidate a whole family by bumping it after a deploy that changes the shape. Always set a TTL, even with explicit invalidation; it bounds the damage of a missed delete. Add random jitter (e.g. ±10%) to TTLs written in bulk so they don't expire together.

**Stampede (thundering herd) protection** when a hot key expires and 1,000 requests miss at once:
- single-flight / request coalescing in the app (one loader per key, others wait);
- a short lock key (`SET key:lock NX PX 5000`) so one worker recomputes;
- serve stale while one request refreshes (soft TTL inside the value, hard TTL on the key);
- Facebook's memcache paper uses leases to stop both thundering herds and stale sets.

**Eviction and sizing.** Set `maxmemory` and a policy; Redis docs suggest `allkeys-lru` as a good default when a subset of keys is hot. Watch hit rate, evictions and memory. A low or falling hit rate on a hot path means the keys are too specific or the TTLs too short; set your own alert threshold from a baseline week.

**Failure mode.** The app must work (slower) with the cache empty or unreachable: short timeouts on cache calls (tens of ms), circuit-break to the DB, and make sure the DB can survive a cold cache (warm up gradually, or rate-limit misses). If it cannot, the cache has become part of your availability budget; treat it like a database (replicas, failover).

**Never cache across users** anything personalised or permission-dependent unless the user/tenant id and role are in the key.

## Examples

- **Product page:** CDN `s-maxage=60, stale-while-revalidate=300, stale-if-error=86400`; purge by surrogate key on price change. Origin load drops to roughly one request per page per minute per edge.
- **Dashboard aggregate (5 s query):** summary table refreshed every 5 min by a job; the UI shows "updated 3 min ago".
- **Permissions check:** cached per `user:{id}:perms:v{n}` for 60 s; on role change delete the key and bump `n` for that user.

## Anti-patterns

- Caching to hide an N+1 or a missing index.
- No TTL ("we delete on write") → one missed path means stale forever.
- Caching error responses or empty results with the normal TTL (negative caching needs a short TTL).
- Cache in front of a DB that can't survive the cache restarting.
- `Cache-Control: public` on a response that includes a user's data; CDN caching of `Set-Cookie` responses.
- Distributed cache for data already in-process fast enough.

## Checks

- A test that asserts cache headers per route class (assets immutable, personalised `private`, sensitive `no-store`).
- Dashboards: hit rate, evictions, latency of cache calls; alert on hit-rate drop after deploys.
- A chaos/test run with the cache disabled: the service stays within an agreed degraded SLO.

## Sources

- RFC 9111, HTTP Caching: https://www.rfc-editor.org/rfc/rfc9111
- RFC 5861, stale-while-revalidate and stale-if-error: https://www.rfc-editor.org/rfc/rfc5861
- MDN, HTTP caching: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching
- Azure Architecture Center, Cache-Aside pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside
- Redis, Key eviction: https://redis.io/docs/latest/develop/reference/eviction/
- Nishtala et al., Scaling Memcache at Facebook (NSDI 2013): https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala
- AWS, Caching best practices: https://aws.amazon.com/caching/best-practices/
