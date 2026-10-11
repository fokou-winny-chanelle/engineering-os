---
id: data/postgres-queries
title: Reading EXPLAIN ANALYZE and writing PostgreSQL queries that scale (pagination, upserts, batching, CTEs)
area: data
read_when: a query is slow, reading a query plan, writing pagination, upserts, bulk writes, reports or job-queue queries
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/sql-explain.html", "https://www.postgresql.org/docs/current/using-explain.html", "https://www.postgresql.org/docs/current/auto-explain.html", "https://www.postgresql.org/docs/current/pgstatstatements.html", "https://www.postgresql.org/docs/current/sql-insert.html", "https://www.postgresql.org/docs/current/queries-with.html", "https://www.postgresql.org/docs/current/sql-select.html", "https://use-the-index-luke.com/no-offset", "https://wiki.postgresql.org/wiki/Don't_Do_This", "https://www.postgresql.org/docs/release/18.0/", "https://www.postgresql.org/docs/current/runtime-config-resource.html"]
---
# Reading plans and writing queries that scale

## Decision guide

**1. Find the queries worth fixing.** `pg_stat_statements` (needs `shared_preload_libraries` and a restart) sorted by `total_exec_time` for overall load and by `mean_exec_time` for user-facing latency. Add `auto_explain` with `auto_explain.log_min_duration` (default -1 = off) to capture plans of slow statements in production; leave `auto_explain.log_analyze` off or sample it, because the docs warn per-node timing for every statement "can have an extremely negative impact on performance".

**2. Run the plan safely.** `EXPLAIN` alone estimates. `EXPLAIN ANALYZE` **actually executes** the statement: wrap writes in `BEGIN; EXPLAIN ANALYZE …; ROLLBACK;` and never run it on a production write you do not want. In PostgreSQL 18 buffer counts are included automatically with ANALYZE; on older versions say `EXPLAIN (ANALYZE, BUFFERS)`. Use production-like data volume and fresh statistics (`ANALYZE table`); plans on a 100-row dev table tell you nothing.

**3. Read the plan bottom-up, node by node.**
- `cost=startup..total` is in arbitrary planner units, only for comparing plans. `actual time` is milliseconds.
- `loops`: on repeated nodes (inner side of a nested loop) actual time and rows are **per-execution averages**; multiply by loops for the real total. A cheap-looking inner index scan × 50,000 loops is your problem.
- Estimated `rows` vs actual `rows` off by 10× or more → bad statistics or correlated columns: `ANALYZE`, raise the column's statistics target, or `CREATE STATISTICS` for correlated columns.
- `Rows Removed by Filter` large compared to rows returned → missing or wrong index (the filter is applied after reading).
- `Buffers: shared hit` (cache) vs `read` (disk or OS cache); big `read` or `temp` numbers explain slow runs better than time alone.
- A sort that reports disk use or a hash with `Batches` > 1 → the operation spilled past `work_mem` (default 4MB, per operation, so raising it globally multiplies memory use): raise it for that query or role, or sort/hash less data.
- `Heap Fetches` on an Index Only Scan → table not vacuumed enough for the visibility map (`data/postgres-concurrency`).
- Seq Scan on a small table or returning most rows is correct; do not force indexes.

**4. Patterns that scale.**
- **Pagination: keyset, not OFFSET.** OFFSET still reads and discards all skipped rows, so page 1,000 is slow and rows shift between pages. Use `WHERE (created_at, id) < ($last_created_at, $last_id) ORDER BY created_at DESC, id DESC LIMIT 50` with an index on `(created_at DESC, id DESC)` (tenant column first when scoped). Return an opaque cursor. Keep OFFSET only for small admin lists.
- **Counting**: exact `COUNT(*)` on big tables reads every visible row. Show "50+" or use `reltuples` estimates for UI totals; keep exact counts for reports.
- **Upsert**: `INSERT … ON CONFLICT (key) DO UPDATE SET … = EXCLUDED.…` is atomic even under high concurrency (the docs guarantee one of insert or update). Needs a unique index on the conflict target. `ON CONFLICT DO NOTHING` + `RETURNING` for idempotent creates. PG 18 `RETURNING old.*, new.*` shows before/after values in one statement.
- **Avoid N+1**: load children for many parents in one query (`WHERE parent_id = ANY($1)`), or let the ORM batch (`data/orm-sql-testing`).
- **Batch writes**: multi-row `INSERT … VALUES (…), (…)` or `COPY` for bulk loads; `UPDATE … FROM (VALUES …)` for many rows; chunk huge updates/deletes by key range (pick the chunk size by measuring lock time and replica lag) so each transaction is short and autovacuum keeps up.
- **Job queues in Postgres**: `SELECT … FROM jobs WHERE status = 'ready' ORDER BY run_at LIMIT 10 FOR UPDATE SKIP LOCKED` lets workers claim different rows without blocking each other; index `(run_at) WHERE status = 'ready'`.
- **CTEs**: a non-recursive, side-effect-free CTE referenced once is inlined; `MATERIALIZED` forces separate evaluation (an optimisation fence), `NOT MATERIALIZED` forces inlining. Data-modifying CTEs (`WITH moved AS (DELETE … RETURNING *) INSERT … SELECT FROM moved`) move rows atomically.
- **`NOT IN` with a subquery** returns no rows if the subquery yields any NULL (wiki); use `NOT EXISTS`.
- **Ranges on timestamps**: `>= start AND < end`, not `BETWEEN` (wiki).
- **Functions on indexed columns** in `WHERE` (`date(created_at) = …`) defeat the index; rewrite as a range or add an expression index.
- **Large `IN` lists**: pass an array (`= ANY($1)`) so the statement text stays stable for prepared statements and `pg_stat_statements`.
- **Timeouts**: set `statement_timeout` per role or per request (APIs: a few seconds; reports: longer, on a replica) so a runaway query cannot hold a connection forever.

## Examples
```sql
-- keyset page 2+, tenant-scoped
SELECT id, created_at, title FROM posts
WHERE tenant_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC
LIMIT 50;
-- index: (tenant_id, created_at DESC, id DESC)

-- idempotent create from a webhook
INSERT INTO payments (provider_event_id, order_id, amount_minor, currency)
VALUES ($1, $2, $3, $4)
ON CONFLICT (provider_event_id) DO NOTHING
RETURNING id;
```

## Anti-patterns
- Tuning from `EXPLAIN` without `ANALYZE` on realistic data; running `EXPLAIN ANALYZE DELETE` on production.
- `SELECT *` in hot paths (wider rows, no index-only scans, breaks when columns are added).
- OFFSET pagination on large or fast-changing tables; `COUNT(*)` on every list page.
- Read-modify-write in application code instead of one atomic `UPDATE … SET x = x + 1`.
- One giant transaction for a backfill; ORM loops issuing one query per row.

## Checks
- [ ] PRs that add or change hot queries include the `EXPLAIN (ANALYZE, BUFFERS)` output on production-like data.
- [ ] `pg_stat_statements` is enabled in every environment past dev; top 10 by total time reviewed monthly.
- [ ] Lists use keyset pagination (API contract has cursors, see `api-design`).
- [ ] An N+1 test (query counter) guards the main list endpoints.

## Sources
- https://www.postgresql.org/docs/current/sql-explain.html (ANALYZE executes; buffers included with ANALYZE)
- https://www.postgresql.org/docs/current/using-explain.html (cost units; per-loop averages; Rows Removed by Filter; BEGIN/ROLLBACK)
- https://www.postgresql.org/docs/current/auto-explain.html (log_min_duration default -1; log_analyze overhead)
- https://www.postgresql.org/docs/current/pgstatstatements.html
- https://www.postgresql.org/docs/current/sql-insert.html (ON CONFLICT DO UPDATE atomic)
- https://www.postgresql.org/docs/current/queries-with.html (MATERIALIZED; data-modifying WITH)
- https://www.postgresql.org/docs/current/sql-select.html (SKIP LOCKED, NOWAIT)
- https://use-the-index-luke.com/no-offset
- https://wiki.postgresql.org/wiki/Don't_Do_This (NOT IN, BETWEEN)
- https://www.postgresql.org/docs/release/18.0/ (OLD/NEW in RETURNING)
- https://www.postgresql.org/docs/current/runtime-config-resource.html (work_mem default 4MB, per operation)
