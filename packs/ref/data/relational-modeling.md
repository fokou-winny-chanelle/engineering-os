---
id: data/relational-modeling
title: Relational data modelling (normalise, denormalise on purpose, constraints, enums, JSONB)
area: data
read_when: designing tables for a new feature, choosing between a column, a lookup table, an enum or JSONB, or deciding whether to denormalise
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.postgresql.org/docs/current/ddl-constraints.html", "https://www.postgresql.org/docs/current/datatype-enum.html", "https://www.postgresql.org/docs/current/sql-altertype.html", "https://www.postgresql.org/docs/current/datatype-json.html", "https://www.postgresql.org/docs/current/ddl-generated-columns.html", "https://www.postgresql.org/docs/release/18.0/", "https://wiki.postgresql.org/wiki/Don't_Do_This"]
---
# Relational data modelling

Model the business first, then the tables. The database is the last line of defence for invariants: anything the code "always" checks but the schema does not will be violated by a script, a race or a future service. Examples use PostgreSQL 18 (current); most of it applies to any SQL database.

## Decision guide

**1. Start from the domain, not the screens.** List the nouns (entities with identity: Customer, Order), the values (Money, Address, DateRange) and the rules ("an order has at least one line", "an email is unique per tenant"). One table per entity; values become columns (or a few columns); rules become constraints. Name tables and columns in lower snake_case (the wiki's "Don't use upper case table or column names": quoted identifiers must then be quoted forever).

**2. Normalise to third normal form by default.** Each fact lives in one place: no repeating groups (`phone1, phone2` → child table), no column that depends on only part of a key, no column that depends on another non-key column (`city` derived from `postcode`). Duplicated facts drift apart and every write must update all copies.

**3. Denormalise only on purpose, with a named owner of consistency.** Valid reasons: a measured hot read path, history that must not change when the source changes, or a read model for another bounded context. Record which kind it is:
| Kind | Example | How it stays correct |
|---|---|---|
| Snapshot (intended to diverge) | `order_lines.unit_price`, shipping address copied onto the order | Copied at write time, never updated: it is a historical fact |
| Derived, same transaction | `orders.total` from lines | Computed in the same transaction (or a generated column when it only uses the same row) |
| Derived, eventually consistent | search index, counters, reporting tables | Rebuilt from the source by a job or CDC; the source of truth is named |
| Cache | Redis | See `architecture/caching`; never the source of truth |

**4. Put invariants in constraints, in this order of preference:** column type → `NOT NULL` → `CHECK` → `UNIQUE` (including partial unique indexes such as "one active subscription per customer": `CREATE UNIQUE INDEX … ON subscriptions (customer_id) WHERE status = 'active'`) → foreign key → exclusion constraint (no overlapping bookings) → trigger (last resort). Postgres does **not** create an index for the referencing side of a foreign key; add one (see `data/postgres-indexing`). Choose `ON DELETE` deliberately: `RESTRICT` for business records, `CASCADE` only for true parts (order → lines), never cascade into financial or audit rows.

**5. Statuses and other small value sets:**
| Option | Use when | Watch out |
|---|---|---|
| `text` + `CHECK (status IN (...))` | Default. Values change with code releases | Changing the list = drop/add the CHECK (add `NOT VALID`, then `VALIDATE`) |
| Lookup table + FK | Values carry data (label, sort order, active flag) or are edited by admins | One more join; seed it in migrations |
| Postgres `ENUM` | Stable, ordered set; 4 bytes per value | Values cannot be removed or reordered without recreating the type; `ALTER TYPE … ADD VALUE` inside a transaction cannot be used until commit; ORMs and migration tools handle it unevenly |
Model state machines explicitly: allowed transitions in code, plus a `CHECK` for combinations that must never coexist (`status = 'paid'` ⇒ `paid_at IS NOT NULL`).

**6. JSONB: for data you do not query relationally.** Good fits: provider payloads kept for audit, user-defined attributes, sparse settings, documents read and written as a whole. Poor fits: anything you filter, join, sort or constrain on most of the time, values with foreign-key meaning, and money.
- Promote a field you query to a real column (a stored generated column from the JSON is a cheap first step; PG 18 makes virtual the default for generated columns, so say `STORED` when you want it indexed and materialised).
- Index with GIN: the default `jsonb_ops` supports key-exists operators; `jsonb_path_ops` is smaller and supports `@>`, `@?` and `@@` but not key-exists. Or use an expression B-tree index on `(doc->>'field')`.
- Any update rewrites and row-locks the whole row; the docs advise keeping documents to a manageable size to reduce lock contention.
- Validate shape at the boundary (Pydantic/Zod) and keep a `schema_version` key for documents that live long.

**7. Types:** `text` over `varchar(n)` unless the limit is a real rule (then `CHECK (char_length(x) <= n)` is easier to change); `timestamptz` for instants; `date` for calendar days; `numeric` or integer minor units for money (`data/keys-money-time`); `boolean` not `'Y'/'N'`; `citext` or a `lower(email)` unique index for case-insensitive keys.

**8. Many-to-many** gets a join table with its own composite primary key and whatever data belongs to the relationship (role, joined_at). Polymorphic `owner_type/owner_id` columns cannot have foreign keys; prefer one nullable FK per target with a `CHECK (num_nonnulls(a_id, b_id) = 1)`, or separate join tables.

## Examples
```sql
CREATE TABLE orders (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id   bigint NOT NULL REFERENCES tenants (id),
  customer_id bigint NOT NULL REFERENCES customers (id),
  status      text   NOT NULL DEFAULT 'draft'
              CHECK (status IN ('draft', 'placed', 'paid', 'cancelled')),
  currency    char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  total_minor bigint NOT NULL CHECK (total_minor >= 0),
  placed_at   timestamptz,
  paid_at     timestamptz,
  CHECK (status <> 'paid' OR paid_at IS NOT NULL)
);
CREATE INDEX ON orders (customer_id);              -- FK side, not automatic
CREATE INDEX ON orders (tenant_id, status, placed_at DESC);
```
(`char(3)` is fine here because ISO 4217 codes are fixed-length and checked; the wiki's advice is against `char(n)` as a default.)

## Anti-patterns
- Entity-attribute-value tables (`entity_id, key, value text`) for core data: no types, no constraints, painful queries. Use columns, or JSONB for the truly dynamic part.
- "The app validates it" with no constraint; uniqueness checked by `SELECT` then `INSERT` (races: use a unique constraint and handle the violation).
- Copying a customer's name onto every row "for speed" without saying whether it is a snapshot or must follow changes.
- One generic `status` enum shared by unrelated tables; booleans that multiply into impossible combinations (`is_paid`, `is_cancelled`, `is_refunded`).
- Storing lists as comma-separated strings; storing JSON in `text`.

## Checks
- [ ] Every rule in the feature spec maps to a type, constraint or a named test (`eos scaffold db-safety` → `schema_lint.sql` catches unindexed FKs and money as float).
- [ ] Each denormalised column is labelled in a comment or ADR as snapshot / derived (same transaction) / derived (eventual) / cache.
- [ ] Enum changes are reviewed against the ADD VALUE transaction rule; CHECK changes use `NOT VALID` + `VALIDATE`.
- [ ] JSONB columns have a validated shape and no field that is filtered on in hot queries without an index or a promoted column.

## Sources
- https://www.postgresql.org/docs/current/ddl-constraints.html (FK does not index the referencing columns; exclusion constraints)
- https://www.postgresql.org/docs/current/datatype-enum.html (cannot remove or reorder values; 4 bytes)
- https://www.postgresql.org/docs/current/sql-altertype.html (ADD VALUE inside a transaction unusable until commit)
- https://www.postgresql.org/docs/current/datatype-json.html (jsonb_path_ops operators; whole-row lock on update)
- https://www.postgresql.org/docs/current/ddl-generated-columns.html
- https://www.postgresql.org/docs/release/18.0/ (virtual generated columns are the default)
- https://wiki.postgresql.org/wiki/Don't_Do_This (upper-case names, varchar(n), char(n))
