---
id: data/migrations
title: Zero-downtime schema migrations (expand/contract, lock-safe DDL, backfills, squawk; Alembic, Prisma, Drizzle, Laravel)
area: data
read_when: writing or reviewing a migration on a live database, renaming/retyping columns, adding constraints or indexes, backfills, migration lint in CI
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.postgresql.org/docs/current/sql-altertable.html", "https://www.postgresql.org/docs/current/sql-createindex.html", "https://www.postgresql.org/docs/current/runtime-config-client.html", "https://squawkhq.com/docs/cli", "https://squawkhq.com/docs/safe_migrations", "https://squawkhq.com/docs/web-frameworks", "https://alembic.sqlalchemy.org/en/latest/offline.html", "https://alembic.sqlalchemy.org/en/latest/api/runtime.html", "https://alembic.sqlalchemy.org/en/latest/autogenerate.html", "https://www.prisma.io/docs/orm/migrations/applying-a-migration", "https://www.prisma.io/docs/orm/prisma-migrate/workflows/customizing-migrations", "https://www.prisma.io/docs/orm/v7/prisma-migrate/workflows/customizing-migrations", "https://orm.drizzle.team/docs/drizzle-kit-push", "https://orm.drizzle.team/docs/drizzle-kit-generate", "https://laravel.com/docs/12.x/migrations", "https://github.com/ankane/strong_migrations"]
---
# Zero-downtime schema migrations

During a deploy, old and new app versions run at the same time against one schema. Every migration must work with both, and no statement may hold a blocking lock for long. Lint catches known-dangerous statements but cannot see table sizes or traffic: a human still reviews.

## Decision guide

**1. Expand → migrate → contract.** 
1. *Expand*: add the new column/table/index, nullable or with a constant default. Deploy.
2. *Write both*: the app writes old and new; reads stay on old. Deploy.
3. *Backfill* old rows in batches (below).
4. *Switch reads* to new; keep writing both. Deploy and watch.
5. *Contract*: stop writing old; later, a separate migration drops it (after the ORM no longer maps it).
Renames are expand/contract too (add new, dual write, backfill, switch, drop); a plain `RENAME COLUMN` breaks the running old version (squawk `renaming-column`, `renaming-table`).

**2. Lock-safe DDL (PostgreSQL 11+ unless noted).**
| Change | Safe way |
|---|---|
| Add column | Nullable, or `DEFAULT` with a non-volatile value (no rewrite). Volatile defaults (`clock_timestamp()`), stored generated and identity columns rewrite the table |
| Add NOT NULL to existing column | `ADD CONSTRAINT c CHECK (col IS NOT NULL) NOT VALID`; `VALIDATE CONSTRAINT c`; `ALTER COLUMN col SET NOT NULL` (skips the scan because a valid CHECK proves it); drop the CHECK. PG 18: `ADD CONSTRAINT c NOT NULL col NOT VALID` then `VALIDATE CONSTRAINT c` |
| Add foreign key | `ADD CONSTRAINT … FOREIGN KEY … NOT VALID`, then `VALIDATE CONSTRAINT` (only SHARE UPDATE EXCLUSIVE on the table, ROW SHARE on the referenced one). Index the FK column concurrently first |
| Add CHECK | `NOT VALID` + `VALIDATE` (squawk `constraint-missing-not-valid`) |
| Add index | `CREATE INDEX CONCURRENTLY`, outside a transaction; drop the INVALID leftover if it fails |
| Add unique constraint | Unique index concurrently, then `ADD CONSTRAINT … UNIQUE USING INDEX` |
| Change type | New column + backfill + switch. In-place only when binary-coercible, which skips the rewrite (the docs: `text` ↔ `varchar` needs no index rebuild without a collation change) |
| Drop column | Remove from code and ORM model first, deploy, then drop |
| Add enum value | `ALTER TYPE … ADD VALUE` cannot be used until committed; run it in its own migration/transaction (Alembic `autocommit_block()`) |

**3. Always set timeouts, and retry.** A waiting `ACCESS EXCLUSIVE` request blocks all later queries on that table (`data/postgres-concurrency`). Run migrations with a short `lock_timeout` (squawk suggests about 1 second) and a `statement_timeout` (about 5 seconds), and retry the migration when the lock times out. Set them on the migration connection (`PGOPTIONS='-c lock_timeout=1s -c statement_timeout=5s'`, Alembic `connect_args`) or as `SET` statements at the top of SQL files (squawk `require-lock-timeout`, `require-statement-timeout`). Long `VALIDATE` and concurrent index builds need a larger statement timeout for that step only.

**4. Backfills are not migrations.** Run them as an idempotent job or script, in batches by primary key range, committing each batch, with a pause and progress log:
```sql
UPDATE orders SET total_minor = round(total * 100)
WHERE id >= $1 AND id < $1 + 5000 AND total_minor IS NULL;
```
Watch replication lag and lock waits; make the batch size a setting; never backfill in the DDL transaction.

**5. Order of deploys.** Schema changes that old code tolerates go first (expand); code that needs them follows; destructive changes go last, in a later release. Make migrations forward-only in production: write the compensating migration instead of relying on `downgrade`/`down`.

**6. Tool specifics.**
- **Alembic (SQLAlchemy).** Autogenerate is "not intended to be perfect": always review and edit; `alembic check` fails CI when models and migrations disagree. `alembic upgrade <from>:<to> --sql` renders a revision as SQL without a database (the `start:end` form only works offline) → pipe into squawk (`scripts/db/alembic_squawk.py` from `eos scaffold db-safety` does this per changed revision). Use `op.create_index(…, postgresql_concurrently=True)` inside `with op.get_context().autocommit_block():`; this commits the preceding work, so set `transaction_per_migration=True` in `env.py`. Use `sa.Identity()` for new PKs (a bare `BigInteger` PK renders as `BIGSERIAL`; squawk `prefer-identity` flags it).
- **Prisma ORM 8** (docs default; on npm the `prisma` CLI is 8.0.0-rc.22 and `@prisma/client` 7.10.0 as of 2026-10-10): you edit `migrations/app/<dir>/migration.ts` and recompile it; `npx prisma migration show <dir>` previews the SQL; `npx prisma migration check` detects hand-edited or deleted migrations; `npx prisma db migrate` (replaces `migrate deploy`) applies them. One `db migrate` run on PostgreSQL is one transaction, so `CREATE INDEX CONCURRENTLY` cannot run there (build big indexes out of band), and destructive operations are applied without a prompt: review `migration show` output in the PR.
- **Prisma ORM 7**: `prisma migrate dev --create-only` to get the SQL, edit `migration.sql` (expand/contract, `NOT VALID`), then `prisma migrate deploy` in CI/CD. `prisma/migrations/*/migration.sql` files are linted by squawk in the eos core CI job.
- **Drizzle**: `drizzle-kit generate` writes SQL to `drizzle/<timestamp>_<name>/migration.sql`, `drizzle-kit migrate` applies unapplied ones and logs them; `--custom` creates an empty SQL migration for backfills or hand-written DDL. `drizzle-kit push` applies schema diffs directly (no migration files; `--force` auto-accepts data-loss statements): prototyping and throwaway databases only.
- **Laravel**: `php artisan migrate --pretend` prints the SQL for review (feed it to squawk); `--force` is required in production; `--isolated` takes a cache lock so only one server migrates.

**7. Lint in CI.** squawk 2.68.0 runs on changed `migrations/**.sql` and `drizzle/**.sql` in the eos core workflow. `eos scaffold db-safety` adds a tuned `.squawk.toml` (`assume_in_transaction = true`; a file that runs outside a transaction starts with `-- squawk-disable-assume-in-transaction`), the Alembic SQL lint, and a schema lint on a migrated database. Suppress a reviewed finding with `-- squawk-ignore <rule>` and a reason.

## Anti-patterns
- `ALTER TABLE … ADD COLUMN … NOT NULL DEFAULT gen_random_uuid()` on a big table (volatile default rewrites it).
- Renaming or dropping a column in the release that stops using it; backfilling inside the DDL transaction.
- No `lock_timeout`; "it was fast in staging".
- Trusting autogenerated migrations (Alembic, Prisma, Drizzle) without reading the SQL.

## Checks
- [ ] squawk passes on every changed migration (core CI job) with the scaffolded `.squawk.toml`; Alembic projects run `alembic_squawk.py` and `alembic check`.
- [ ] Migration PRs state the expand/contract step they belong to and which release removes the old path.
- [ ] Migration runner sets `lock_timeout`/`statement_timeout` and retries on lock timeout.
- [ ] Backfills are separate, batched, idempotent jobs with progress logs.
- [ ] `schema_lint.sql` passes on the migrated schema (db-safety workflow).

## Sources
- https://www.postgresql.org/docs/current/sql-altertable.html (rewrites; NOT VALID/VALIDATE; SET NOT NULL via CHECK; type changes)
- https://www.postgresql.org/docs/current/sql-createindex.html (CONCURRENTLY rules; INVALID index)
- https://www.postgresql.org/docs/current/runtime-config-client.html (lock_timeout, statement_timeout)
- https://squawkhq.com/docs/cli (config keys; squawk-ignore)
- https://squawkhq.com/docs/safe_migrations (timeouts, retry)
- https://squawkhq.com/docs/web-frameworks (Alembic `--sql` into squawk)
- https://alembic.sqlalchemy.org/en/latest/offline.html (start:end offline only)
- https://alembic.sqlalchemy.org/en/latest/api/runtime.html (autocommit_block commits the preceding transaction)
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html (alembic check; not intended to be perfect)
- https://www.prisma.io/docs/orm/migrations/applying-a-migration (db migrate; no prompt for destructive ops)
- https://www.prisma.io/docs/orm/prisma-migrate/workflows/customizing-migrations (one transaction)
- https://www.prisma.io/docs/orm/v7/prisma-migrate/workflows/customizing-migrations (--create-only)
- https://orm.drizzle.team/docs/drizzle-kit-push (--force accepts data-loss statements)
- https://orm.drizzle.team/docs/drizzle-kit-generate (--custom; folder layout)
- https://laravel.com/docs/12.x/migrations (--pretend, --force, --isolated)
- https://github.com/ankane/strong_migrations (same dangerous-operation list for Rails)
