---
id: analytics/quality-contracts
title: Data quality and data contracts (what to test where, dbt tests vs Great Expectations vs Soda vs pandera, ODCS contracts, breaking-change rules, quarantine, ownership)
area: analytics
read_when: adding data-quality checks to ingestion or models, writing or changing a data contract between a producer and consumers, choosing a data-quality tool, or bad data reached a dashboard or model
verified: 2026-10-11
revisit_days: 180
sources: ["https://github.com/bitol-io/open-data-contract-standard", "https://bitol-io.github.io/open-data-contract-standard/latest/", "https://cli.datacontract.com/", "https://docs.getdbt.com/docs/build/data-tests", "https://docs.getdbt.com/docs/mesh/govern/model-contracts", "https://docs.greatexpectations.io/docs/core/introduction/", "https://github.com/sodadata/soda-core", "https://pandera.readthedocs.io/en/stable/", "https://docs.dagster.io/getting-started/concepts"]
---
# Data quality and contracts

A data contract is a versioned, reviewed promise from the team that produces a dataset to the teams that use it: the schema, meaning, quality rules, owner and service level. Tests check the data against it on every run; a contract check in CI stops a producer from silently breaking consumers. The one idea: **schema changes are API changes** and get the same review, versioning and deprecation as a public API (`api/evolution`, `data/migrations`).

## Decision guide

**1. Test at each boundary, not only at the end.**
| Boundary | Check | Typical tool |
|---|---|---|
| Ingestion (raw) | schema matches the contract, row counts vs source, freshness, no duplicate natural keys in the batch | contract test (datacontract-cli, Soda), dbt source freshness, pandera on dataframes |
| Transformation (staging → marts) | keys unique and not null, foreign keys resolve, accepted values, business rules | dbt data tests and unit tests (`analytics/dbt-elt`) |
| Serving (marts, features, exports) | contract shape enforced, totals reconcile with the system of record | dbt model contracts, reconciliation queries |
| ML features | ranges, null rates, category sets, drift vs training | pandera / GX in the pipeline, drift monitoring (`ml/serving-monitoring`) |

**2. Tool choice** (versions and licences from PyPI/GitHub, 2026-10-11).
| Tool | Licence | Use when |
|---|---|---|
| dbt tests | Apache-2.0 (dbt-core) | your transformations are dbt: start here, it costs nothing extra |
| pandera 0.34 | MIT | validating pandas/Polars dataframes in Python pipelines and training code |
| GX Core 1.24 (Great Expectations) | Apache-2.0 | many non-dbt sources, rich "Expectations" library, data docs |
| Soda Core 4.x | **Elastic License 2.0** (source-available, not OSI open source) | its data-contract engine and CLI fit; check the licence terms for your use |
| datacontract-cli 1.2 | MIT | lint, test, `breaking` and `changelog` for contract files (ODCS) |
| Dagster asset checks | Apache-2.0 | you already orchestrate with Dagster |
One tool per layer is plenty. Do not run three overlapping frameworks.

**3. Contract format.** The **Open Data Contract Standard (ODCS)** by Bitol (an LF AI & Data Foundation project), current version v3.2.0, Apache-2.0, is a YAML document. Required top-level keys in its JSON Schema: `apiVersion`, `kind: DataContract`, `id`, `version`; `status` (proposed, draft, active, deprecated, retired), `schema` (objects with `properties`: `name`, `logicalType`, `required`, `unique`, `primaryKey`, `classification`, `quality`), `team`, `support`, `slaProperties` are optional sections. eos uses ODCS so contracts work with datacontract-cli and vendor tools.

**4. Breaking-change rules** (what `eos data check` enforces against the base branch):
| Change | Breaking? | Required |
|---|---|---|
| add an optional property | no | minor version bump |
| remove or rename a property | yes | major version bump, deprecation period, consumers notified |
| change `logicalType` | yes | major bump |
| optional → `required: true` | yes (producers may fail) | major bump |
| tighten `enum` / accepted values | yes | major bump |
| loosen a rule, add docs | no | patch/minor (eos warns when a schema change keeps the same version) |
Run old and new versions side by side (`orders_v1`, `orders_v2` views or dbt model versions) for the deprecation window.

**5. Bad rows: quarantine, do not drop.** Route failing rows to a `_rejected` table with the failing rule and batch id; alert when the reject rate crosses a threshold you set from history. Silent drops turn into "revenue is down 3%" debates.

**6. Personal data in contracts.** Mark properties holding personal data with `classification` (for example `restricted`) and a tag such as `pii`; eos warns when a property named like `email`, `phone`, `msisdn`, `national_id` or `date_of_birth` has no classification. The classification drives masking in marts, access roles and retention (`analytics/privacy-anonymisation`).

## Examples
```yaml
apiVersion: v3.2.0
kind: DataContract
id: payments-daily
version: 1.1.0
status: active
team: {name: payments-data}
schema:
  - name: fct_daily_payments
    properties:
      - {name: payment_day, logicalType: date, required: true}
      - {name: merchant_id, logicalType: string, required: true}
      - {name: amount_xaf, logicalType: integer, required: true}
      - {name: payer_msisdn_hash, logicalType: string, classification: restricted, tags: [pii]}
```
Removing `merchant_id` in a pull request without bumping to 2.0.0 fails `eos data check --base origin/main` (DAT006).

## Anti-patterns
- Contracts written once in a wiki and never checked by a machine.
- Quality checks only on the final dashboard query; failures discovered by the CFO.
- `severity: warn` on everything so the pipeline stays green.
- A producer renames a column on Friday; three dashboards break on Monday.
- **When NOT to write formal contracts:** one team producing and consuming its own tables; dbt tests and model contracts are enough until another team or tool depends on the data.

## Checks
- [ ] Datasets used outside the producing team have an ODCS contract in git with an owner (`team`) and status.
- [ ] `eos data check` in CI (DAT001–DAT008): valid fundamentals, typed properties, classified personal data, a named owning team, version bumped on breaking changes vs the base branch.
- [ ] Ingestion and marts have tests at each boundary; failing rows are quarantined with a reason.
- [ ] Reject-rate and freshness alerts have owners.

## Sources
- ODCS repository (v3.2.0, Apache-2.0): https://github.com/bitol-io/open-data-contract-standard · reference: https://bitol-io.github.io/open-data-contract-standard/latest/
- datacontract CLI (lint, test, breaking, changelog): https://cli.datacontract.com/
- dbt data tests: https://docs.getdbt.com/docs/build/data-tests · model contracts: https://docs.getdbt.com/docs/mesh/govern/model-contracts
- GX Core: https://docs.greatexpectations.io/docs/core/introduction/
- Soda Core (Elastic License 2.0): https://github.com/sodadata/soda-core
- pandera: https://pandera.readthedocs.io/en/stable/
- Dagster concepts (asset checks): https://docs.dagster.io/getting-started/concepts
