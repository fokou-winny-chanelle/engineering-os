---
id: data-modeling
title: Data modeling & migrations
kind: phase
mode: both
when: editing schemas, models, migrations or SQL
description: Use for DB schemas, ORM models, migrations or SQL: constraints, money types, indexes, zero-downtime migrations.
globs: ["**/migrations/**", "**/alembic/**", "**/*.sql", "**/models/**", "**/models.py", "**/schema.prisma", "**/prisma/**", "database/migrations/**", "**/entities/**", "**/drizzle/**"]
next: [api-design, backend]
---
# Data modeling & migrations

## Entry
Architecture (consistency rules, bounded contexts) and the requirements' data rules are approved.

## Standards
1. The database enforces invariants. Use NOT NULL, foreign keys, UNIQUE, CHECK constraints and enums/lookup tables. Application checks are an addition, not a substitute.
2. Keys. Use surrogate keys (bigint identity or UUIDv7) plus natural unique keys where they exist. Expose opaque IDs publicly, never sequential ones.
3. Money. Store integer minor units (`bigint`) plus a currency code, or `numeric(p,s)`. Never use float. Decide the rounding rule and write it down. Ledgers are append-only, and balances are derived or reconciled.
4. Time. Use `timestamptz` and store UTC. Add `created_at`/`updated_at` everywhere. Use soft delete only with a reason, and then filter it with partial indexes.
5. Indexes follow queries. Name the query each index serves. Index foreign keys. Check `EXPLAIN (ANALYZE)` on the top queries with realistic row counts.
6. Zero-downtime migrations (expand → migrate → contract):
   - Add the column as nullable, then backfill in batches, then add the constraint as `NOT VALID` and `VALIDATE` it separately.
   - Create indexes `CONCURRENTLY` (outside a transaction).
   - Never rename or drop in the same release that stops using the column.
   - Set `lock_timeout` and `statement_timeout`.
7. Migrations are forward-only in production. Each has a tested rollback plan, which is often a new forward migration. Never edit a migration that has already run anywhere shared.
8. Idempotency and concurrency. Use unique idempotency keys for externally triggered writes. Use optimistic locking (a version column) or `SELECT … FOR UPDATE` for balances, and make the isolation level an explicit choice.
9. PII. Classify columns (public/internal/confidential/PII/secret). Minimise what you store, encrypt sensitive fields, and define retention and deletion jobs.
10. The AI never runs migrations against shared or production DBs. It writes them, and a human applies them.

## Deliverables
- A schema change with its migration file(s), an ERD or notes in `docs/architecture/data.md`, and a data-classification update.
- An ADR for structural changes (new aggregate, partitioning, multi-tenancy model).

## Automated checks
- Migration lint: squawk in core CI; `eos scaffold db-safety` adds a tuned `.squawk.toml`, Alembic SQL lint, money-as-float rules and a schema lint (unindexed FKs).
- Migrate up from an empty DB in CI, and up/down on a copy when supported.
- Schema drift check: models versus migrations (stack pack: e.g. `alembic check`).

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `data/relational-modeling` (constraints, enums, JSONB) · `data/keys-money-time` (ids, money, ledgers, time) · `data/multi-tenancy` (tenant_id, RLS) · `data/history-retention` (soft delete, audit, erasure) · `data/migrations` (expand/contract, lock-safe DDL, ORMs) · `data/postgres-indexing` · `data/postgres-concurrency` (locks, isolation, vacuum) · `architecture/data-consistency` (idempotency, CQRS) · `security/privacy` (PII inventory).

## Exit checklist (Definition of Done)
- [ ] Constraints encode the business invariants. Money is not float. Times are timestamptz.
- [ ] The migration is lint-clean, locks are safe, and the backfill is batched. The release split is noted for expand/contract.
- [ ] Indexes are justified by named queries.
- [ ] PII is classified and retention is defined.
- [ ] Human review (always for money/ledger tables).

## Handoff → api-design / backend
Pass the migration files, data notes and query patterns.

## Stop & escalate
Stop if a migration rewrites or locks a large table, drops data, or changes money columns. Present the plan for approval first.
