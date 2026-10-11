---
id: analytics/architecture
title: Analytics architecture for small teams (Postgres-first, DuckDB, when to add a warehouse or lakehouse, CDC vs batch ELT, layers, adoption stages, cost controls)
area: analytics
read_when: planning reporting or BI, choosing between a read replica, DuckDB, a warehouse (BigQuery, Snowflake, ClickHouse) or a lakehouse (Iceberg, Delta, DuckLake), setting up ingestion (CDC or batch), or analytics queries are slowing production
verified: 2026-10-11
revisit_days: 180
sources: ["https://duckdb.org/why_duckdb", "https://duckdb.org/docs/current/connect/concurrency", "https://ducklake.select/", "https://raw.githubusercontent.com/duckdb/pg_duckdb/main/README.md", "https://iceberg.apache.org/docs/latest/", "https://debezium.io/documentation/reference/stable/connectors/postgresql.html", "https://dlthub.com/docs/intro", "https://cloud.google.com/bigquery/docs/best-practices-costs", "https://docs.snowflake.com/en/user-guide/warehouses-considerations", "https://docs.getdbt.com/docs/introduction"]
---
# Analytics architecture: grow it in steps

The OLTP/OLAP separation ladder (materialised views → replica → logical replication → CDC/ELT) and the rules for the analytics copy are in `data/nosql-analytics`. This ref decides **what to run at each stage**, how data gets there, and how to keep the bill and the pipeline small. The one idea: a small team should run the fewest moving parts that answer today's questions, with SQL in git, and move up a stage only when a measured limit is hit.

## Decision guide

**1. Adoption stages.** Move up when the trigger is real, not planned.
| Stage | What runs | Move up when |
|---|---|---|
| 0. Product DB + read replica | SQL views and a BI tool (Metabase, Superset) on a replica with a read-only role | reports need history the app deletes, joins with other sources (payments provider, CRM, events), or replica lag/cancelled queries hurt |
| 1. Reporting Postgres or DuckDB | Batch ELT (nightly or hourly) into a separate Postgres schema/DB, or Parquet files queried by DuckDB; dbt models in git | data no longer fits one machine comfortably, many concurrent analysts, or sources multiply |
| 2. Managed warehouse | BigQuery, Snowflake, Redshift or ClickHouse (self-hosted or cloud); dbt; an orchestrator | several teams, strict access control per dataset, or very large event volumes |
| 3. Lakehouse | Open table formats (Iceberg, Delta, DuckLake) on object storage, several engines | multiple engines must share one copy, or storage cost dominates and you have platform engineers |
Most products in their first years live at stage 0–1. A warehouse adds a second security perimeter, a second copy for erasure and a bill that grows with queries.

**2. DuckDB facts that decide fit** (DuckDB docs): in-process, columnar, built for analytical (OLAP) queries, ACID with MVCC, single-file database or lakehouse formats. In-process, **one process can read and write; many processes can only read** (`READ_ONLY`). Multi-process writes go through the Quack remote protocol, which DuckDB documents as beta as of v1.5.2. So: great for CI, notebooks, scheduled jobs and embedded dashboards over Parquet; not a shared multi-writer server today. **DuckLake** (v1.0) is a lakehouse format that keeps the catalog in a SQL database (PostgreSQL, SQLite or DuckDB) and data in Parquet files.

**3. Postgres-first options.** A reporting replica or separate Postgres covers a lot. `pg_duckdb` (official DuckDB extension for PostgreSQL) runs analytical queries through DuckDB's engine (`duckdb.force_execution=true`) and reads/writes Parquet, Iceberg and Delta. Run it on a reporting instance, not the primary: faster scans are still load on the server users depend on.

**4. Ingestion: batch ELT or CDC.**
| | Batch ELT (incremental by `updated_at` or full extract) | CDC (Debezium via `pgoutput` logical decoding) |
|---|---|---|
| Freshness | hours / minutes | seconds |
| Captures deletes and every intermediate state | no (unless soft deletes) | yes |
| Moving parts | a scheduled job (dlt, a SQL `COPY`, a vendor connector) | Kafka or Debezium Server, replication slot, schema change handling |
| Failure mode | late data | a stopped consumer makes the slot retain WAL until the primary's disk fills (monitor it) |
Start with batch unless a product need requires seconds. `dlt` (open-source Python library) loads APIs and databases into datasets with incremental loading; managed connectors are fine when the licence and data residency fit (check where the vendor processes data).

**5. Layers, whatever the engine.** `raw` (as loaded, append-only, never edited by hand) → `staging` (one model per source table: rename, cast, deduplicate) → `intermediate` → `marts` (facts and dimensions for people and tools). Transformations are SQL in git, built and tested by dbt (`analytics/dbt-elt`), idempotent so re-runs give the same result (dbt docs).

**6. Lakehouse formats** when you truly need them: Iceberg is "an open table format for huge analytic datasets" with schema evolution and hidden partitioning, usable from Spark, Trino, Flink and others; Delta Lake is the Spark-centred equivalent. Choose by the engines you will actually run.

**7. Cost controls** (no prices here; read the vendor page on the day):
- BigQuery on-demand bills by **bytes read**: partition and cluster large tables, select columns instead of `SELECT *`, dry-run to estimate (an upper bound), and set custom daily query quotas.
- Snowflake bills warehouse running time: size warehouses for the workload and suspend them when idle; suspending drops the warehouse cache, so the first queries afterwards are slower.
- Everywhere: incremental models instead of full rebuilds for large facts, retention on raw event tables, and a monthly look at the most expensive queries and their owners (`ops/capacity-cost`).

## Examples
- Mobile-money app, 6 engineers: nightly `COPY` of ledger and users (pseudonymised) into a reporting Postgres, dbt builds `fct_daily_payments` and `dim_merchants`, Metabase reads marts only. Finance totals reconcile with the ledger every morning.
- Same team a year later, events at tens of millions of rows a month: events land as daily Parquet partitions in object storage; DuckDB jobs aggregate them into the reporting Postgres. Still no warehouse.

## Anti-patterns
- Buying a warehouse, a lakehouse and a streaming platform before the first dashboard has a user.
- BI tool on the production primary, or analysts with write access to raw tables.
- CDC because it sounds modern when daily numbers are enough; abandoned replication slots.
- Business logic in BI tool queries (each dashboard computes "revenue" differently); keep it in dbt marts (`analytics/metrics-dashboards`).
- **When NOT to build analytics infrastructure at all:** a few founders' questions answered by saved SQL on a replica are fine.

## Checks
- [ ] Each analytics store is in the data inventory with owner, retention and erasure path (`data/nosql-analytics`, `security/privacy`).
- [ ] Ingestion jobs are idempotent and replayable for a date range (`analytics/pipelines-orchestration`).
- [ ] Replication slots monitored if CDC is used.
- [ ] Warehouse cost controls set (quotas, auto-suspend, partitioning) and reviewed monthly.
- [ ] `eos scaffold analytics` for a dbt project with tests and contracts; `eos data check` in CI.

## Sources
- DuckDB, Why DuckDB: https://duckdb.org/why_duckdb · Concurrency: https://duckdb.org/docs/current/connect/concurrency
- DuckLake: https://ducklake.select/
- pg_duckdb README: https://raw.githubusercontent.com/duckdb/pg_duckdb/main/README.md
- Apache Iceberg: https://iceberg.apache.org/docs/latest/
- Debezium PostgreSQL connector (replication slots, WAL): https://debezium.io/documentation/reference/stable/connectors/postgresql.html
- dlt: https://dlthub.com/docs/intro
- BigQuery cost best practices: https://cloud.google.com/bigquery/docs/best-practices-costs
- Snowflake warehouse considerations: https://docs.snowflake.com/en/user-guide/warehouses-considerations
- dbt introduction (idempotent transformations): https://docs.getdbt.com/docs/introduction
