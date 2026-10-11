---
id: data/postgres-operations
title: Running PostgreSQL (PgBouncer, partitioning, replicas, backups and PITR, upgrades, extensions)
area: data
read_when: setting up pooling, partitioning a growing table, adding replicas, designing backups and restores, planning a major-version upgrade, or choosing extensions
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.pgbouncer.org/config.html", "https://www.pgbouncer.org/features.html", "https://www.pgbouncer.org/faq.html", "https://www.postgresql.org/docs/current/ddl-partitioning.html", "https://github.com/pgpartman/pg_partman", "https://www.postgresql.org/docs/current/warm-standby.html", "https://www.postgresql.org/docs/current/hot-standby.html", "https://www.postgresql.org/docs/current/logical-replication-restrictions.html", "https://www.postgresql.org/docs/current/continuous-archiving.html", "https://www.postgresql.org/docs/current/app-pgbasebackup.html", "https://www.postgresql.org/docs/current/app-pgdump.html", "https://pgbackrest.org/", "https://www.postgresql.org/docs/current/pgupgrade.html", "https://www.postgresql.org/support/versioning/", "https://www.postgresql.org/docs/release/18.0/", "https://www.postgresql.org/docs/current/pgstatstatements.html"]
---
# Running PostgreSQL

On a managed service (RDS, Cloud SQL, Azure, Supabase, Neon, Prisma Postgres…) the provider runs much of this, but you still own pool sizing, restore tests, upgrade timing and the extension list. Capacity steps (when to add replicas or shard) are in `architecture/database-scaling`.

## Decision guide

**1. Connection pooling with PgBouncer.**
- Modes: `session` (default; server connection held until the client disconnects; all features work), `transaction` (released at commit; the useful one for many app workers or serverless), `statement` (multi-statement transactions disallowed).
- Transaction mode never supports: session `SET`/`RESET`, `LISTEN`, SQL `PREPARE`/`DEALLOCATE`, `WITH HOLD` cursors, `PRESERVE/DELETE ROWS` temp tables, `LOAD`, session-level advisory locks. Use `set_config(…, true)` and `pg_advisory_xact_lock` instead.
- Protocol-level prepared statements work in transaction mode since PgBouncer 1.21.0 when `max_prepared_statements` is non-zero (default 200 in current config docs). SQL-level `PREPARE` is still not tracked. Check your driver and ORM docs (Prisma has a PgBouncer page; asyncpg and psycopg have their own settings).
- Defaults to size consciously: `default_pool_size` 20 per user/database pair; `max_client_conn` needs OS file-descriptor headroom. Total server connections across poolers and direct clients must stay under `max_connections` (typically 100 by default) minus admin and replication headroom.
- Migrations, `LISTEN/NOTIFY` consumers and long admin sessions connect directly (or through a session-mode pool), not through the transaction pool.

**2. Partitioning** (declarative: range, list or hash).
- Worth it for very large tables, mostly time-series or append-heavy (events, audit, ledger history), and for retention: dropping or detaching a partition is far faster than a bulk `DELETE` and avoids its vacuum cost.
- Queries must filter on the partition key so the planner can prune partitions; check with EXPLAIN. Unique and primary keys must include every partition-key column (so a global unique `id` alone is impossible; use `(id, created_at)` or enforce uniqueness elsewhere).
- Create future partitions ahead of time and attach/detach with care: `DETACH PARTITION … CONCURRENTLY` (squawk `require-concurrent-partition-detach`). pg_partman automates time- and number-based partition sets on top of built-in declarative partitioning.
- Converting an existing big table is a project: new partitioned table, dual writes or batched copy, swap names in a short lock window.

**3. Replicas.**
- Physical streaming replication is asynchronous by default: a primary crash can lose recently committed transactions. Synchronous replication (`synchronous_standby_names`, `synchronous_commit`) waits for standby confirmation and adds commit latency; use it where losing a committed payment is unacceptable.
- Hot standby reads: queries can be cancelled when they conflict with WAL replay (`max_standby_streaming_delay`); `hot_standby_feedback = on` avoids cleanup conflicts but delays vacuum on the primary and can bloat it.
- Route only lag-tolerant reads to replicas; read-your-writes goes to the primary (`architecture/database-scaling`).
- Logical replication (publications/subscriptions) copies chosen tables between versions or to other systems, but does not replicate DDL or sequence values: apply additive schema changes to the subscriber first and fix sequences before switching over.

**4. Backups and point-in-time recovery.** Define RPO (data you can lose) and RTO (time to restore) first; they decide the design.
- `pg_dump` makes consistent logical exports without blocking users, but the docs say it is generally not the right choice for regular backups except in simple cases (slow restore, no PITR). Use it for migrations between systems and small databases.
- Physical base backup (`pg_basebackup`, or pgBackRest for parallel, compressed, full/differential/incremental backups with retention) + continuous WAL archiving = restore to any moment since the base backup (PITR).
- PostgreSQL 17+ `pg_basebackup --incremental=<manifest of an earlier backup>`; restoring needs the incremental plus every earlier backup it depends on, combined with `pg_combinebackup`.
- **Untested backups are not backups.** Schedule an automated restore to a scratch instance (weekly or monthly), run a sanity query, record the time taken against the RTO. Keep at least one copy in another account/region, protected from deletion by the production credentials.
- Managed services: know the retention window, whether PITR is on, and how long a restore takes for your size; practise it once.

**5. Upgrades.**
- Minor releases (at least every three months) contain bug, security and corruption fixes; the project recommends always running the current minor. Automate them.
- Major versions are supported for 5 years (PG 18 until 14 November 2030, 17 until 8 November 2029). Plan a major upgrade per year or two, not at end-of-life.
- `pg_upgrade` (`--link` for speed; PG 18 now keeps planner statistics, earlier versions need `ANALYZE` afterwards) or logical replication for near-zero downtime; rehearse on a restored copy, read the release notes' migration section, and test the app's queries for plan changes.

**6. Extensions.** Add deliberately (each is code running in your database, and managed providers allow a fixed list). Common, worth knowing: `pg_stat_statements` (needs `shared_preload_libraries`), `auto_explain`, `pg_trgm`, `btree_gist`, `citext`, `pgcrypto`, `pgvector`, PostGIS, `pg_partman`, `pgaudit`, `pg_repack`. Create them in migrations (`CREATE EXTENSION IF NOT EXISTS`), pin versions, and include them in upgrade rehearsals.

**7. Monitor at least:** connections vs max (by state), longest transaction, replication lag and slot retention, dead tuples and last autovacuum per big table, `age(datfrozenxid)`, disk growth, cache hit ratio trend, slow queries from `pg_stat_statements`, failed backups and last successful restore test.

## Anti-patterns
- One huge connection pool per app instance multiplied by autoscaling, no pooler.
- Session-only features (SET, LISTEN, session advisory locks) behind transaction pooling.
- Partitioning a table that fits comfortably in memory "for performance" (the docs suggest it when a table would exceed physical memory); partitioning by a key queries do not filter on.
- Backups never restored; backups stored in the same account with the same credentials as production.
- Staying on an end-of-life major version; skipping minor releases.
- Abandoned logical replication slots (they retain WAL until the disk fills).

## Checks
- [ ] Runbook: pool sizes per service, sum vs `max_connections`, which clients bypass the pooler.
- [ ] Automated restore test with recorded duration; alert if it fails or is older than its schedule.
- [ ] Monitoring covers the list in step 7; alerts on replication slot lag and `age(datfrozenxid)`.
- [ ] Upgrade calendar: current minor within a month of release; next major planned before EOL.
- [ ] Extensions listed in an ADR or the README with versions.

## Sources
- https://www.pgbouncer.org/config.html (pool_mode, default_pool_size 20, max_prepared_statements default 200)
- https://www.pgbouncer.org/features.html (transaction pooling feature table)
- https://www.pgbouncer.org/faq.html (prepared statements in transaction mode since 1.21.0)
- https://www.postgresql.org/docs/current/ddl-partitioning.html (range/list/hash; pruning; unique must include the key; drop/detach vs DELETE)
- https://github.com/pgpartman/pg_partman
- https://www.postgresql.org/docs/current/warm-standby.html (asynchronous by default; synchronous replication)
- https://www.postgresql.org/docs/current/hot-standby.html (query conflicts; hot_standby_feedback)
- https://www.postgresql.org/docs/current/logical-replication-restrictions.html (no DDL, no sequence data)
- https://www.postgresql.org/docs/current/continuous-archiving.html (PITR; incremental backups need earlier backups)
- https://www.postgresql.org/docs/current/app-pgbasebackup.html (--incremental)
- https://www.postgresql.org/docs/current/app-pgdump.html (not for regular backups except simple cases)
- https://pgbackrest.org/
- https://www.postgresql.org/docs/current/pgupgrade.html (--link)
- https://www.postgresql.org/support/versioning/ (minor releases at least every three months; 5-year support; EOL dates)
- https://www.postgresql.org/docs/release/18.0/ (pg_upgrade retains statistics)
- https://www.postgresql.org/docs/current/pgstatstatements.html
