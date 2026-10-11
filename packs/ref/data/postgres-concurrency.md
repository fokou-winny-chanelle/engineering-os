---
id: data/postgres-concurrency
title: PostgreSQL concurrency (locks and the lock queue, isolation levels and anomalies, MVCC, vacuum, bloat, wraparound)
area: data
read_when: debugging blocked or deadlocked queries, choosing an isolation level, preventing lost updates or double booking, or tuning autovacuum and bloat
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/explicit-locking.html", "https://www.postgresql.org/docs/current/transaction-iso.html", "https://www.postgresql.org/docs/current/mvcc-intro.html", "https://www.postgresql.org/docs/current/routine-vacuuming.html", "https://www.postgresql.org/docs/current/runtime-config-autovacuum.html", "https://www.postgresql.org/docs/current/sql-vacuum.html", "https://www.postgresql.org/docs/current/storage-hot.html", "https://www.postgresql.org/docs/current/runtime-config-client.html", "https://www.postgresql.org/docs/current/functions-admin.html", "https://www.citusdata.com/blog/2018/02/22/seven-tips-for-dealing-with-postgres-locks/", "https://gocardless.com/blog/zero-downtime-postgres-migrations-the-hard-parts/", "https://reorg.github.io/pg_repack/", "https://www.postgresql.org/docs/current/errcodes-appendix.html", "https://www.postgresql.org/docs/current/runtime-config-logging.html"]
---
# PostgreSQL concurrency

`architecture/data-consistency` gives the four standard fixes for races (atomic update, `FOR UPDATE`, version column, SERIALIZABLE + retry). This ref explains the machinery underneath so you can pick correctly and debug when it goes wrong.

## Decision guide

**1. MVCC in one paragraph.** Every `UPDATE` writes a new row version and leaves the old one as a dead tuple; readers see a snapshot. So reading never blocks writing and writing never blocks reading. Costs: dead tuples must be vacuumed, long-running transactions keep old versions alive for everyone, and transaction ids (32-bit) must be frozen before they wrap.

**2. Table locks you will meet.**
| Mode | Taken by | Blocks |
|---|---|---|
| ACCESS SHARE | `SELECT` | Only ACCESS EXCLUSIVE |
| ROW EXCLUSIVE | `INSERT`, `UPDATE`, `DELETE`, `MERGE` | SHARE and stronger |
| SHARE UPDATE EXCLUSIVE | `VACUUM`, `ANALYZE`, `CREATE INDEX CONCURRENTLY`, `VALIDATE CONSTRAINT` | Other schema changes and vacuums, not reads/writes |
| SHARE | `CREATE INDEX` (plain) | Writes |
| SHARE ROW EXCLUSIVE | `ADD FOREIGN KEY` (on both tables) | Writes |
| ACCESS EXCLUSIVE | Most `ALTER TABLE`, `DROP`, `TRUNCATE`, `VACUUM FULL`, `REINDEX` (plain), `REFRESH MATERIALIZED VIEW` | Everything, including `SELECT` |
**The lock queue is the real danger.** A lock request that cannot be granted waits in a queue, and later requests that conflict with it queue behind it. So an `ALTER TABLE` waiting for ACCESS EXCLUSIVE behind one slow `SELECT` blocks every new query on that table until it gets its turn: a "fast" migration takes the site down. Fix: `SET lock_timeout = '2s'` (session or transaction, never globally in `postgresql.conf`, per the docs) and retry the migration (`data/migrations`).

**3. Row locks.** `UPDATE`/`DELETE` lock the rows they change until commit. Explicit: `SELECT … FOR UPDATE` (exclusive), `FOR NO KEY UPDATE` (what plain `UPDATE` takes; does not block FK checks), `FOR SHARE`, `FOR KEY SHARE`. Modifiers: `NOWAIT` (error instead of waiting) and `SKIP LOCKED` (job queues). Keep the locked section short; never call external services while holding row locks.

**4. Isolation levels and anomalies** (PostgreSQL implements three; Read Uncommitted behaves like Read Committed):
| Level | Dirty read | Non-repeatable read | Phantom | Serialization anomaly | Use |
|---|---|---|---|---|---|
| Read Committed (default) | No | Possible | Possible | Possible | Most OLTP, with atomic updates or row locks |
| Repeatable Read (snapshot) | No | No | No (in PG) | Possible (write skew) | Consistent reports, multi-statement reads |
| Serializable (SSI) | No | No | No | No | Invariants across rows ("at most N on call", "no overlapping booking" without a constraint) |
- Classic bugs at Read Committed: **lost update** (two requests read balance 100, both write 100 − x) → use `UPDATE … SET balance = balance - $1 WHERE … AND balance >= $1`, or `FOR UPDATE`; **write skew** (two doctors both go off call because each saw the other on call) → Serializable, a constraint, or lock a shared parent row.
- Repeatable Read and Serializable abort with SQLSTATE `40001` (`could not serialize access …`); the docs require the application to retry the **whole** transaction. Put the retry loop in one helper (bounded attempts, jitter), keep transactions short and idempotent.
- Prefer constraints when they can express the rule (unique, exclusion, CHECK): they work at any isolation level.

**5. Deadlocks.** Postgres detects them and aborts one transaction (which one is unpredictable). Prevent by touching rows in a consistent order (sort ids before `FOR UPDATE`), keeping transactions short, and retrying on `40P01`. Deadlocks are always logged; `log_lock_waits = on` (default off) also logs waits longer than `deadlock_timeout`.

**6. Advisory locks** for app-defined mutual exclusion (one cron runner, one migration at a time): prefer transaction-level `pg_advisory_xact_lock(key)`; session-level locks survive rollback and break behind PgBouncer transaction pooling. They are a coordination tool, not a substitute for constraints.

**7. Timeouts that protect everyone:** `lock_timeout` (migrations), `statement_timeout` (per role/request), `idle_in_transaction_session_timeout` (default 0 = off; set it, because an idle open transaction holds locks and stops vacuum), `transaction_timeout` (PG 17+).

**8. Vacuum, bloat and wraparound.**
- Autovacuum triggers a table vacuum after `autovacuum_vacuum_threshold` (50) + `autovacuum_vacuum_scale_factor` (0.2) × rows dead tuples, capped by `autovacuum_vacuum_max_threshold` (100,000,000, PG 18); analyze after 50 + 0.1 × rows changes. On big tables 20% is a lot of garbage: lower the scale factor per table (`ALTER TABLE events SET (autovacuum_vacuum_scale_factor = 0.02)`).
- Watch `pg_stat_user_tables.n_dead_tup`, `last_autovacuum`, and the oldest transaction in `pg_stat_activity` (`xact_start`). The usual cause of runaway bloat is a long transaction, an abandoned replication slot, or a forgotten prepared transaction, not autovacuum settings.
- Plain `VACUUM` makes space reusable but rarely returns it to the OS. `VACUUM FULL` rewrites the table under ACCESS EXCLUSIVE (an outage for big tables); use pg_repack, which works online without holding an exclusive lock during processing.
- HOT updates (no indexed column changed, room on the page) avoid index writes and reduce bloat; see `data/postgres-indexing`.
- **Wraparound:** transaction ids are 32-bit; every table must be vacuumed (frozen) at least once every two billion transactions or the docs warn of catastrophic data loss. Autovacuum forces a freeze when `relfrozenxid` age passes `autovacuum_freeze_max_age` (200 million). Alert on `age(datfrozenxid)` well before that; never disable autovacuum.

## Anti-patterns
- `SELECT` then `UPDATE` with a value computed in the app, at Read Committed, with no lock or condition.
- Long transactions wrapping HTTP calls, file uploads or user think-time.
- Running `ALTER TABLE` on a busy table with no `lock_timeout`.
- Switching everything to Serializable without a retry helper; retrying only the failed statement.
- `VACUUM FULL` in business hours; turning autovacuum off "because it is slow".

## Checks
- [ ] Money/inventory/booking code has a concurrency test (two parallel requests) proving no lost update or double booking.
- [ ] One retry helper handles `40001`/`40P01`; transactions using RR/Serializable go through it.
- [ ] Roles have `statement_timeout` and `idle_in_transaction_session_timeout`; migrations set `lock_timeout` (squawk `require-lock-timeout`).
- [ ] Monitoring: dead tuples per table, oldest transaction age, `age(datfrozenxid)`, replication slot lag, lock waits.

## Sources
- https://www.postgresql.org/docs/current/explicit-locking.html (lock modes; row locks; deadlocks; advisory locks)
- https://www.postgresql.org/docs/current/transaction-iso.html (anomaly table; 40001 retries; predicate locks)
- https://www.postgresql.org/docs/current/mvcc-intro.html (reading never blocks writing)
- https://www.postgresql.org/docs/current/routine-vacuuming.html (wraparound; two billion transactions)
- https://www.postgresql.org/docs/current/runtime-config-autovacuum.html (defaults 50, 0.2, 0.1, 200 million, 100,000,000)
- https://www.postgresql.org/docs/current/sql-vacuum.html (VACUUM FULL takes ACCESS EXCLUSIVE)
- https://www.postgresql.org/docs/current/storage-hot.html
- https://www.postgresql.org/docs/current/runtime-config-client.html (lock_timeout not in postgresql.conf; idle_in_transaction default 0; transaction_timeout)
- https://www.postgresql.org/docs/current/functions-admin.html (advisory lock functions)
- https://www.citusdata.com/blog/2018/02/22/seven-tips-for-dealing-with-postgres-locks/ (lock queues, lock timeouts)
- https://gocardless.com/blog/zero-downtime-postgres-migrations-the-hard-parts/ (queued ACCESS EXCLUSIVE blocks later queries)
- https://reorg.github.io/pg_repack/ (online, no exclusive lock while processing)
- https://www.postgresql.org/docs/current/errcodes-appendix.html (40001 serialization_failure, 40P01 deadlock_detected)
- https://www.postgresql.org/docs/current/runtime-config-logging.html (log_lock_waits, default off)
