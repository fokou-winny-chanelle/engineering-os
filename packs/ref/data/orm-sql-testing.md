---
id: data/orm-sql-testing
title: ORMs vs SQL, ORM pitfalls (SQLAlchemy 2, Prisma, Drizzle), caching interplay, and test data
area: data
read_when: choosing between ORM and SQL for a query, debugging N+1 or lazy-load errors, configuring ORM pools, writing raw SQL through an ORM, caching DB reads, or setting up database tests and fixtures
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.sqlalchemy.org/en/21/orm/queryguide/relationships.html", "https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html", "https://docs.sqlalchemy.org/en/21/orm/session_basics.html", "https://docs.sqlalchemy.org/en/21/core/pooling.html", "https://docs.sqlalchemy.org/en/21/orm/session_transaction.html", "https://www.prisma.io/docs/orm/v7/prisma-client/setup-and-configuration/databases-connections/connection-pool", "https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries", "https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/pgbouncer", "https://www.prisma.io/docs/orm/middleware/built-in-lints", "https://orm.drizzle.team/docs/sql", "https://orm.drizzle.team/docs/column-types/pg", "https://testcontainers-python.readthedocs.io/en/latest/", "https://node.testcontainers.org/modules/postgresql/", "https://factoryboy.readthedocs.io/en/stable/"]
---
# ORMs, SQL, caching and test data

## Decision guide

**1. ORM or SQL?** Use the ORM for CRUD, simple filters and relations (type safety, migrations, fewer typos). Use SQL (through the ORM's safe raw API or a query file) for reports, window functions, CTEs, bulk operations, upserts with conditions, and anything where you already know the plan you want. Rule: whatever generates it, you must be able to see and `EXPLAIN` the SQL. Turn on SQL logging in dev and count queries in tests.

**2. The N+1 problem** (one query for the list, one per row for its relation) is the most common ORM performance bug.
- SQLAlchemy 2: relationships lazy-load by default. Load deliberately per query: `selectinload()` for collections (the docs call it generally the best strategy for one-to-many/many-to-many), `joinedload()` for many-to-one. Make accidental lazy loads fail: `lazy="raise"` on the relationship or `raiseload("*")` in the query.
- Prisma: fetch relations with `include`/`select` in the same call, not in a loop; the Prisma ORM 8 `lints` middleware blocks risky query shapes (such as a delete without a WHERE) before they run.
- Drizzle: relational queries (`db.query.x.findMany({ with: … })`) or an explicit join; avoid awaiting per-row queries in `map`.
- Guard with a test that asserts the query count of key endpoints (SQLAlchemy event listener, Prisma query event, Drizzle logger).

**3. SQLAlchemy 2 specifics.**
- Async: no implicit IO under asyncio, so lazy loads raise; eager-load, or use `AsyncAttrs` and `await obj.awaitable_attrs.children`.
- `expire_on_commit` defaults to True: after `commit()` attributes are expired and reload on access (an error under async or after the session closes). Use `async_sessionmaker(engine, expire_on_commit=False)` for async apps, or re-query.
- One `Session`/`AsyncSession` per request or unit of work; `AsyncSession` "is not safe for use in concurrent tasks" (no sharing across `asyncio.gather`).
- `create_engine(…, pool_pre_ping=True)` to survive dropped connections; size `pool_size + max_overflow` per process × processes under the database limit (`data/postgres-operations`).
- Money columns: `Numeric(12, 2)` with `Mapped[Decimal]`, never `Float` (semgrep `eos-money-float-orm-python`).

**4. Prisma specifics.**
- Raw SQL: `$queryRaw`/`$executeRaw` with the tagged template parameterise values; `$queryRawUnsafe`/`$executeRawUnsafe` take a raw string and the docs warn of significant SQL injection risk. Never interpolate user input into the Unsafe variants or into `Prisma.raw`.
- Prisma ORM 7 with the `pg` driver adapter: pool `max` defaults to 10 and the acquire/connection timeout to 0 (no timeout), unlike v6 (`num_cpus × 2 + 1`, 10 s pool timeout). Set `max` per instance and a finite `connectionTimeoutMillis`, or a saturated pool waits forever.
- Behind PgBouncer follow Prisma's PgBouncer page (transaction mode, prepared statements); migrations use a direct connection.
- Decimal fields come back as `Decimal` objects (decimal.js); keep them as decimals through the calculation; never `Number(x)` an amount.

**5. Drizzle specifics.**
- The `sql` template parameterises interpolated values (`${id}` → `$1`); `sql.raw()` inserts the string with no escaping: only for trusted identifiers you validated against an allow-list.
- Money: `numeric({ precision, scale })` without `mode: 'number'` (that maps to JS `number`, a float) or `bigint` minor units; never `real`/`doublePrecision` (semgrep `eos-money-float-drizzle`).

**6. Caching with the database** (full patterns in `architecture/caching`).
- Invalidate or update the cache **after** the transaction commits (outbox or post-commit hook); invalidating before commit lets a concurrent reader repopulate the old value.
- Never cache inside an open transaction what another transaction may roll back; never cache authorization decisions longer than the permission change you tolerate.
- Keys include tenant and version (`t:42:product:7:v3`); TTLs on everything; protect hot keys from stampedes (single-flight, early refresh).
- The ORM identity map (Session) is not a cache across requests.

**7. Test data and fixtures.**
- Test against the real database engine and version (Testcontainers starts a throwaway Postgres; `eos scaffold tests-python` ships the fixture). SQLite in tests hides Postgres behaviour (types, locking, JSONB, constraints).
- Apply the real migrations to the test database once per run (this also tests the migrations), then isolate each test: wrap it in a transaction and roll back (SQLAlchemy documents joining a Session into an external transaction for test suites), or truncate between tests when the code under test commits.
- Build data with factories (factory_boy, or small typed builders in TS) that set only what the test cares about; avoid big shared static fixture files that every test depends on.
- Seed data for local dev is code (idempotent script), separate from test factories and from migrations (except true reference data such as currencies).
- **Never copy production data** into dev or test without an approved anonymisation step: it is personal data (`security/privacy`). Generate synthetic data with realistic volume for performance tests.
- Test the database rules themselves: unique/check/FK violations raise, RLS hides other tenants, concurrency tests for counters and balances (`data/postgres-concurrency`).

## Anti-patterns
- Trusting the ORM to "be efficient" without looking at the generated SQL.
- Lazy loading inside templates/serialisers; `expire_on_commit=True` with async code.
- String-building SQL in `$queryRawUnsafe`, `sql.raw`, `text(f"…")`.
- One global ORM session shared across requests or tasks.
- Mocking the database in tests that are meant to test queries; SQLite standing in for Postgres.
- Production dumps on laptops.

## Checks
- [ ] Query-count test on the main list endpoints; SQL logging available in dev.
- [ ] Semgrep: `eos-js-sql-template-literal` (security scaffold) and `eos-money-float-*` (db-safety scaffold) pass.
- [ ] ORM pool sizes × instances documented and under the database or pooler limit; Prisma v7 timeouts set.
- [ ] Tests run against Postgres (Testcontainers or CI service) with migrations applied; no production data in fixtures.

## Sources
- https://docs.sqlalchemy.org/en/21/orm/queryguide/relationships.html (lazy by default; selectinload; raise loading)
- https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html (no implicit IO; expire_on_commit=False; AsyncAttrs; not safe in concurrent tasks)
- https://docs.sqlalchemy.org/en/21/orm/session_basics.html (expire_on_commit)
- https://docs.sqlalchemy.org/en/21/core/pooling.html (pool_pre_ping)
- https://docs.sqlalchemy.org/en/21/orm/session_transaction.html (joining a Session into an external transaction for tests)
- https://www.prisma.io/docs/orm/v7/prisma-client/setup-and-configuration/databases-connections/connection-pool (v6 vs v7 pg adapter defaults)
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries (Unsafe variants and SQL injection)
- https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/pgbouncer
- https://www.prisma.io/docs/orm/middleware/built-in-lints
- https://orm.drizzle.team/docs/sql (sql template parameterises; sql.raw unescaped)
- https://orm.drizzle.team/docs/column-types/pg (numeric modes; real, double precision)
- https://testcontainers-python.readthedocs.io/en/latest/
- https://node.testcontainers.org/modules/postgresql/
- https://factoryboy.readthedocs.io/en/stable/
