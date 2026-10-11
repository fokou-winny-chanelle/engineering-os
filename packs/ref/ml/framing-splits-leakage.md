---
id: ml/framing-splits-leakage
title: Framing an ML problem, baselines, metrics tied to decisions, train/validation/test splits, and data leakage (types, detection, the eos split check)
area: ml
read_when: deciding whether a feature needs ML, defining the target and metric, choosing a baseline, splitting data for training and evaluation, reviewing results that look too good, or before reporting any model metric
verified: 2026-10-11
revisit_days: 365
sources: ["https://developers.google.com/machine-learning/guides/rules-of-ml", "https://scikit-learn.org/stable/common_pitfalls.html", "https://scikit-learn.org/stable/modules/cross_validation.html", "https://reproducible.cs.princeton.edu/", "https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html", "https://scikit-learn.org/stable/modules/calibration.html"]
---
# Framing, baselines, splits and leakage

Most ML failures are decided before the first model: the wrong target, a metric nobody acts on, or a test set that leaks the future. Google's first rule of ML is "Don't be afraid to launch a product without machine learning". The one idea: **write down the decision the model changes, beat a simple baseline on a split that mimics production, and assume leakage until you have checked for it.**

## Decision guide

**1. Framing checklist (before data work).**
- The decision: who acts on the prediction, when, and what they do differently (block a transaction, ask for a document, rank a list).
- The target: exactly what is predicted, observed when, and with what delay (chargebacks arrive weeks later; loan default needs months).
- The prediction moment: what data exists **at that moment**. Every feature must be computable then.
- Costs of errors: false positive vs false negative in money or user harm; this picks the metric and threshold.
- The baseline to beat: current rule, heuristic, or "predict the majority class". Rule #3: choose ML over a *complex* heuristic, not over a simple one that works.
- Stop condition: the gain that justifies running a model (monitoring, retraining, explanations, on-call).

**2. Metrics that match the decision.**
| Situation | Use | Avoid |
|---|---|---|
| rare positives (fraud, default) | precision and recall at the operating threshold, precision–recall curve (scikit-learn: PR is useful when classes are very imbalanced), cost-weighted error | accuracy (99.5% by predicting "no fraud") |
| scores used as probabilities (pricing, limits) | calibration (reliability curve, Brier score); scikit-learn calibration tools | raw scores from uncalibrated models |
| ranking / review queues | precision@k for the queue size reviewers can handle | global AUC alone |
| regression (amounts, demand) | MAE in business units, error by segment | RMSE only, which hides typical error |
Report confidence intervals (bootstrap) and **slices**: region, language, channel (app/USSD/web), device class, new vs returning, and protected or proxy groups where lawful (`ml/fintech-risk`).

**3. Splits that mimic production.** scikit-learn notes that the i.i.d. assumption "rarely" holds in practice.
| Data | Split | Tool |
|---|---|---|
| events over time (transactions, churn, demand) | train on the past, test on later periods, with a gap for label delay; Rule #33: train on data until January 5th, test from January 6th | `TimeSeriesSplit`, manual date cut |
| several rows per user/merchant/device | all rows of an entity in one split | `GroupKFold`, `StratifiedGroupKFold` |
| truly independent rows | stratified random split | `StratifiedKFold` |
Three sets: train (fit), validation (tune, choose thresholds), test (touched once, at the end). If you looked at the test set to make a choice, it is now a validation set.

**4. Leakage: information at training time that will not exist at prediction time.** scikit-learn: "never call fit on the test data"; split first, then fit scalers, encoders, imputers and feature selection on train only, ideally inside a `Pipeline`. Kapoor and Narayanan's running list found 41 papers across 30 fields identifying leakage-type errors affecting 648 papers. Common forms:
- **Target leakage:** features recorded after the outcome (`chargeback_reason`, `account_closed_at`, `collections_status` when predicting default).
- **Temporal leakage:** random split on time-ordered data; aggregates computed over the whole dataset (customer lifetime totals including future months).
- **Entity leakage:** the same customer in train and test, so the model memorises people.
- **Duplicate leakage:** identical or near-identical rows across splits (retries, duplicated imports).
- **Preprocessing leakage:** normalising, imputing or selecting features on all data before splitting.
- **Label-definition leakage:** labels produced by the current rule system, so the model learns the rule, not the fraud.

**5. Detect it.** Suspiciously high scores; one feature dominating importance; performance collapsing on a later time slice. `eos data split` checks split files mechanically: shared ids or groups across splits, identical rows across splits, time order (train max < test min, optional gap), and single columns that almost perfectly determine the target or have outcome-like names. `eos scaffold ml` adds a split and leakage checklist to fill in with every model.

## Examples
Fraud model, prediction at authorisation time: split by transaction date (train Jan–Jun, validation Jul, test Aug) with a 30-day gap before each boundary because labels arrive late; all transactions of a card stay in one split; features use only data before the transaction timestamp (rolling 24 h count computed as of that instant). Baseline: the current velocity rule's precision/recall at the same alert volume.
```bash
python3 .eos/bin/eos.py data split --train data/train.csv --test data/test.csv \
  --id card_id --time txn_at --gap-days 30 --target is_fraud
```

## Anti-patterns
- Random `train_test_split` on transactions; the same user on both sides.
- `StandardScaler().fit(X)` before splitting; target encoding computed on all rows.
- Reporting accuracy on a 1%-positive problem; no baseline; no slices.
- Tuning on the test set ("we tried 40 configurations and report the best test score").
- **When NOT to use ML:** the rule is simple and stable, labels are scarce or delayed beyond usefulness, or nobody will act on the score.

## Checks
- [ ] Framing note: decision, target, prediction moment, error costs, baseline, stop condition.
- [ ] Split strategy matches the data (time / group / random) and is written in the model card.
- [ ] `eos data split` passes on the exported splits; checklist from `eos scaffold ml` filled in and reviewed.
- [ ] Metrics at the operating threshold with intervals and slices; baseline reported alongside.

## Sources
- Google, Rules of Machine Learning (Rules #1, #3, #33): https://developers.google.com/machine-learning/guides/rules-of-ml
- scikit-learn, Common pitfalls (data leakage, pipelines): https://scikit-learn.org/stable/common_pitfalls.html
- scikit-learn, Cross-validation (i.i.d., grouped, time series): https://scikit-learn.org/stable/modules/cross_validation.html
- Kapoor and Narayanan, Leakage and the Reproducibility Crisis in ML-based Science: https://reproducible.cs.princeton.edu/
- scikit-learn, Precision-Recall (imbalanced classes): https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html
- scikit-learn, Probability calibration: https://scikit-learn.org/stable/modules/calibration.html
