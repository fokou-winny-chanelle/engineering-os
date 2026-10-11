---
id: data/postgres-indexing
title: PostgreSQL indexing in depth (types, column order, partial/covering/expression, FK indexes, upkeep)
area: data
read_when: adding or reviewing an index, a query is slow despite an index, choosing GIN/GiST/BRIN, or cleaning up unused and invalid indexes
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/indexes-types.html", "https://www.postgresql.org/docs/current/indexes-multicolumn.html", "https://www.postgresql.org/docs/current/indexes-index-only-scans.html", "https://www.postgresql.org/docs/current/indexes-partial.html", "https://www.postgresql.org/docs/current/sql-createindex.html", "https://www.postgresql.org/docs/current/ddl-constraints.html", "https://www.postgresql.org/docs/current/monitoring-stats.html", "https://www.postgresql.org/docs/current/storage-hot.html", "https://www.postgresql.org/docs/release/18.0/", "https://use-the-index-luke.com/", "https://github.com/pgvector/pgvector", "https://www.postgresql.org/docs/current/gin.html", "https://www.postgresql.org/docs/current/indexes-unique.html", "https://www.postgresql.org/docs/current/hot-standby.html"]
---
# PostgreSQL indexing in depth

`architecture/database-scaling` has the short version (find slow queries, composite order, pooling). This ref is the detail for when you are actually designing or debugging indexes. Always confirm with `EXPLAIN (ANALYZE, BUFFERS)` on realistic data (`data/postgres-queries`).

## Decision guide

**1. Index types** (core PostgreSQL 18: B-tree, Hash, GiST, SP-GiST, GIN, BRIN; plus the `bloom` extension):
| Type | Use for | Notes |
|---|---|---|
| B-tree (default) | `= < <= >= >`, `BETWEEN`, `IN`, `IS NULL`, sorting, anchored `LIKE 'foo%'` | Non-C locales need `text_pattern_ops` for `LIKE 'foo%'`; never helps `LIKE '%bar'` |
| Hash | Equality only | Rarely better than B-tree; only B-tree can be unique, and hash cannot be multicolumn |
| GIN | Values with many parts: `jsonb`, arrays, full-text `tsvector`, trigrams (`pg_trgm`) | Updates tend to be slow (one index insert per extracted key; the fast-update pending list softens this) |
| GiST | Ranges and overlap (`&&`), geometry/PostGIS, exclusion constraints, nearest-neighbour `ORDER BY <->` | Lossy for some opclasses (rechecks) |
| SP-GiST | Space-partitioned data: points, quadtrees, tries, IP ranges | Niche; test against GiST |
| BRIN | Huge tables where the column follows physical order (append-only `created_at`, ids) | Tiny; useless if rows are updated or inserted out of order |
For vectors (pgvector): exact search by default (perfect recall); HNSW (better speed/recall, slower build, more memory) or IVFFlat for approximate search, which changes results.

**2. Multicolumn B-tree order.** Equality columns first, then the one range or sort column: the docs' rule is that equality constraints on leading columns, plus an inequality on the first column without equality, limit the part of the index scanned; later columns are only filters inside the index. PostgreSQL 18 adds **skip scan**, which can use an index when a leading column has no condition (useful when that column has few distinct values), but design for the leading-column rule anyway. Match sort direction for mixed `ORDER BY a ASC, b DESC`.

**3. Shapes that pay off.**
- **Partial**: index only the rows you query: `WHERE status = 'pending'`, `WHERE deleted_at IS NULL`. Smaller, faster, and enables "unique among live rows". The query's `WHERE` must imply the index predicate.
- **Covering** (`INCLUDE (cols)`): payload columns enable index-only scans without widening the search key. Index-only scans skip the table only for pages marked all-visible in the visibility map, so they work well on tables vacuumed regularly and poorly on heavily updated ones (check `Heap Fetches` in EXPLAIN).
- **Expression**: index exactly what you filter on: `lower(email)`, `(payload->>'order_id')`, `date_trunc('day', created_at AT TIME ZONE 'UTC')` (expression must be immutable; queries must use the same expression).
- **Unique** indexes and constraints enforce rules; `NULLS NOT DISTINCT` makes NULLs collide when you need that.

**4. Foreign keys need an index on the referencing columns.** The docs: declaring a foreign key "does not automatically create an index on the referencing columns". Without it, every `DELETE`/key `UPDATE` on the parent scans the child table (and holds locks meanwhile), and joins from parent to children are slow. The index's leading columns must be the FK columns (any order among themselves). `schema_lint.sql` from `eos scaffold db-safety` lists FKs without one; exempt only reviewed cases (tiny lookup tables whose parent rows are never deleted).

**5. Every index has a price.** Each one slows every insert and most updates, uses memory and disk, and can stop HOT updates: an update is heap-only (no index writes) only if it changes no indexed column (BRIN excepted) and the page has free space. So:
- Avoid indexing frequently-updated columns you rarely search on (`last_seen_at`).
- Consider `fillfactor` below 100 on update-heavy tables to leave room for HOT.
- Prefer one composite index that serves several queries over many single-column ones.

**6. Build and change indexes safely on live tables.**
- `CREATE INDEX CONCURRENTLY` (takes SHARE UPDATE EXCLUSIVE: reads and writes continue). It cannot run inside a transaction block, waits for existing transactions that touched the table, and if it fails leaves an **INVALID** index that still costs writes: drop it and retry. squawk `require-concurrent-index-creation` and `ban-concurrent-index-creation-in-transaction` enforce both halves.
- `DROP INDEX CONCURRENTLY` and `REINDEX CONCURRENTLY` likewise (squawk `require-concurrent-index-deletion`, `require-concurrent-reindex`).
- Unique constraint on a big table: build the unique index concurrently, then `ALTER TABLE … ADD CONSTRAINT … UNIQUE USING INDEX …` (squawk `disallowed-unique-constraint`).

**7. Upkeep.**
- Unused: `pg_stat_user_indexes.idx_scan = 0` (and `last_idx_scan`) across a full business cycle; standbys record their own index usage, so check replicas that serve reads too. Keep indexes that back constraints.
- Duplicates: an index that is a leading-column prefix of another with the same predicate is usually redundant.
- Invalid: `SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;` should be empty.
- Bloat after mass updates/deletes: `REINDEX CONCURRENTLY`, or pg_repack for tables (`data/postgres-concurrency`).

## Examples
```sql
-- "my open tickets, newest first", tenant-scoped
CREATE INDEX CONCURRENTLY tickets_open_idx
  ON tickets (tenant_id, assignee_id, created_at DESC)
  WHERE status <> 'closed';
-- covering lookup for an API that returns only id and status
CREATE INDEX CONCURRENTLY orders_ext_idx ON orders (external_ref) INCLUDE (status);
-- jsonb containment
CREATE INDEX CONCURRENTLY events_payload_idx ON events USING gin (payload jsonb_path_ops);
-- huge append-only table
CREATE INDEX CONCURRENTLY metrics_time_brin ON metrics USING brin (recorded_at);
```

## Anti-patterns
- An index per column "just in case"; indexes that duplicate the primary key prefix.
- Expecting `WHERE lower(email) = …` to use an index on `email`; functions on the column defeat plain indexes.
- Leading a composite index with a low-selectivity column that queries do not filter on.
- Non-concurrent `CREATE INDEX` on a large live table in a migration (blocks writes for the whole build).
- Leaving INVALID indexes after a failed concurrent build.
- Adding indexes without checking the plan before and after.

## Checks
- [ ] `schema_lint.sql` (db-safety scaffold) passes: no FK without a supporting index.
- [ ] squawk passes on migrations (concurrent index rules on, `.squawk.toml` from the scaffold).
- [ ] New index PRs include the target query and its `EXPLAIN (ANALYZE, BUFFERS)` before/after.
- [ ] Quarterly: unused, duplicate and invalid index queries reviewed; results recorded.

## Sources
- https://www.postgresql.org/docs/current/indexes-types.html (types and supported operators; BRIN correlation)
- https://www.postgresql.org/docs/current/indexes-multicolumn.html (leading-column rule; skip scan; which types support multiple key columns)
- https://www.postgresql.org/docs/current/indexes-index-only-scans.html (visibility map; INCLUDE)
- https://www.postgresql.org/docs/current/indexes-partial.html
- https://www.postgresql.org/docs/current/sql-createindex.html (CONCURRENTLY; INVALID index after failure)
- https://www.postgresql.org/docs/current/ddl-constraints.html (FK does not create an index)
- https://www.postgresql.org/docs/current/monitoring-stats.html (idx_scan, last_idx_scan)
- https://www.postgresql.org/docs/current/storage-hot.html (HOT conditions)
- https://www.postgresql.org/docs/release/18.0/ (skip scan)
- https://use-the-index-luke.com/
- https://github.com/pgvector/pgvector (exact by default; HNSW vs IVFFlat)
- https://www.postgresql.org/docs/current/gin.html (GIN updates tend to be slow; pending list)
- https://www.postgresql.org/docs/current/indexes-unique.html (only B-tree can be unique)
- https://www.postgresql.org/docs/current/hot-standby.html (standbys record index usage)
