---
id: architecture/database-scaling
title: Database scaling (indexing, pooling, replicas, partitioning, sharding)
area: architecture
read_when: a query is slow, DB CPU or connections are high, planning replicas, partitioning or sharding
verified: 2026-10-10
revisit_days: 365
sources: ["https://use-the-index-luke.com/", "https://www.postgresql.org/docs/current/indexes.html", "https://www.postgresql.org/docs/current/using-explain.html", "https://www.postgresql.org/docs/current/pgstatstatements.html", "https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing", "https://www.pgbouncer.org/features.html", "https://www.postgresql.org/docs/current/runtime-config-connection.html", "https://www.postgresql.org/docs/current/hot-standby.html", "https://www.postgresql.org/docs/current/ddl-partitioning.html", "https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/", "https://www.notion.com/blog/sharding-postgres-at-notion", "https://github.blog/engineering/infrastructure/partitioning-githubs-relational-databases-scale/"]
---
# Database scaling

Climb in order and stop at the first step that meets the SLO with headroom: queries and indexes → pooling → bigger box → caching → replicas → partitioning → vertical split by table group → horizontal sharding. Each step up costs more to run and to undo. Examples here are PostgreSQL; the ideas carry to MySQL.

## Decision guide

**1. Find the expensive queries.** Turn on `pg_stat_statements` and sort by `total_exec_time` (total cost) and by `mean_exec_time` (worst user experience). Fix the top 5 before anything else. Read plans with `EXPLAIN (ANALYZE, BUFFERS)`: look for `Seq Scan` on big tables, row estimates far from actual (run `ANALYZE`, raise statistics), `Sort` spilling to disk, and nested loops over thousands of rows.

**2. Index for the real access paths** (Use The Index, Luke is the best free guide):
- B-tree by default. Composite index column order: equality columns first, then the range or sort column: `WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC` → `(tenant_id, status, created_at DESC)`.
- Covering index (`INCLUDE (...)`) to allow index-only scans for hot reads.
- Partial index for skewed filters: `CREATE INDEX … ON jobs (run_at) WHERE status = 'pending'`.
- Expression index when you query a function: `lower(email)`.
- GIN for `jsonb` containment, arrays and full-text; BRIN for huge append-only tables ordered by time.
- Every foreign key you join or cascade on needs an index on the referencing column (Postgres does not create it).
- Each index slows writes and takes memory; drop unused ones (`pg_stat_user_indexes.idx_scan = 0` over a full business cycle).
- Build on live tables with `CREATE INDEX CONCURRENTLY` (migration lint enforces it).

**3. Pool connections.** Each Postgres connection is a process; `max_connections` defaults to typically 100. Many app instances × big pools exhaust it and slow everything.
- HikariCP's formula as a starting point for active connections: `(core_count × 2) + effective_spindle_count` (spindles ≈ 0 when data is cached). Small pools with waiting threads beat big pools. Then load test around it.
- Total = instances × pool size must stay under `max_connections` minus admin/replication headroom.
- Serverless or many workers → a pooler (PgBouncer, RDS Proxy, Supabase/Neon poolers). PgBouncer transaction pooling breaks session features (`SET`/`RESET`, `LISTEN`, SQL `PREPARE`, `WITH HOLD` cursors, session-level advisory locks); protocol-level prepared statements work only with `max_prepared_statements` > 0. Check its feature table against your driver.
- Set `statement_timeout` and `idle_in_transaction_session_timeout` so one bad query or forgotten transaction can't hold connections and locks.

**4. Scale up** before scaling out: a bigger instance with more RAM (working set fits in memory) and faster storage is a config change, not an architecture change.

**5. Read replicas** (streaming replication / hot standby) for read-heavy loads that tolerate lag: reports, search indexing, public pages. Not for: reads right after a write by the same user (read-your-writes), or anything that decides money. Monitor replication lag and stop routing to a replica that falls behind. Replicas do not help write load.

**6. Partition a big table** (declarative range/list/hash). The Postgres docs' rule of thumb: worth it when the table would exceed the server's physical memory. Best fit: time-series and append-only data (events, logs, ledger history) partitioned by month, where old partitions are detached and archived instead of `DELETE`d. Queries must filter on the partition key or they scan all partitions. Unique constraints must include the partition key.

**7. Vertical split** by table group into separate databases. Figma did this first ("a dozen vertically partitioned databases") and called it a relatively easy, very impactful lever before horizontal sharding; GitHub moved table groups off its main `mysql1` cluster and reported a 50% load reduction on the hosts that took that data. Requires that the moved tables are not joined with the rest: modules that own their tables make this possible (see `architecture/modular-monolith`).

**8. Horizontal sharding** on a key that almost every query has (tenant, workspace, user). Notion chose 480 logical shards (Postgres schemas) on 32 physical databases, so shards can move between machines without re-sharding. Costs: cross-shard queries and transactions, rebalancing, per-shard migrations, global uniqueness (use UUIDs/ULIDs or a sequence service). Consider managed distributed SQL or Citus-style extensions before building your own router. This is a one-way door: ADR plus human review.

## Examples

- **Slow tenant dashboard (2.4 s):** `pg_stat_statements` shows one query at 60% of total time; plan shows a seq scan on 30M rows filtered by `tenant_id` and sorted by `created_at`; composite index `(tenant_id, created_at DESC)` → index scan; p95 drops; before/after plans go in the PR.
- **Connection storms on deploy:** 20 pods × pool 20 = 400 > 100 max → PgBouncer in transaction mode, app pools of 5, `statement_timeout = 5s` for web traffic.
- **Events table at 2 TB:** monthly range partitions, detach after 13 months to cheap storage; BRIN on `created_at` inside partitions.

## Anti-patterns

- Adding replicas or a cache before reading the query plan.
- An index on every column "just in case"; or none on foreign keys.
- `OFFSET` pagination deep into large tables (see `architecture/api-performance`).
- Huge app pools ("more connections = more throughput").
- Long transactions that hold locks while calling external APIs.
- Sharding by a key many queries don't have (forces scatter-gather); sharding before vertical splits and partitioning were tried.

## Checks

- `pg_stat_statements` enabled in every environment; top queries reviewed in the performance pack's routine.
- Migration lint (squawk) in CI: concurrent index builds, lock timeouts, no blocking `ALTER`s.
- Query-count assertions in tests for hot endpoints (Django `assertNumQueries`, SQLAlchemy event counters, Prisma query logging).
- Alerts: connections used / max, replication lag, slow-query rate, disk growth.

## Sources

- Use The Index, Luke: https://use-the-index-luke.com/
- PostgreSQL, Indexes: https://www.postgresql.org/docs/current/indexes.html
- PostgreSQL, Using EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
- PostgreSQL, pg_stat_statements: https://www.postgresql.org/docs/current/pgstatstatements.html
- HikariCP, About Pool Sizing: https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
- PgBouncer, Features: https://www.pgbouncer.org/features.html
- PostgreSQL, Connection settings (max_connections): https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL, Hot standby: https://www.postgresql.org/docs/current/hot-standby.html
- PostgreSQL, Table partitioning: https://www.postgresql.org/docs/current/ddl-partitioning.html
- Figma, How Figma's databases team lived to tell the scale: https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/
- Notion, Herding elephants: sharding Postgres at Notion: https://www.notion.com/blog/sharding-postgres-at-notion
- GitHub, Partitioning GitHub's relational databases to handle scale: https://github.blog/engineering/infrastructure/partitioning-githubs-relational-databases-scale/
