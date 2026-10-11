---
id: analytics/pipelines-orchestration
title: Data pipelines and orchestration (idempotent tasks, partitions, backfills, late data, choosing cron vs Dagster vs Airflow vs Prefect, retries and alerting)
area: analytics
read_when: writing an ingestion or transformation job, choosing an orchestrator, planning a backfill or re-run, handling late or corrected data, or a pipeline produced duplicates after a retry
verified: 2026-10-11
revisit_days: 180
sources: ["https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html", "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html", "https://docs.dagster.io/guides/build/partitions-and-backfills/backfilling-data", "https://docs.dagster.io/getting-started/concepts", "https://docs.prefect.io/v3/concepts/caching", "https://pypi.org/project/apache-airflow/", "https://pypi.org/project/dagster/", "https://pypi.org/project/prefect/"]
---
# Pipelines that can be re-run

A pipeline will fail halfway, be retried, and be re-run for last month after a bug fix. Design every task so that **running it again for the same interval gives the same result**. Airflow's best-practice guide says it plainly: treat tasks like database transactions, never leave partial results, and produce the same outcome on every re-run. Layering and engines: `analytics/architecture`; tests on outputs: `analytics/quality-contracts`.

## Decision guide

**1. Idempotency rules** (adapted from Airflow's best practices; they apply to any tool):
- **Write by partition, replace not append.** Overwrite the whole target partition (day, merchant, batch) inside a transaction, or `MERGE`/`UPSERT` on a natural key. Airflow: do not `INSERT` on re-run; use UPSERT.
- **Read a fixed interval, never "latest".** Parameterise by the run's logical interval (`data_interval_start` in Airflow, a partition key in Dagster), not by "now". Airflow: do not use `now()` for critical computation inside a task.
- **Deterministic outputs.** No random sampling without a seed, stable sort for "first" records, explicit time zones.
- **Atomic publish.** Build into a staging table or path, validate, then swap or rename; consumers never see half a day.
- **Record what ran**: interval, code version (git SHA), input row counts, output row counts.

**2. Choosing the scheduler.**
| Option | Fits | Watch out |
|---|---|---|
| cron / CI schedule / `pg_cron` + idempotent scripts | 1–5 jobs, one team, simple dependencies | no backfill UI, no lineage; alerting is yours |
| dbt alone, scheduled | ELT where everything after loading is SQL | ingestion still needs a job |
| Dagster (1.13.x, Apache-2.0) | asset-centric: you think in tables and models; partitions, asset checks and dbt integration built in | another service to run (or a hosted plan) |
| Airflow (3.3.x, Apache-2.0) | many heterogeneous tasks, large ecosystem of operators, teams that already know it | heavier to operate; DAG files are code that runs at parse time (keep top-level code light) |
| Prefect (3.8.x, Apache-2.0) | Python-first flows, dynamic workflows | caching needs result persistence, which is off by default (Prefect docs) |
Versions are the latest on PyPI on 2026-10-11. Pick one; two orchestrators is worse than either.

**3. Backfills.** Plan them, do not improvise them.
- Airflow 3: backfill from the UI or `airflow backfill create --dag-id … --from-date … --to-date … --reprocess-behavior failed --max-active-runs 3`; it re-runs every interval in the range.
- Dagster: a backfill over N partitions launches N runs by default; a `BackfillPolicy.single_run()` asset processes the whole range in one run (useful when the engine parallelises, such as a warehouse query) and must read `partition_time_window` or `partition_key_range` instead of a single key.
- Always: cap concurrency so the source database is not hammered, run on a copy first for large ranges, compare row counts and key totals before and after, and tell consumers (dashboards change).

**4. Late and corrected data.** Mobile clients upload events hours late on poor networks, and payment providers send corrections days later. Reprocess a sliding window (for example the last 3 days) on every run, keep `loaded_at` separate from `event_at`, and alert when late volume jumps. For money, the ledger is the truth: reconcile analytics totals with it daily.

**5. Failure handling.** Retries with backoff for transient errors only (timeouts, 5xx), never for data errors. A failed data test stops downstream publishing. Alert to a channel with an owner; include the interval and a re-run command. Freshness SLOs per mart ("payments mart updated by 07:00 WAT") turn into alerts (`ops/slo-error-budgets`).

**6. Secrets and access.** Pipelines read production through a read-only role on a replica; credentials come from the secret store, never from DAG files or notebooks (`security/secrets-keys`).

## Examples
```sql
-- idempotent daily load: replace one day of payments in a transaction
BEGIN;
DELETE FROM raw.payments WHERE paid_on = :day;
INSERT INTO raw.payments SELECT * FROM staging_payments WHERE paid_on = :day;
COMMIT;
```
Dagster asset with daily partitions and a single-run backfill policy writes `overwrite_data_in_datetime_range(start, end, rows)`, the pattern shown in Dagster's backfill guide.

## Anti-patterns
- `INSERT` on every run (duplicates after each retry), or "load since last run" stored in a local file.
- Jobs that read `now()` or "the latest file", so a re-run of last Tuesday computes today.
- Retrying data-quality failures until they pass; swallowing exceptions to keep the DAG green.
- Heavy work at module import in Airflow DAG files.
- **When NOT to adopt an orchestrator:** three nightly jobs with no dependencies; a scheduled CI workflow plus alerts is enough.

## Checks
- [ ] Every job takes an explicit interval/partition and can be re-run for a past date with the same result (test it: run twice, compare counts and checksums).
- [ ] Writes replace a partition or upsert on a key; no blind appends.
- [ ] Backfill runbook: concurrency cap, verification queries, consumer notice.
- [ ] Freshness alerts on marts; failed tests block publishing.

## Sources
- Airflow best practices (tasks as transactions, UPSERT, partitions, `now()`): https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
- Airflow DAG runs and backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html
- Dagster backfilling data: https://docs.dagster.io/guides/build/partitions-and-backfills/backfilling-data · concepts: https://docs.dagster.io/getting-started/concepts
- Prefect caching (idempotent retries, result persistence): https://docs.prefect.io/v3/concepts/caching
- PyPI: https://pypi.org/project/apache-airflow/ · https://pypi.org/project/dagster/ · https://pypi.org/project/prefect/
