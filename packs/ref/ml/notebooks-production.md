---
id: ml/notebooks-production
title: From notebooks to production (what notebooks are for, stripping outputs, secrets and data in notebooks, Jupytext text notebooks, papermill runs, nbQA linting, refactoring into tested modules, the eos notebook check)
area: ml
read_when: committing a Jupyter notebook, reviewing a notebook PR, moving notebook code into a pipeline or service, scheduling a notebook, or a notebook leaked data, credentials or huge outputs into git
verified: 2026-10-11
revisit_days: 365
sources: ["https://github.com/kynan/nbstripout", "https://github.com/jupytext/jupytext", "https://papermill.readthedocs.io/en/latest/", "https://pypi.org/project/nbqa/", "https://pypi.org/project/nbstripout/", "https://scikit-learn.org/stable/common_pitfalls.html"]
---
# Notebooks to production

Notebooks are excellent for exploring data and explaining results, and poor as production code: hidden state from out-of-order cells, outputs that leak data into git, untestable logic and unreadable diffs. The one idea: **notebooks explore and report; modules ship.** Commit notebooks without outputs, keep reusable logic in tested Python modules the notebook imports, and run anything scheduled as a script or pipeline task.

## Decision guide

**1. What belongs where.**
| Work | Where |
|---|---|
| Exploration, one-off analysis, charts for a decision memo | notebook (outputs stripped in git; export the memo as HTML/PDF outside git or to a docs store) |
| Feature definitions, transforms, training, evaluation, scoring | Python package (`src/…`) with unit tests; notebooks import it |
| Scheduled reports | a script or pipeline task; if a notebook is truly the report, run it with papermill and store the executed copy as an artefact, not in git |
| SQL transformations | dbt models (`analytics/dbt-elt`) |

**2. Outputs out of git.** nbstripout (MIT, 0.9.1) "strips output from Jupyter and IPython notebooks" and some metadata; it works as a **git filter** (`nbstripout --install`, optionally `--attributes .gitattributes`) or a **pre-commit hook** (`repo: https://github.com/kynan/nbstripout`, `id: nbstripout`). Options cover keeping counts or outputs and dropping extra metadata keys (`--extra-keys`). Why it matters: outputs hold rows of real data (customer names, phone numbers), tokens printed while debugging, and megabytes of base64 images. **`eos data check`** fails a tracked notebook that still has outputs (NB001) or execution counts (NB002), contains a secret-like string (NB003), or is unusually large (NB004, warning), so a missing hook is caught in CI.

**3. Reviewable notebooks.** Jupytext (MIT) pairs a notebook with a plain-text version, for example the `py:percent` format (`# %%` cell markers in a `.py` file), giving clear diffs and editing in any IDE. Option: commit only the `.py` paired file and treat `.ipynb` as local. nbQA runs Python linters and formatters (ruff, black, mypy…) on notebooks, so notebook code meets the same bar.

**4. Parameterised runs.** papermill parameterises and executes notebooks: tag a `parameters` cell, run `papermill in.ipynb out.ipynb -p run_date 2026-10-10`. Good for repeatable analyses; the executed notebook is an artefact with data in it, so store it with the same access rules as the data.

**5. Refactoring path (notebook → module).**
1. Restart kernel and run all; fix anything that depended on hidden state.
2. Move functions (loading, cleaning, features, metrics) into `src/<pkg>/…`; the notebook calls them.
3. Write unit tests for those functions with small fixtures (no production data).
4. Replace global variables and hard-coded paths with parameters and config.
5. Wrap fitting in a scikit-learn `Pipeline` so preprocessing is learned on training data only (scikit-learn pitfalls) and the same object serves predictions.
6. Add the entrypoint (`train.py`, a pipeline task) that logs run metadata (`ml/experiments-reproducibility`).

**6. Data and secrets in notebooks.** No production personal data on laptops (`analytics/privacy-anonymisation`); connect to governed environments with masked views. Credentials from environment variables or a secret manager, never typed into cells. If a secret was ever committed in a notebook output, rotate it: stripping later does not remove it from git history.

## Examples
```yaml
# .pre-commit-config.yaml (fragment; also in docs/ml/split-leakage-checklist.md from `eos scaffold ml`)
- repo: https://github.com/kynan/nbstripout
  rev: 0.9.1
  hooks:
    - id: nbstripout
```
```text
$ python3 .eos/bin/eos.py data check
  error: NB001 notebooks/explore_fraud.ipynb: 14 cell(s) with outputs, first at cell 2 (nbstripout; outputs leak data into git)
  error: NB003 notebooks/explore_fraud.ipynb: secret-like value in cell 7 (rotate it if it was ever committed)
```

## Anti-patterns
- `final_model.ipynb` run by hand monthly as the production pipeline.
- Notebooks with printed customer rows, API keys or 20 MB of images committed to git.
- Copy-pasting the same cleaning code across ten notebooks instead of importing one function.
- Cells that only work in a particular execution order.
- **When NOT to convert a notebook:** a finished one-off analysis that informed a decision; archive it (outputs stripped, memo exported) instead of building a pipeline.

## Checks
- [ ] Tracked notebooks have no outputs or execution counts (`eos data check` NB001/NB002; nbstripout hook installed).
- [ ] No secrets or personal data in notebooks (NB003, Semgrep/gitleaks in pre-commit).
- [ ] Logic used by pipelines lives in tested modules; scheduled work runs as scripts or tasks.
- [ ] Notebook code linted (nbQA) or paired as text (Jupytext) for review.

## Sources
- nbstripout (git filter, pre-commit hook, options): https://github.com/kynan/nbstripout · PyPI: https://pypi.org/project/nbstripout/
- Jupytext (text notebooks, py:percent): https://github.com/jupytext/jupytext
- papermill (parameterise and execute notebooks): https://papermill.readthedocs.io/en/latest/
- nbQA: https://pypi.org/project/nbqa/
- scikit-learn, Common pitfalls (pipelines prevent leakage): https://scikit-learn.org/stable/common_pitfalls.html
