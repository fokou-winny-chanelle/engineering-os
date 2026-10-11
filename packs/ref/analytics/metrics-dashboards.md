---
id: analytics/metrics-dashboards
title: Metrics layer and dashboards (one definition per metric, metric specs, semantic layers vs dbt marts, BI tool choice, dashboard design, reconciliation, experiment readouts)
area: analytics
read_when: defining a business metric (revenue, active users, conversion), building or reviewing a dashboard, choosing a BI tool or semantic layer, or two reports disagree on the same number
verified: 2026-10-11
revisit_days: 180
sources: ["https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl", "https://github.com/dbt-labs/metricflow", "https://cube.dev/docs/product/introduction", "https://docs.evidence.dev/", "https://metabase.com/docs/latest/", "https://developers.google.com/machine-learning/guides/rules-of-ml"]
---
# Metrics everyone agrees on

When finance says revenue was 41 M XAF and product says 44 M, nobody trusts either dashboard. The cause is almost always two definitions. The one idea: **each metric has one written definition, implemented once (a dbt mart or a semantic layer), and every dashboard reads that implementation**; numbers that touch money reconcile with the ledger.

## Decision guide

**1. Write the metric spec before the SQL.** For each metric: name, plain-English definition, formula, grain (per day, per merchant), filters (test accounts, internal staff, refunds), time zone of the day boundary (Africa/Douala for local reporting), currency and rounding, owner, source model, and known caveats. Keep specs in git next to the models (`metrics/*.yml` or dbt YAML).

**2. Where the definition lives.**
| Option | Fits | Notes |
|---|---|---|
| dbt marts with one column per metric input + documented SQL | small teams, one BI tool | simplest; dashboards aggregate a single mart, no custom joins |
| dbt Semantic Layer (MetricFlow) | many tools and teams need the same metrics via an API | dbt docs: requires a dbt platform Starter or Enterprise-tier account; MetricFlow itself is Apache-2.0 |
| Cube (open-source semantic layer core) | embedded analytics, APIs for apps, caching | another service to run |
| BI tool's own model layer (Metabase models/metrics, Lightdash on dbt) | the BI tool is the only consumer | definitions locked into one tool |
Start with marts; add a semantic layer when a second consumer (app, notebook, another BI tool, an AI agent) needs the same numbers.

**3. Metric hygiene.**
- **Counts of what?** "Active user" needs an action and a window ("completed at least one transfer in the last 30 days"), not "opened the app".
- **Ratios:** define numerator and denominator populations explicitly; compute ratios from summed parts, never average daily ratios.
- **Money:** gross vs net of refunds, fees and reversals; amounts in minor units; XAF and other currencies never summed without conversion at a stated rate and date.
- **Exclusions:** test merchants, staff accounts, fraud-flagged transactions, and duplicates are excluded in one place (the mart), not per dashboard.
- **Late data:** label the last complete day; partial days are greyed out or hidden.

**4. Dashboards.** One dashboard per decision or audience. Top: the 3–5 metrics that decide something, with comparison (vs last period, vs target) and the definition one click away. Then breakdowns that explain movement (channel: app/USSD/web, region, new vs returning, device class). Show uncertainty and sample sizes on small segments. Every dashboard has an owner and a review date; unused dashboards are archived. Accessibility: do not encode meaning by colour alone (`frontend/accessibility`).

**5. Tool choice.** Pick by who builds and who reads: SQL-first teams can publish reports as code (Evidence Core is an MIT-licensed SQL + Markdown framework); self-service exploration for non-SQL users suits Metabase, Superset or Lightdash. Requirements that matter more than features: row-level permissions, SSO, read-only warehouse role, audit of exports, hosting region.

**6. Experiments and metric changes.** Google's Rules of ML: design and implement metrics before building models (Rule #2), and the same applies to features: decide the success metric and guardrail metrics (errors, latency, complaints, refunds) before launching an A/B test, fix the sample size and duration in advance, and do not stop at the first significant peek. When a metric definition changes, version it (`active_users_v2`), backfill history, and annotate dashboards.

## Examples
```yaml
# metrics/net_payment_volume.yml
name: net_payment_volume_xaf
definition: Sum of completed payments minus refunds and reversals, in XAF, by business day (Africa/Douala).
formula: sum(amount_xaf) where status in (completed) - sum(amount_xaf) where status in (refunded, reversed)
grain: [payment_day, merchant_id, channel]
excludes: [test merchants (dim_merchants.is_test), staff wallets]
source: ref('fct_daily_payments')
owner: finance-data
reconciles_with: ledger daily closing report (tolerance 0 XAF)
```

## Anti-patterns
- Each analyst writes their own revenue SQL in the BI tool.
- Dashboards with 40 charts and no owner; KPIs without definitions or comparison.
- Averaging percentages; mixing currencies; counting app opens as "active users".
- Changing a metric's definition in place so last quarter's numbers silently move.
- **When NOT to add a semantic layer:** one BI tool and one team; documented marts are enough.

## Checks
- [ ] Every KPI on an executive dashboard has a spec in git with owner and source model.
- [ ] Money metrics reconcile with the ledger daily (singular dbt test or scheduled query, `analytics/dbt-elt`).
- [ ] Dashboards read marts/semantic layer only (BI role cannot read raw or staging schemas).
- [ ] Experiments have pre-registered success and guardrail metrics.

## Sources
- dbt Semantic Layer (MetricFlow, plan requirement): https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl
- MetricFlow (Apache-2.0): https://github.com/dbt-labs/metricflow
- Cube: https://cube.dev/docs/product/introduction
- Evidence (Evidence Core, MIT): https://docs.evidence.dev/
- Metabase docs (models, metrics): https://metabase.com/docs/latest/
- Google, Rules of Machine Learning (Rule #2: metrics first): https://developers.google.com/machine-learning/guides/rules-of-ml
