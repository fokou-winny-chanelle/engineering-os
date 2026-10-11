---
id: data/search-redis
title: Search (Postgres full-text and trigram vs a search engine) and Redis use and misuse
area: data
read_when: adding search, autocomplete or semantic search, or adding Redis (cache, sessions, rate limits, queues, locks) to a project
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/textsearch-intro.html", "https://www.postgresql.org/docs/current/textsearch-controls.html", "https://www.postgresql.org/docs/current/textsearch-tables.html", "https://www.postgresql.org/docs/current/textsearch-indexes.html", "https://www.postgresql.org/docs/current/pgtrgm.html", "https://github.com/pgvector/pgvector", "https://www.meilisearch.com/docs/learn/getting_started/what_is_meilisearch", "https://typesense.org/docs/overview/what-is-typesense.html", "https://docs.opensearch.org/latest/about/", "https://redis.io/docs/latest/develop/reference/eviction/", "https://raw.githubusercontent.com/redis/redis/unstable/redis.conf", "https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/", "https://redis.io/docs/latest/commands/keys/", "https://redis.io/docs/latest/commands/scan/", "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/", "https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html", "https://redis.io/legal/licenses/", "https://valkey.io/"]
---
# Search, and Redis without regrets

## Decision guide: search

**1. Start in Postgres; move out when a named need appears.**
| Need | Postgres answer | Move to a search engine when |
|---|---|---|
| Keyword search over titles/bodies, stemming, ranking | Full-text search: `tsvector` + GIN | Relevance tuning, synonyms, per-field boosting and analytics become a product feature |
| Typo tolerance, "contains" (`LIKE '%abc%'`), fuzzy names | `pg_trgm` (`similarity`, `%`, GIN/GiST indexes support `LIKE`, `ILIKE`, `~`, `~*`) | Instant search-as-you-type across many fields with typo tolerance and facets out of the box |
| Facets and filters on structured fields | Normal indexes + `GROUP BY` | Many facets over millions of documents at interactive latency |
| Semantic / similarity search | pgvector (exact by default; HNSW or IVFFlat approximate indexes) | Very large vector sets or hybrid ranking you cannot tune in SQL |
| Search across several databases or services | (not a fit) | Always: a dedicated index fed by events/CDC |
Dedicated engines: Meilisearch and Typesense (open source, typo-tolerant, instant search; Typesense describes itself as an open-source alternative to Algolia), OpenSearch/Elasticsearch (large-scale, logs plus search, more operations). Each adds a second copy of the data to keep in sync, secure and delete from.

**2. Postgres full-text search done properly.**
```sql
ALTER TABLE articles ADD COLUMN search tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body, '')), 'B')) STORED;
CREATE INDEX CONCURRENTLY articles_search_idx ON articles USING gin (search);
SELECT id, title, ts_rank(search, q) AS rank
FROM articles, websearch_to_tsquery('english', $1) AS q
WHERE search @@ q ORDER BY rank DESC LIMIT 20;
```
- `websearch_to_tsquery` accepts user-style input (quotes, `or`, `-word`) without syntax errors; `to_tsquery` is stricter.
- Pick the text search configuration per language (`english`, `french`, … several are predefined; store a `language` column for multilingual content and build the vector with it).
- GIN is the preferred text search index; a stored generated column keeps the vector in sync without triggers.
- Keep tenant and permission filters in the same query (`WHERE tenant_id = $2 AND search @@ q`).

**3. Syncing an external search index.** The database stays the source of truth. Write changes to an outbox in the same transaction and index from it (or CDC), make indexing idempotent, rebuild from scratch with a script, and include the index in tenant offboarding and personal-data erasure (`data/history-retention`). Apply authorization after search too: never return documents the user may not read.

## Decision guide: Redis

**4. Good uses** (each with a TTL and a defined loss tolerance): cache of database reads (`architecture/caching`), sessions, rate-limit counters (`INCR` + `EXPIRE`), short-lived tokens/OTP attempts, leaderboards (sorted sets), lightweight queues and fan-out (Streams with consumer groups; pub/sub for fire-and-forget), de-duplication sets, locks for **efficiency** (avoid doing the same work twice).

**5. Misuse to avoid.**
- **Source of truth for money, orders or anything you cannot rebuild.** With RDB snapshots you can lose the last minutes of writes on a crash; AOF with `appendfsync everysec` can lose about 1 second. Keep durable facts in Postgres.
- **No memory policy.** The default `maxmemory-policy` is `noeviction`: when memory is full, writes that add data fail. For a pure cache set `maxmemory` and `allkeys-lru` (or `allkeys-lfu`); `volatile-*` policies only evict keys with a TTL and behave like noeviction if none have one. Use separate instances (or databases with care) for cache vs data that must not be evicted.
- **`KEYS` in application code.** The docs: "Don't use KEYS in your regular application code"; it blocks the server on large datasets. Use `SCAN` (incremental; may return duplicates, so callers must tolerate them) or keep explicit index sets.
- **Unbounded keys and big values**: every key gets a TTL unless it is deliberately permanent; keep values small (split large hashes/lists); namespace keys (`app:t:42:…`).
- **Locks for correctness.** Kleppmann's analysis: a lease can expire while the holder is paused (GC, network), so two clients act at once; for correctness the protected resource must check a monotonically increasing **fencing token**. Redis's own docs present Redlock as a proposal open to analysis. For correctness use database constraints, row locks or advisory locks in Postgres (`data/postgres-concurrency`); use Redis locks only where a duplicate is merely wasteful.
- **Cache invalidated before the DB commit**, or cache keys without tenant/version.
- **Exposed Redis**: bind privately, require auth/ACLs and TLS on shared networks; never on a public IP.

**6. Licensing and forks** (check before you ship it inside a product): Redis 8 is available under RSALv2, SSPLv1 or AGPLv3; Valkey is a BSD-licensed key/value store backed by the Linux Foundation (9.1.2 current at verification; providers listed on valkey.io describe it as compatible with Redis OSS). Managed services may run either; check the modules you depend on (JSON, search) before switching.

## Anti-patterns
- `LIKE '%term%'` on a big table without a trigram index; building a search engine out of `ILIKE` chains.
- A search cluster added "for later" with no sync or deletion story.
- Redis used as the only copy of carts, balances or job state that must not be lost.
- `KEYS *` in a cron job; keys with no TTL growing until eviction or OOM.
- Redlock or `SET NX` guarding a payment.

## Checks
- [ ] Search queries include tenant/permission filters; search index included in erasure and offboarding tests.
- [ ] FTS: generated `tsvector` column + GIN index; queries use `websearch_to_tsquery` for user input.
- [ ] Redis config reviewed: `maxmemory` + policy matches use; persistence choice written down; no `KEYS` (grep in CI); all keys have TTL or a documented reason.
- [ ] Locks: anything correctness-critical is enforced by Postgres, not by a Redis lock.

## Sources
- https://www.postgresql.org/docs/current/textsearch-intro.html
- https://www.postgresql.org/docs/current/textsearch-controls.html (websearch_to_tsquery)
- https://www.postgresql.org/docs/current/textsearch-tables.html (stored generated tsvector + GIN)
- https://www.postgresql.org/docs/current/textsearch-indexes.html (GIN preferred)
- https://www.postgresql.org/docs/current/pgtrgm.html (LIKE/ILIKE/regex index support)
- https://github.com/pgvector/pgvector
- https://www.meilisearch.com/docs/learn/getting_started/what_is_meilisearch
- https://typesense.org/docs/overview/what-is-typesense.html
- https://docs.opensearch.org/latest/about/
- https://redis.io/docs/latest/develop/reference/eviction/ (policies; volatile-* like noeviction without TTLs)
- https://raw.githubusercontent.com/redis/redis/unstable/redis.conf (default maxmemory-policy noeviction)
- https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/ (RDB minutes; AOF everysec about 1 s)
- https://redis.io/docs/latest/commands/keys/
- https://redis.io/docs/latest/commands/scan/
- https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
- https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html (efficiency vs correctness; fencing tokens)
- https://redis.io/legal/licenses/ (RSALv2, SSPLv1, AGPLv3)
- https://valkey.io/ (BSD, Linux Foundation, 9.1.2)
