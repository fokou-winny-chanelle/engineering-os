---
id: data-ml
title: Data pipelines and machine learning
kind: phase
mode: files
when: editing notebooks, data pipelines, feature code, training or evaluation code, or model serving
description: Use for data pipelines, notebooks, training, evaluation and model serving. Reproducible data and runs, leakage checks, eval sets, model cards, monitoring drift.
globs: ["**/*.ipynb", "**/notebooks/**", "**/pipelines/**", "**/dags/**", "**/dbt_project.yml", "**/models/**/*.sql", "**/dvc.yaml", "**/train*.py", "**/eval*.py", "**/features/**"]
next: [testing-qa, operations]
---
# Data pipelines and machine learning

## Entry
A question or product metric the data or model must serve, a named owner for the data, and a baseline (current metric, or a simple heuristic) to beat.

## Standards
1. **Reproducible runs.** Pin code, environment (lockfile), data version (DVC/LakeFS/snapshot ID), config and random seeds. Log every run (MLflow or similar) with params, data version, metrics and artefact hashes. A result nobody can re-run doesn't count.
2. **Notebooks explore; modules ship.** Move logic into tested modules before it reaches a pipeline or production. Strip notebook outputs in git (nbstripout).
3. **Data contracts.** Schema, types, nullability and ranges are checked at ingestion (pandera, Great Expectations, dbt tests). Bad rows are quarantined, not silently dropped. Pipelines are idempotent: re-running a day gives the same result.
4. **Leakage and splits.** Split before any fitting, scaling or feature selection. Split by time for forecasting and by entity for user data. Keep a held-out test set that is touched once. Check for target leakage (features that won't exist at prediction time).
5. **Evaluation that matches the product.** Use a baseline, metrics tied to the decision (precision at the operating threshold, cost-weighted error), slices (region, device, language, new vs returning users) and confidence intervals. For LLM features: a versioned eval set, regression runs on every prompt or model change, and LLM-as-judge only with a rubric, a different judge model and human spot checks.
6. **Privacy.** Minimise and pseudonymise personal data. Have a lawful basis for training use. No production PII in notebooks on laptops. Document retention.
7. **Serving.** The same feature code in training and serving (or a feature store). Version the model, have a rollback, use shadow or canary releases, and set latency and cost budgets.
8. **Monitoring.** Track input drift, prediction drift, data freshness and the business metric, with alerts and a retraining or rollback runbook.
9. **Document.** A model card (purpose, data, metrics by slice, limits, owner) and a datasheet for new datasets.

## Deliverables
- Pipeline or model code with tests, a run log link, eval report with slices, model card, and a monitoring plan.

## Automated checks
- Unit tests for transforms, dbt tests, an eval regression gate for model or prompt changes. `eos data check` (ODCS contracts incl. breaking changes vs base, notebooks without outputs or secrets), `eos data split` (leakage across split files), `eos scaffold analytics` (dbt + contracts + PII-in-events Semgrep), `eos scaffold ml` (split checklist, model card).

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `analytics/architecture` · `analytics/dbt-elt` · `analytics/pipelines-orchestration` · `analytics/quality-contracts` · `analytics/product-events` · `analytics/metrics-dashboards` · `analytics/privacy-anonymisation` · `ml/framing-splits-leakage` · `ml/experiments-reproducibility` · `ml/serving-monitoring` · `ml/fintech-risk` · `ml/notebooks-production` · `data/nosql-analytics` · `llm/rag` · `llm/evals-in-production`.

## Exit checklist (Definition of Done)
- [ ] The run can be reproduced from the commit plus the data version.
- [ ] Beats the baseline on the held-out set, with slices reviewed and no leakage found.
- [ ] Data contracts and privacy review done. Model card written.
- [ ] Monitoring, alerts and rollback ready before traffic.

## Handoff → testing-qa / operations
Pass the eval report, model card, monitoring dashboards and the retraining runbook.

## Stop & escalate
Stop on use of personal or sensitive data without a confirmed lawful basis, on fairness concerns across slices, or when the metric gain is within noise.
