---
id: ml/experiments-reproducibility
title: Features, experiment tracking, model registry and reproducibility (feature engineering rules, point-in-time joins, MLflow tracking and aliases, DVC and lakeFS data versioning, seeds and lockfiles, model cards and datasheets)
area: ml
read_when: engineering features, setting up experiment tracking or a model registry, versioning datasets, making a training run reproducible, choosing DVC vs lakeFS vs snapshots, or writing a model card
verified: 2026-10-11
revisit_days: 180
sources: ["https://developers.google.com/machine-learning/guides/rules-of-ml", "https://docs.feast.dev/", "https://raw.githubusercontent.com/treeverse/lakeFS/master/LICENSE", "https://mlflow.org/docs/latest/ml/model-registry/", "https://mlflow.org/docs/latest/ml/model-registry/workflow/", "https://dvc.org/doc/start", "https://docs.lakefs.io/", "https://arxiv.org/abs/1810.03993", "https://arxiv.org/abs/1803.09010", "https://pypi.org/project/mlflow/", "https://pypi.org/project/dvc/"]
---
# Features, experiments and reproducible runs

A model result counts only if someone else can re-run it from the commit and get the same numbers (the data-ml pack's first standard). The one idea: **every run records code SHA, environment lockfile, data version, config and seed, and every deployed model points back to that run.** Splits and leakage: `ml/framing-splits-leakage`; serving: `ml/serving-monitoring`.

## Decision guide

**1. Feature engineering rules** (Google, Rules of ML):
- Start with directly observed and reported features rather than learned ones (Rule #17); combine them in human-understandable ways (Rule #20).
- Give feature columns owners and documentation (Rule #11); clean up features you no longer use (Rule #22).
- Re-use code between training and serving (Rule #32), or log the features used at serving time and train on those logs (Rule #29), to avoid training/serving skew.
- Point-in-time correctness: each training row may only use values known at its timestamp. Feature stores such as Feast (Apache-2.0, 0.66) generate "point-in-time correct feature sets" so future values do not leak; for a small team, an SQL `ASOF`-style join on `valid_from`/`valid_to` or event time does the same.
- For mobile money and lending: velocity counts (transfers in the last 1 h/24 h/7 d as of the event), merchant category, device and SIM-change recency, account age, channel; never raw phone numbers or names (`analytics/privacy-anonymisation`).

**2. What to version, and how.**
| Thing | How |
|---|---|
| Code | git SHA recorded in every run; no training from uncommitted changes (check `git status` in the training entrypoint) |
| Environment | lockfile (uv/pip-tools/conda-lock) and container image digest; CUDA/driver versions for GPU work |
| Data | an immutable snapshot id: DVC (`.dvc` files in git pointing at content-addressed storage), lakeFS (Git-like branches and commits over object storage), warehouse table snapshots or time travel, or a dated Parquet path that is never overwritten |
| Config and hyperparameters | a file in git, logged with the run |
| Randomness | seeds for Python, NumPy and the framework, logged; note that some GPU kernels stay non-deterministic, so record tolerance |
| Outputs | model artefact hash, metrics, evaluation report, plots |

**3. Choosing data versioning.**
| Option | Fits | Watch out |
|---|---|---|
| Dated immutable paths + manifest (row counts, hashes) | small teams, data in a warehouse or bucket | discipline: nobody overwrites |
| DVC (3.67, Apache-2.0) | files and datasets used by Python training; pipelines (`dvc.yaml`) with cached stages | remote storage to set up and secure |
| lakeFS (server now under the Business Source License 1.1 on its main branch; production use allowed with conditions such as unmodified and internal-only; the Python client is Apache-2.0) | data lakes on object storage needing Git-like branches, commits and merges for data | a service to run; have the licence reviewed |
| Warehouse snapshots / time travel | training data built in the warehouse | retention windows limit how far back you can go |

**4. Experiment tracking and registry.** MLflow (3.17 on PyPI, Apache-2.0) logs params, metrics and artefacts per run and has a model registry. Its docs mark **model stages as deprecated**; use **aliases** instead: a mutable named reference such as `champion` pointing at a version, loaded with `models:/MyModel@champion`. Promotion = moving the alias after the evaluation gate passes; rollback = moving it back. Hosted trackers are fine if the data residency and retention fit (no personal data in run params or artefact names).

**5. Model cards and datasheets.** A model card (Mitchell et al.) states intended use, out-of-scope uses, training data, metrics overall and by slice, ethical considerations and limitations; a datasheet (Gebru et al.) documents how a dataset was collected, its composition and recommended uses. Keep both in git next to the code; `eos scaffold ml` adds templates. Update them on every promoted version.

**6. Run gate before promotion.** The candidate must beat the current champion and the baseline on the same frozen test split, with no slice regressing beyond a set tolerance, and the run must be reproducible (re-run on CI or a second machine within tolerance).

## Examples
```python
# train.py (essentials)
run_meta = {
    "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "data_version": "s3://ml/fraud/snapshots/2026-09-30/manifest.json",
    "seed": 20261011,
    "lockfile_sha256": sha256_file("uv.lock"),
}
with mlflow.start_run():
    mlflow.log_params({**params, **run_meta})
    ...
    mlflow.log_metrics({"recall_at_1pct_alerts": r, "precision_at_1pct_alerts": p})
# after the gate: client.set_registered_model_alias("fraud-scorer", "champion", version)
```

## Anti-patterns
- "Final_v3_really_final.ipynb" as the model of record; results that only exist on one laptop.
- Training data rebuilt from live tables each run, so last month's model cannot be reproduced.
- Feature logic written twice (pandas for training, SQL or Kotlin for serving) and drifting apart.
- Moving the `champion` alias by hand without an evaluation record.
- **When NOT to add MLflow/DVC/lakeFS:** a single quarterly model with a small dataset; a git-tracked script, a dated immutable snapshot and a results JSON committed with the code are enough.

## Checks
- [ ] Every run logs git SHA, lockfile hash, data version, config and seed; training refuses a dirty tree for registered runs.
- [ ] Training and serving share feature code, or serving features are logged and reused.
- [ ] Registry uses aliases; promotion needs a passing evaluation record linked to the run.
- [ ] Model card and datasheet present and updated per promoted version (`eos scaffold ml`).

## Sources
- Google, Rules of Machine Learning (Rules #11, #17, #20, #22, #29, #32): https://developers.google.com/machine-learning/guides/rules-of-ml
- Feast (point-in-time correct features): https://docs.feast.dev/
- MLflow Model Registry (aliases): https://mlflow.org/docs/latest/ml/model-registry/ · workflow (stages deprecated): https://mlflow.org/docs/latest/ml/model-registry/workflow/
- DVC: https://dvc.org/doc/start · lakeFS: https://docs.lakefs.io/ · lakeFS licence (BSL 1.1): https://raw.githubusercontent.com/treeverse/lakeFS/master/LICENSE
- Mitchell et al., Model Cards for Model Reporting: https://arxiv.org/abs/1810.03993
- Gebru et al., Datasheets for Datasets: https://arxiv.org/abs/1803.09010
- PyPI: https://pypi.org/project/mlflow/ · https://pypi.org/project/dvc/
