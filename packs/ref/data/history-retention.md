---
id: data/history-retention
title: History and retention (soft delete, audit trails, temporal data, deletion and privacy in the schema)
area: data
read_when: adding delete/undo, an audit log, "as of" or validity-period data, retention rules, or erasure requests for personal data
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/rangetypes.html", "https://www.postgresql.org/docs/current/sql-createtable.html", "https://www.postgresql.org/docs/release/18.0/", "https://www.postgresql.org/docs/current/indexes-partial.html", "https://www.postgresql.org/docs/current/ddl-partitioning.html", "https://github.com/pgaudit/pgaudit", "https://gdpr-info.eu/art-5-gdpr/", "https://gdpr-info.eu/art-17-gdpr/", "https://gdpr-info.eu/art-25-gdpr/"]
---
# History and retention

"Keep everything forever" and "delete means `DELETE`" are both wrong defaults. Decide per table: how long each kind of row lives, who may see its history, and what erasure means. Pair this with `security/privacy` (inventory, lawful basis, DPIA).

## Decision guide

**1. Deleting rows: pick per table.**
| Approach | Use when | Costs |
|---|---|---|
| Hard `DELETE` | Default for data with no business or legal reason to keep | Gone (except backups); FKs need a clear `ON DELETE` |
| Soft delete (`deleted_at timestamptz`) | Users expect undo/trash; short grace period before purge | Every query, unique constraint and FK must account for it; deleted personal data is still personal data |
| Archive table / partition | Rows are closed but must be kept (invoices, orders) | A move job; queries on history go to the archive |
| Status (`cancelled`, `closed`) | It is a business state, not a deletion | None; model it as a state |
Soft-delete done right:
- Uniqueness among live rows only: `CREATE UNIQUE INDEX … ON users (tenant_id, lower(email)) WHERE deleted_at IS NULL`; hot indexes partial on `WHERE deleted_at IS NULL`.
- One place applies the filter (a view `active_users`, an ORM default filter); RLS can also hide deleted rows.
- A purge job hard-deletes after a grace period you choose, and the period is written in the retention schedule.
- Children: decide whether they are soft-deleted with the parent or blocked by it.

**2. Audit trail: who changed what, when.**
| Option | Captures | Notes |
|---|---|---|
| App-level audit events (`audit_events`: actor, action, entity, entity_id, before/after JSONB, request id, at) | Business intent ("refund approved") and the user | Best signal; must be written in the same transaction as the change |
| Trigger-based row history (`<table>_history` or one generic table) | Every row change, even from scripts | No actor unless the app sets it per transaction (`set_config('app.actor_id', $1, true)`), more write cost |
| pgAudit extension | Session/object audit logging through the Postgres log | For compliance on statements (who ran DDL, who read a table); not a product feature |
| CDC to a log store (Debezium) | All changes, outside the database | Operationally heavier; good for analytics and cross-system audit |
- Audit tables are append-only: no UPDATE/DELETE grants for the app role; partition by month and set a retention for them too.
- Do not copy secrets or full card data into before/after snapshots; mask personal fields that the auditor does not need.

**3. Temporal data: values valid for a period** (prices, contracts, employee roles, tax rates).
- Store `valid tstzrange` (or `daterange`) with half-open bounds `[from, to)`; "current" is `valid @> now()`.
- Prevent overlaps in the database. Any version: `EXCLUDE USING gist (product_id WITH =, valid WITH &&)` (needs `btree_gist` for the scalar column). PostgreSQL 18: `PRIMARY KEY (product_id, valid WITHOUT OVERLAPS)` and `FOREIGN KEY (…, PERIOD valid) REFERENCES …` for temporal keys; the docs say this is enforced like the equivalent exclusion constraint and expect `btree_gist` for non-range columns.
- Snapshot what was true at transaction time onto the transaction (price on the order line) instead of re-deriving it from the temporal table later.
- System-versioned history ("what did the row look like on 3 March"): history table + trigger, or event sourcing (`architecture/data-consistency`); Postgres has no built-in `SYSTEM_TIME`.

**4. Retention in the schema.**
- Keep a retention schedule (table → purpose → retention period → deletion method) next to the data inventory; GDPR's storage-limitation principle (Art. 5(1)(e)) requires keeping identifying data no longer than necessary, and Art. 25 asks for data protection by design and by default.
- Time-based data (events, logs, audit, sessions): range-partition by month and drop or detach old partitions; the docs note this is far faster than bulk `DELETE` and avoids the VACUUM overhead (`data/postgres-operations`).
- Everything else: a scheduled purge job per table with batched deletes (`DELETE … WHERE id IN (SELECT id … LIMIT 5000)`), its own metrics, and a test.
- Backups age out on their own schedule; document that erased data can survive in backups until they expire and must not be restored into production without re-applying erasures (keep an erasure log of ids).

**5. Personal data and erasure (Art. 17: erase "without undue delay" when a ground applies).**
- Isolate personal data: a `people`/`user_profiles` table holding name, email, phone, address; other tables reference the person by id. Erasure then touches few tables and the rest keeps referential integrity.
- Erase vs anonymise: replace identifying fields with NULL or placeholders and keep non-identifying facts needed by law (invoices often must be kept for tax; check your jurisdiction). Hashing an email is pseudonymisation, not anonymisation.
- Per-subject encryption keys for large or replicated personal payloads: destroying the key makes every copy (including backups and event logs) unreadable. Needs a real key-management design (`security/crypto`).
- Erasure must reach caches, search indexes, object storage, analytics copies, logs and third-party processors; keep the list in the inventory and test the erasure job end to end.
- Mark personal columns in the schema (`COMMENT ON COLUMN users.email IS 'pii:contact'`) so tooling and reviewers can find them.

## Anti-patterns
- Soft delete everywhere by default, with no purge, so "deleted" personal data lives forever.
- Unique constraints that ignore `deleted_at`, blocking re-signup with the same email.
- Audit log written outside the business transaction (lost on crash, or logged for a rolled-back change).
- Overlapping validity periods "prevented" only by application checks.
- Erasure that deletes the users row but leaves names in order snapshots, audit JSON, search and analytics.

## Checks
- [ ] Each table has a retention entry; purge jobs exist and have tests and metrics.
- [ ] Soft-deleted tables use partial unique indexes and a single filtered access path.
- [ ] Validity-period tables have an exclusion constraint or PG 18 `WITHOUT OVERLAPS` key.
- [ ] Erasure test: create a user with orders, audit events and a search document; run erasure; assert no identifying field remains anywhere listed in the inventory.
- [ ] Audit and ledger tables: app role lacks UPDATE/DELETE.

## Sources
- https://www.postgresql.org/docs/current/rangetypes.html (exclusion constraint on ranges)
- https://www.postgresql.org/docs/current/sql-createtable.html (WITHOUT OVERLAPS, PERIOD, btree_gist)
- https://www.postgresql.org/docs/release/18.0/ (temporal constraints)
- https://www.postgresql.org/docs/current/indexes-partial.html
- https://www.postgresql.org/docs/current/ddl-partitioning.html (drop/detach partitions instead of bulk DELETE)
- https://github.com/pgaudit/pgaudit
- https://gdpr-info.eu/art-5-gdpr/ (storage limitation)
- https://gdpr-info.eu/art-17-gdpr/ (erasure without undue delay)
- https://gdpr-info.eu/art-25-gdpr/ (data protection by design and by default)
