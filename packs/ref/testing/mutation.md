---
id: testing/mutation
title: Mutation testing - what it measures, where it pays (money/auth), mutmut and Stryker incremental runs in CI, reading survivors
area: testing
read_when: deciding whether tests on money, auth or permission code are strong enough; a mutation job failed; setting up mutmut or StrykerJS
verified: 2026-10-10
revisit_days: 180
sources: ["https://testing.googleblog.com/2021/04/mutation-testing.html", "https://testing.googleblog.com/2020/08/code-coverage-best-practices.html", "https://mutmut.readthedocs.io/en/latest/", "https://stryker-mutator.io/docs/stryker-js/incremental/", "https://stryker-mutator.io/docs/stryker-js/configuration/"]
---
# Mutation testing

Coverage says a line *ran*; it does not say any assertion would notice if the line were wrong. A mutation tool makes small changes to the code (flip `>` to `>=`, replace `+` with `-`, drop a call, return `None`), runs the tests for each change, and reports **survivors**: mutants no test caught. Score = caught / (caught + survived + uncovered). Google surfaces surviving mutants in code review, at most one per line, and suppresses unproductive ("arid") code such as logging.

## Decision guide

**1. Where it pays.** It is slow (the suite runs once per mutant), so aim it:
| Run it on | Skip it on |
|---|---|
| fees, prices, tax, refunds, balances, currency rounding | UI layout, copy, styling |
| auth, sessions, permission checks, token validation | generated code, migrations, config |
| parsers of untrusted input, idempotency and retry logic | logging, glue, thin controllers |
| code an AI agent wrote together with its own tests | prototypes (`spike` lane) |

**2. How eos runs it** (`eos scaffold mutation`): a CI workflow, never `eos verify`.
- On a PR, `eos mutation-plan` picks changed source files on risky paths (risk words like `billing`, `auth`, `payment` in the path, plus `lanes.risky` globs in `.eos/config.json`). With the label `lane:risky` it takes every changed source file; the weekly schedule takes all risky files.
- Python: mutmut on just those modules. Node: StrykerJS `--incremental --mutate <files>`.
- `eos mutation-score` fails the job under `MUTATION_MIN` (repository variable; default 60, Stryker's default "low" threshold). Treat the number as policy to tune, not a target.

**3. mutmut (Python, 3.x).** Needs `fork` (on Windows, use WSL). Configure in `pyproject.toml` `[tool.mutmut]`: `source_paths`, `only_mutate`, `do_not_mutate`, `mutate_only_covered_lines = true` (cuts uncovered noise). `mutmut run "pkg.billing.*"` mutates matching functions; `mutmut results` / `mutmut browse` list survivors; `mutmut apply <mutant>` writes one to disk (commit first). `mutmut export-cicd-stats` writes `mutants/mutmut-cicd-stats.json`; mutmut itself exits 0 even with survivors, which is why the score step exists. It remembers finished work, so local reruns are incremental.

**4. StrykerJS (JS/TS).** `--incremental` (since 6.2) reuses `reports/stryker-incremental.json` and re-tests only changed code and tests (test changes are tracked fully with the Jest, Vitest and CucumberJS runners; less precisely with others). `coverageAnalysis: "perTest"` runs only the tests that cover each mutant. Defaults `thresholds: { high: 80, low: 60, break: null }`; set `break` only if you want Stryker itself to fail. JSON report: `reports/mutation/mutation.json`. Cache the incremental file between CI runs if you want PR runs faster still.

**5. Reading a survivor.** For each one ask: would a user or the business notice this change?
- Yes: add or sharpen an assertion (often a boundary, `>=` vs `>`, or an exact amount instead of "is positive").
- No, the mutant behaves identically (an **equivalent mutant**): ignore it, or exclude the line/function with the tool's disable comment and a reason.
- No, but the code is pointless: delete the code.

**6. Local loop.** Run on one module while writing tests for risky code: `mutmut run "app.billing.fees.*"` or `npx stryker run --mutate src/billing/fees.ts`. A few minutes on one file beats an hour on the repo.

## Anti-patterns
- Running mutation testing on the whole repository on every PR (slow, ignored), or in pre-commit hooks.
- Chasing 100%: equivalent mutants make it impossible and the last points are rarely worth it.
- "Killing" survivors with tests that assert implementation details (call counts, private state); test behaviour (`testing/unit-design`).
- Raising the score by excluding files instead of improving tests; excluding without a reason.
- Treating a high score on code with weak oracles as proof; mutation measures tests against the mutators it knows.

## Checks
- `eos mutation-plan --json` shows what CI would mutate for the current branch; `eos mutation-score <report> --min N`.
- `eos verify` (risky lanes) prints a reminder when risky source changed; the workflow carries the gate.
- Review: survivors on money/auth lines are fixed or justified in the PR before merge (human review for money and security code).

## Sources
- Google Testing Blog, Mutation Testing (2021): https://testing.googleblog.com/2021/04/mutation-testing.html
- Google Testing Blog, Code Coverage Best Practices (2020): https://testing.googleblog.com/2020/08/code-coverage-best-practices.html
- mutmut documentation: https://mutmut.readthedocs.io/en/latest/
- StrykerJS incremental mode: https://stryker-mutator.io/docs/stryker-js/incremental/ · configuration: https://stryker-mutator.io/docs/stryker-js/configuration/
