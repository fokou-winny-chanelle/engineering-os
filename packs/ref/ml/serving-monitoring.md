---
id: ml/serving-monitoring
title: Serving and monitoring classic ML models (batch vs online scoring, training/serving skew, shadow and canary, latency and fallbacks, data and prediction drift, delayed labels, retraining triggers, rollback)
area: ml
read_when: deploying a model, choosing batch or real-time scoring, adding a fallback for model outages, setting up drift or performance monitoring, deciding when to retrain, or a model's live performance dropped
verified: 2026-10-11
revisit_days: 180
sources: ["https://developers.google.com/machine-learning/guides/rules-of-ml", "https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/", "https://papers.nips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html", "https://docs.evidentlyai.com/metrics/explainer_drift", "https://mlflow.org/docs/latest/ml/model-registry/", "https://pypi.org/project/evidently/", "https://pypi.org/project/nannyml/"]
---
# Serving and monitoring models

A model in production is a service with its own failure modes: it can be up, fast and wrong. Sculley et al. ("Hidden Technical Debt in ML Systems") list the risks: boundary erosion, entanglement, hidden feedback loops, undeclared consumers, data dependencies, configuration issues and changes in the external world. The ML Test Score (Breck et al.) turns them into 28 tests and monitoring needs. The one idea: **serve the simplest way that meets the decision's latency, monitor inputs, outputs and the business metric, and keep a non-ML fallback and a one-step rollback.**

## Decision guide

**1. Batch or online.**
| | Batch scoring (nightly/hourly job writes scores to a table) | Online scoring (API call at decision time) |
|---|---|---|
| Fits | churn, collections lists, credit limit reviews, marketing | fraud at authorisation, real-time pricing, ranking |
| Latency budget | hours | tens to hundreds of ms inside the request |
| Failure impact | stale scores (serve yesterday's, alert) | must fall back within the timeout |
| Features | warehouse SQL | precomputed online features + request data; the same definitions as training |
Prefer batch whenever the decision tolerates it: fewer moving parts, easier to reproduce and audit. Rule #8: know the freshness requirements of your system.

**2. Online serving essentials.**
- **Same feature code** for training and serving, or log serving features and train on them (Rules #29, #32); **measure training/serving skew** (Rule #37) by comparing logged serving features with recomputed training features for the same entities.
- Timeout and fallback: if the model or feature store does not answer within budget, use the rule-based score or a safe default and log it; never block payments on a model outage without a decision (`api/reliability`).
- Version in every prediction log: model version/alias, feature versions, score, threshold, decision, request id. These logs are personal data: retention and access apply.
- Thresholds live in config, owned by the business, changed with review.

**3. Releasing a new model.** Rule #9: detect problems before exporting models. Gate offline (beats champion and baseline, slices OK, `ml/experiments-reproducibility`), then **shadow** (score live traffic, take no action, compare), then **canary** (a small share of decisions, watch business and guardrail metrics), then move the registry alias (`champion`). Rollback = move the alias back; keep the previous version deployable.

**4. Monitoring layers.**
| Layer | Signal | Alert on |
|---|---|---|
| Service | latency, errors, timeouts, fallback rate | SLO burn (`ops/slo-error-budgets`) |
| Data quality | nulls, out-of-range, unseen categories, schema changes per feature | contract/test failures (`analytics/quality-contracts`) |
| Data drift | input distributions vs training reference | sustained drift on important features |
| Prediction drift | score distribution, share above threshold, alert volume | sudden shifts (often an upstream bug, not the world) |
| Performance | precision/recall when labels arrive, calibration | drop beyond tolerance per slice |
| Business | fraud losses, approval rate, default rate, complaints | movement against targets |
Rule #10: watch for silent failures, such as a feature table that stopped updating.

**5. Drift detection, concretely.** Evidently's default per-column method (version 0.7.x, Apache-2.0): with ≤ 1,000 reference rows, two-sample Kolmogorov–Smirnov for numeric columns and chi-squared for categorical (p < 0.05 means drift); with more, Wasserstein distance (numeric) and Jensen–Shannon divergence (categorical) with a 0.1 threshold. By default it does not react to more empty values, so test null shares separately. Drift is a prompt to investigate, not proof of harm: with large samples almost everything "drifts". Tie alerts to features that matter and to performance where labels exist.

**6. Delayed labels.** Fraud labels (chargebacks) and credit outcomes arrive weeks or months late. Monitor proxies meanwhile (manual review outcomes, early-payment behaviour), estimate performance on the labelled subset with its lag stated, and backfill metrics when labels land. NannyML estimates performance without labels, but its last PyPI release (0.13.1, July 2025) supports Python below 3.13 only: check maintenance before adopting.

**7. Retraining.** Triggers: schedule (with the same gate every time), confirmed performance drop, or a known change (new product, new market, policy change). Retraining on data shaped by the previous model's decisions creates feedback loops (blocked transactions never get fraud labels): keep a small random holdout of unactioned decisions where ethics and law allow, or use reviewer labels.

## Examples
Fraud scoring at authorisation: online model behind a 150 ms budget (set by the payment flow's own SLO); on timeout the existing velocity rules decide and `fallback=true` is logged. Dashboard: p95 latency, fallback rate, alert rate per hour, score histogram vs last 4 weeks, confirmed-fraud precision at 30 days lag, losses per 1,000 transactions. Weekly retrain candidate goes through gate → shadow (7 days) → 10% canary → alias move.

## Anti-patterns
- Feature logic reimplemented in the serving language; nobody measures skew.
- Monitoring only CPU and latency; the model has been scoring on a frozen feature table for a month.
- Alerting on every drifted column; alert fatigue, then nobody looks.
- Retraining automatically on every drift alert with no gate.
- **When NOT to serve online:** the decision can wait until tomorrow; a batch table is simpler, cheaper and auditable.

## Checks
- [ ] Prediction logs carry model version, features version, score, threshold, decision and request id.
- [ ] Timeout + fallback path tested; fallback rate monitored.
- [ ] Shadow/canary stage before alias move; rollback rehearsed.
- [ ] Drift, data quality, performance (with label lag) and business metrics on one dashboard with owners.

## Sources
- Google, Rules of Machine Learning (Rules #8, #9, #10, #29, #32, #37): https://developers.google.com/machine-learning/guides/rules-of-ml
- Breck et al., The ML Test Score (28 tests and monitoring needs): https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/
- Sculley et al., Hidden Technical Debt in Machine Learning Systems (NeurIPS 2015): https://papers.nips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html
- Evidently, data drift algorithm defaults: https://docs.evidentlyai.com/metrics/explainer_drift
- MLflow Model Registry (aliases): https://mlflow.org/docs/latest/ml/model-registry/
- PyPI: https://pypi.org/project/evidently/ · https://pypi.org/project/nannyml/
