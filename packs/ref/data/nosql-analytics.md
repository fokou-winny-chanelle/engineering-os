---
id: data/nosql-analytics
title: When a non-relational store fits, and keeping analytics (OLAP) away from the production database
area: data
read_when: someone proposes MongoDB, DynamoDB, a time-series or graph database, or a warehouse; reports or dashboards are slowing production; planning CDC, ELT or a data warehouse
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.mongodb.com/docs/manual/data-modeling/", "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html", "https://github.com/timescale/timescaledb", "https://www.postgresql.org/docs/current/logical-replication-restrictions.html", "https://www.postgresql.org/docs/current/hot-standby.html", "https://debezium.io/documentation/reference/stable/connectors/postgresql.html", "https://clickhouse.com/docs/intro", "https://duckdb.org/why_duckdb", "https://docs.getdbt.com/docs/introduction", "https://www.postgresql.org/docs/current/datatype-json.html", "https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html"]
---
# NoSQL when it fits; analytics off the OLTP path

PostgreSQL covers relational data, documents (`jsonb`), key/value, full-text search, vectors (pgvector), queues (`SKIP LOCKED`) and time-series (partitioning, TimescaleDB extension) well enough for most products. A second database is a second thing to secure, back up, migrate, monitor, keep consistent and erase personal data from. Add one for a named requirement, not for fashion.

## Decision guide

**1. When a non-relational store earns its place.**
| Store type | Fits | Costs and caveats |
|---|---|---|
| Document (MongoDB, Firestore) | Aggregates read and written as a whole; schema varies per record; MongoDB's own rule: "data that's accessed together should be stored together" | Cross-document invariants and joins are on you; plan indexes and validation (JSON Schema) anyway |
| Key/value / wide-column (DynamoDB, Cassandra, Bigtable) | Huge, predictable access patterns by key at steady low latency; global scale | AWS: do not start designing a DynamoDB schema "until you know the questions it will need to answer"; single-table designs are hard to change; ad-hoc queries and analytics need an export |
| In-memory (Redis/Valkey) | Cache, counters, sessions, rate limits | Not a system of record (`data/search-redis`) |
| Time-series (TimescaleDB as a Postgres extension, InfluxDB, ClickHouse) | High-rate metrics/events, rollups, retention by time | Often fine in Postgres with monthly partitions until volume says otherwise |
| Graph (Neo4j, etc.) | Deep, variable-length relationship traversal is the core query (fraud rings, recommendations) | Recursive CTEs in Postgres handle shallow hierarchies; a graph DB is another copy to sync |
| Search engine | Relevance, typo tolerance, facets at scale | Derived index, never the source of truth |
Questions before saying yes: Which access patterns does Postgres fail, with measurements? Who owns operations and backups? How do we keep it consistent with the main database (outbox/CDC)? How does erasure reach it? What does it cost at 10× data?

**2. If you choose a document store, still model.** Embed what is read together and bounded in size (order + lines); reference what is shared or unbounded (reviews, comments); validate documents at write; index for every query; avoid documents that grow forever; keep money as decimal types, not doubles.

**3. Separate analytics (OLAP) from production (OLTP).** Reports scan many rows, run long and hold snapshots; on the primary they compete with users, hold back vacuum and bloat tables (`data/postgres-concurrency`). Climb in order:
| Step | Use when | Watch out |
|---|---|---|
| Indexed queries / materialised views on the primary | A few internal reports | `REFRESH MATERIALIZED VIEW CONCURRENTLY` needs a unique index; schedule off-peak |
| Read replica for reporting | Many or heavy reports; minutes of lag OK | Long queries get cancelled by replay conflicts or, with `hot_standby_feedback`, bloat the primary |
| Logical replication to a reporting Postgres | Different indexes/retention than production | No DDL or sequence replication |
| CDC (Debezium via `pgoutput` logical decoding) or batch ELT into a warehouse/OLAP engine | Cross-system analytics, history, BI tools, product analytics | Replication slots retain WAL if the consumer stops: monitor them; schema changes must flow downstream |
| Embedded analytics (DuckDB) | Analysts or jobs querying exports/Parquet without a server | Not for concurrent multi-user serving |
OLAP engines: ClickHouse (column-oriented SQL DBMS for OLAP, open source and cloud), BigQuery/Snowflake/Redshift (managed warehouses), DuckDB (in-process). Model transformations as version-controlled SQL (dbt) with tests, not ad-hoc scripts.

**4. Rules for the analytics copy.**
- Analytics never writes back into production tables; derived results come back through an API or a job with an owner.
- Product events (clicks, page views) go to the event pipeline, not into OLTP tables row by row.
- Minimise and pseudonymise personal data on the way in; the warehouse is in the data inventory, retention schedule and erasure process (`data/history-retention`, `security/privacy`).
- Define metrics once (semantic layer or dbt models) so finance and product numbers agree; reconcile key totals (revenue, payments) back to the ledger.
- Access to the warehouse is role-based and audited; exports to spreadsheets are a data leak path.

## Anti-patterns
- MongoDB "because the schema might change" (it will change in Postgres too, with migrations and constraints helping you).
- DynamoDB chosen before the access patterns are known.
- BI tool pointed at the production primary with a superuser account.
- Nightly `pg_dump` restored into a "reporting database" that nobody secures or deletes from.
- Abandoned CDC replication slot filling the primary's disk.

## Checks
- [ ] ADR for every additional datastore: requirement, measurements, sync method, backup, erasure, owner, cost.
- [ ] No analytical query runs on the primary at peak (check `pg_stat_statements` for report queries).
- [ ] Replication slots monitored (retained WAL, active consumer); alert when inactive.
- [ ] Warehouse listed in the data inventory with retention and erasure coverage.

## Sources
- https://www.mongodb.com/docs/manual/data-modeling/ (accessed together, stored together; embedding vs references)
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html (know the questions first; few tables)
- https://github.com/timescale/timescaledb (time-series as a Postgres extension)
- https://www.postgresql.org/docs/current/logical-replication-restrictions.html (no DDL, no sequences)
- https://www.postgresql.org/docs/current/hot-standby.html (replay conflicts; hot_standby_feedback)
- https://debezium.io/documentation/reference/stable/connectors/postgresql.html (pgoutput logical decoding; replication slots)
- https://clickhouse.com/docs/intro (column-oriented OLAP)
- https://duckdb.org/why_duckdb (in-process)
- https://docs.getdbt.com/docs/introduction
- https://www.postgresql.org/docs/current/datatype-json.html
- https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html (CONCURRENTLY needs a plain unique index)
