---
id: analytics/dbt-elt
title: dbt projects that stay correct (staging/intermediate/marts, data tests, unit tests, model contracts, incremental models, Slim CI with state and defer, dbt v1 vs v2)
area: analytics
read_when: creating or reviewing a dbt project, adding tests or contracts to models, making a model incremental, setting up dbt in CI, or choosing between dbt v1 (Python) and v2 (Rust)
verified: 2026-10-11
revisit_days: 180
sources: ["https://docs.getdbt.com/docs/introduction", "https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview", "https://docs.getdbt.com/docs/build/data-tests", "https://docs.getdbt.com/docs/build/unit-tests", "https://docs.getdbt.com/docs/mesh/govern/model-contracts", "https://docs.getdbt.com/docs/build/incremental-models", "https://docs.getdbt.com/reference/node-selection/defer", "https://docs.getdbt.com/docs/supported-data-platforms", "https://pypi.org/project/dbt-core/", "https://pypi.org/project/dbt-duckdb/"]
---
# dbt that stays correct

dbt turns SQL `select` statements in git into tables and views, with tests, lineage and docs. Where it sits in the stack: `analytics/architecture`. The one idea: every mart that a person or tool reads has **tests on its keys, a contract on its shape, and a CI build** of what changed, so a broken join fails a pull request instead of a board meeting.

## Decision guide

**1. Versions (checked 2026-10-11).** dbt docs now describe two generations: **v2** (Rust engine, the default when you install dbt, adapters bundled) and **v1** (the original Python dbt-core, still maintained). The v2 adapter table lists Snowflake, BigQuery, Databricks, Redshift and DuckDB (CLI) as generally available, Spark (CLI) beta and ClickHouse private beta; **Postgres is not in that table**, so Postgres warehouses stay on v1 (`dbt-postgres` 1.11.0). Latest v1 on PyPI: `dbt-core` 1.12.5 (Apache-2.0), `dbt-duckdb` 1.11.0. `eos scaffold analytics` pins v1 + DuckDB because it runs offline in CI with no warehouse account; switching engines is a profile change.

**2. Structure** (dbt's own guide): `staging` (one model per source table: rename, cast, light cleaning; no joins), `intermediate` (purpose-built steps), `marts` (business entities: `fct_*` facts, `dim_*` dimensions). Sources are declared in YAML with freshness checks. Only marts are exposed to BI.

**3. Tests: which kind for what.**
| Kind | What it checks | Use for |
|---|---|---|
| Generic data tests (built in: `unique`, `not_null`, `accepted_values`, `relationships`) | assertions on built data | every primary key (`unique` + `not_null`), every foreign key (`relationships`), every status column (`accepted_values`) |
| Singular data tests (a SQL file returning failing rows) | business rules | "ledger debits = credits per day", "no payment after refund" |
| Unit tests (dbt v1.8+) | model SQL against small static inputs and expected output | tricky logic: window functions, date bucketing, currency rounding, deduplication. dbt says they need no production compute: run them in dev and CI |
| Source freshness | last load time | alert when an upstream feed stops |
Set `severity: warn` only with an owner and an expiry; `store_failures` keeps failing rows for debugging.

**4. Model contracts.** With `contract: {enforced: true}` the YAML must list every column's `name` and `data_type`; dbt runs a preflight check that the query returns exactly those columns and types, and writes them into the DDL. Limits from dbt docs:
- Supported on SQL models materialised as table, view (names and types only) or incremental (with `on_schema_change: append_new_columns` or `fail`); not on Python, ephemeral or materialised-view models, nor on sources, seeds or snapshots.
- **Constraints are often not enforced by cloud warehouses**: on Redshift, Snowflake and BigQuery only `not_null` is enforced and `primary_key`/`unique`/`foreign_key` are metadata; Postgres enforces all of them; Databricks enforces `not_null` and `check`; Spark and Athena enforce none. Keep the `unique`/`relationships` data tests anyway.
- dbt warns that governance features added too early make change harder: put contracts on marts other teams or tools depend on, not on every staging model.

**5. Incremental models** for large, append-mostly facts. `is_incremental()` is true only when the table exists, the model is incremental and `--full-refresh` was not passed; the SQL must be valid either way. `unique_key` makes reruns update rows instead of appending duplicates (idempotency). Add a lookback window for late-arriving rows (e.g. reprocess the last 3 days) and schedule a periodic full refresh if the source can change history.

**6. Slim CI.** Build only changed models and their children against a production manifest: `dbt build --select state:modified+ --defer --state prod-manifest/`. Defer resolves `ref()` to production for parents you did not build. Without a production manifest (new project), build everything on a small sample (DuckDB in CI works well).

**7. Money and time** in marts: integer minor units or `numeric`, never float; XAF has no minor unit; timestamps in UTC with the business day computed explicitly in Africa/Douala (`data/keys-money-time`). A singular test reconciles mart totals with the ledger.

## Examples
```yaml
# models/marts/_marts.yml
models:
  - name: fct_daily_payments
    config: {contract: {enforced: true}}
    columns:
      - {name: payment_day, data_type: date, constraints: [{type: not_null}]}
      - name: merchant_id
        data_type: varchar
        data_tests: [not_null, {relationships: {arguments: {to: ref('dim_merchants'), field: merchant_id}}}]
      - {name: amount_xaf, data_type: bigint, data_tests: [not_null]}
unit_tests:
  - name: refunds_are_negative
    model: fct_daily_payments
    given: [{input: ref('stg_payments'), rows: [{payment_id: p1, status: refunded, amount_xaf: 500, ...}]}]
    expect: {rows: [{amount_xaf: -500, ...}]}
```
CI: `dbt deps && dbt build --target ci` (seeds, models, tests, unit tests in DAG order), then `eos data check` for ODCS contracts.

## Anti-patterns
- Marts with no `unique`/`not_null` on the grain: duplicates double revenue silently.
- Business logic copied into BI queries instead of a mart.
- `SELECT *` from sources in staging (schema drift flows straight into marts); contracts on every model from day one.
- Incremental models with no `unique_key` and no lookback (duplicates on retry, missing late rows).
- Running full `dbt build` on production data in every PR when Slim CI would do.
- **When NOT to use dbt:** a handful of views with one consumer; a plain SQL file in git and a scheduled job are enough until models depend on each other.

## Checks
- [ ] Every mart: grain tested (`unique` + `not_null`), foreign keys (`relationships`), statuses (`accepted_values`), contract enforced if consumed outside the team.
- [ ] Unit tests on models with non-trivial logic; a reconciliation test for money marts.
- [ ] CI runs `dbt build` (Slim CI when a production manifest exists) and fails on test errors.
- [ ] `eos scaffold analytics` gives a working DuckDB-backed project with these tests and a CI job.

## Sources
- dbt introduction (v1/v2, idempotence): https://docs.getdbt.com/docs/introduction
- How we structure dbt projects: https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview
- Data tests: https://docs.getdbt.com/docs/build/data-tests · Unit tests: https://docs.getdbt.com/docs/build/unit-tests
- Model contracts: https://docs.getdbt.com/docs/mesh/govern/model-contracts
- Incremental models: https://docs.getdbt.com/docs/build/incremental-models
- Defer and Slim CI: https://docs.getdbt.com/reference/node-selection/defer
- Supported data platforms (v2 adapter lifecycle): https://docs.getdbt.com/docs/supported-data-platforms
- PyPI: https://pypi.org/project/dbt-core/ · https://pypi.org/project/dbt-duckdb/
