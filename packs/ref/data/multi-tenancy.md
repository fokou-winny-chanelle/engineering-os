---
id: data/multi-tenancy
title: Multi-tenant data (shared schema + tenant_id + RLS, schema per tenant, database per tenant)
area: data
read_when: building SaaS where several customers (organisations, schools, shops) share one deployment, or adding tenant isolation to an existing schema
verified: 2026-10-10
revisit_days: 365
sources: ["https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/silo-pool-and-bridge-models.html", "https://www.postgresql.org/docs/current/ddl-rowsecurity.html", "https://www.postgresql.org/docs/current/functions-admin.html", "https://www.pgbouncer.org/features.html", "https://www.postgresql.org/docs/current/ddl-partitioning.html"]
---
# Multi-tenant data

Cross-tenant data leaks are the worst bug a SaaS can ship, and they come from one missing `WHERE tenant_id = ?`. Pick a model that makes the safe query the easy one, and back it with a second layer the code cannot forget.

## Decision guide

**1. Choose the isolation model** (AWS SaaS Lens vocabulary: *pool* = shared resources, *silo* = dedicated resources, *bridge* = a mix):
| Model | Isolation | Cost and operations | Pick when |
|---|---|---|---|
| Shared tables, `tenant_id` column (pool) | Logical: query filters + RLS | One schema, one migration run, cheapest | Default for B2B/B2C SaaS with many small tenants |
| Schema per tenant | Namespaces in one database | Migrations run N times; catalog bloat with thousands of schemas; pooling per schema is awkward | Few tenants (tens to low hundreds) needing per-tenant extensions or restores |
| Database (or cluster) per tenant (silo) | Strong; per-tenant backup, restore, region, encryption keys | N databases to migrate, monitor and pay for | Regulated or large customers, data-residency contracts, noisy neighbours |
| Hybrid (bridge) | Pool for most, silo for a few | Two code paths for routing | Enterprise tier on top of a pooled product |
Write the choice and the trigger for moving a tenant to a silo (size, contract, residency) in an ADR.

**2. Pooled model rules.**
- `tenant_id NOT NULL` on every tenant-owned table, including join and child tables (do not rely on reaching the tenant through a parent join).
- Lead composite keys and indexes with `tenant_id`: `UNIQUE (tenant_id, email)`, `INDEX (tenant_id, created_at DESC)`.
- Make cross-tenant references impossible with composite foreign keys: parent `UNIQUE (tenant_id, id)`, child `FOREIGN KEY (tenant_id, customer_id) REFERENCES customers (tenant_id, id)`.
- Resolve the tenant once per request from the authenticated principal (token claim, session), never from a client-supplied header or body field alone; reject requests where they disagree.
- One data-access layer adds the tenant filter (repository base class, ORM global filter, Prisma/Drizzle helper). Raw SQL goes through a reviewed helper.
- Background jobs, exports and caches carry the tenant explicitly: cache keys start with `t:{tenant_id}:`; queue payloads include it; log lines include it.

**3. Row-level security as the second layer** (Postgres):
```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;      -- owners bypass RLS otherwise
CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id')::bigint)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::bigint);
```
Per transaction, from the app: `SELECT set_config('app.tenant_id', $1, true);` (`true` = only for the current transaction).
- Superusers and roles with `BYPASSRLS` always bypass RLS; table owners do too unless `FORCE ROW LEVEL SECURITY`. Run the app as a dedicated non-owner role; run migrations as the owner.
- With RLS enabled and no policy, the default is deny (no rows). `current_setting('app.tenant_id')` raises an error when the setting was never defined in the session, which fails closed (after an earlier transaction-local set it reads as an empty string, and the `::bigint` cast fails, also closed); the two-argument `current_setting(name, true)` returns NULL instead (and NULL = x is never true, also closed).
- A policy's `USING` also acts as `WITH CHECK` when none is given; spell both out for clarity.
- PgBouncer transaction pooling: session `SET` is never supported, so use transaction-local `set_config(..., true)` inside an explicit transaction for every request; a session-level setting would leak to the next client on that server connection.
- RLS policies run per row; keep them simple equality on an indexed column. Test query plans with RLS on.
- Admin/support tooling that must see all tenants uses a separate role and is audited, not a flag in the app role.

**4. Silo model rules.** A tenant directory (tenant → connection/secret/region) in a control-plane database; migrations run by a job that iterates tenants with a concurrency limit and records per-tenant schema versions; one tenant's failed migration must not block the rest; every tenant database gets the same backups, monitoring and upgrade cadence.

**5. Size and noisy neighbours.** Track rows and query time per tenant (`pg_stat_statements` cannot see tenants; add `tenant_id` to logs and traces). Big tenants: per-tenant rate limits and job concurrency; hash or list partitioning by `tenant_id` only when a single table outgrows the box (partition keys must be part of every unique constraint); moving a whale to a silo is easier when every table already has `tenant_id`.

**6. Offboarding and residency.** Deleting a tenant must reach every table, cache, search index, object storage prefix, analytics copy and backup policy (`data/history-retention`). Residency requirements usually force a silo (or a regional pool), so ask early.

## Anti-patterns
- `tenant_id` only on top-level tables; child rows reachable across tenants by guessing ids.
- Tenant taken from a request header the client controls.
- App connecting as the table owner or a superuser, so RLS silently does nothing.
- Session-level `SET app.tenant_id` behind a transaction pooler.
- Global unique constraints (`UNIQUE (email)`) that leak "this email exists in another tenant".
- Caches, search indexes or object storage paths without the tenant in the key.

## Checks
- [ ] Two-tenant test fixture: every list/read/update/delete endpoint returns 404/403 for the other tenant's ids (extend the authorization matrix from `eos scaffold security-tests`).
- [ ] A test connects as the app role with `app.tenant_id` unset and gets no rows (or an error) from each RLS table.
- [ ] Query that lists tenant-owned tables without RLS enabled returns nothing: `SELECT relname FROM pg_class WHERE relkind IN ('r','p') AND relrowsecurity = false AND relnamespace = 'public'::regnamespace AND relname IN (<tenant tables>)`.
- [ ] App role is not owner and has no BYPASSRLS (`SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user`).
- [ ] Composite FKs include `tenant_id`; `schema_lint.sql` (db-safety scaffold) shows them indexed.

## Sources
- https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/silo-pool-and-bridge-models.html (silo, pool, bridge)
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html (default deny; owners, superusers and BYPASSRLS bypass; FORCE; USING implies WITH CHECK)
- https://www.postgresql.org/docs/current/functions-admin.html (`set_config(..., is_local)`)
- https://www.pgbouncer.org/features.html (SET/RESET never supported in transaction pooling)
- https://www.postgresql.org/docs/current/ddl-partitioning.html (unique constraints must include the partition key)
