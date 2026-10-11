---
id: testing/property-fuzz
title: Property-based testing and fuzzing - Hypothesis, fast-check, stateful/model-based tests, coverage-guided fuzzers
area: testing
read_when: testing parsers, serialisers, money maths, state machines or anything with many input combinations; reproducing a property failure; deciding whether to fuzz
verified: 2026-10-10
revisit_days: 180
sources: ["https://hypothesis.readthedocs.io/en/latest/reference/api.html", "https://hypothesis.readthedocs.io/en/latest/stateful.html", "https://fast-check.dev/docs/core-blocks/runners/", "https://fast-check.dev/docs/configuration/", "https://fast-check.dev/docs/tutorials/quick-start/read-test-reports/", "https://fast-check.dev/docs/advanced/model-based-testing/", "https://github.com/dubzzz/fast-check/blob/main/packages/fast-check/src/check/runner/configuration/Parameters.ts", "https://github.com/google/atheris", "https://github.com/CodeIntelligenceTesting/jazzer.js", "https://go.dev/doc/security/fuzz/", "https://google.github.io/clusterfuzzlite/"]
---
# Property-based testing and fuzzing

An example test checks one input you thought of. A property test states a rule that holds for *all* valid inputs, lets the library generate hundreds of them, and shrinks any failure to a minimal case. Fuzzers go further and search for crashes guided by code coverage. API fuzzing from an OpenAPI spec (Schemathesis) is in `api/testing`; security fuzzing in `security/security-testing`.

## Decision guide

**1. Where it pays.** Parsers and serialisers, money splitting and rounding, date and time-zone logic, permission matrices, state machines, data migrations, anything with a simple reference implementation. Skip it for glue code and UI layout.

**2. Property patterns** (templates: `eos scaffold property-python`, `property-node`).
| Pattern | Property | Example |
|---|---|---|
| Invariant | always true after the operation | shares of a split add up to the total and differ by at most one cent |
| Round trip | `decode(encode(x)) == x` | JSON, CSV export/import, URL state |
| Oracle | equals a slow, obviously correct version | optimised price calculation vs a naive loop |
| Idempotence | `f(f(x)) == f(x)` | normalising an email, applying a migration twice |
| Metamorphic | a known change to input gives a known change to output | doubling all prices doubles the total |
| Model-based / stateful | random sequences of operations keep the system equal to a simple model | cart, ledger, rate limiter |

**3. Hypothesis (Python, MPL-2.0).**
- Defaults: 100 examples per test, a 200 ms deadline per example. When the `CI` environment variable is set, the built-in `ci` profile loads automatically: derandomised, no deadline, no example database, prints a reproduction blob.
- Register extra profiles before tests load (in `conftest.py`, as the tests-python scaffold does with `nightly`, 2000 examples) and select with `--hypothesis-profile=nightly`.
- Failing inputs are saved in `.hypothesis/examples` and retried first next run; add the shrunk case as `@example(...)` so it always runs (explicit examples do not shrink).
- Build inputs with strategies that match the domain (`st.integers(min_value=0)`, `st.decimals(places=2)`, `st.builds(Order, ...)`), not `assume()` filters that discard most examples.
- Stateful: subclass `RuleBasedStateMachine`, define `@rule` steps, `@initialize` and `@invariant` checks.

**4. fast-check (TypeScript/JavaScript, MIT).**
- `fc.assert(fc.property(arbs..., predicate), params)`; default 100 runs (`numRuns`). Set shared defaults once with `fc.configureGlobal`.
- A failure prints `{ seed, path }`: pass them back to `fc.assert` to replay the exact counterexample; then keep it as a pinned example (`examples: [...]`).
- Model-based: `fc.commands([...])` with `fc.modelRun` (async variants exist) to check sequences of actions against a model.

**5. Fuzzing.** Coverage-guided fuzzers mutate inputs to reach new code; best for parsers, decoders and file handlers. Python: Atheris (coverage-guided, also fuzzes native extensions). Go: built in since 1.18 (`go test -fuzz=FuzzX -fuzztime=…`; the corpus lives in `testdata/fuzz`). Node: Jazzer.js. Run fuzzers on a schedule or with ClusterFuzzLite on PRs, keep the corpus, and turn every crash into a regression test.

**6. Running them in the lanes.** Property tests are ordinary tests: they run with the suite (100 examples is fast). Long runs (thousands of examples, fuzzing for minutes) go in a nightly job, never in `eos verify`.

## Anti-patterns
- Re-implementing the function under test inside the property (the test shares its bugs); use a simpler oracle or a weaker invariant.
- `assume()` or `.filter()` rejecting most inputs; health-check warnings ignored.
- Unbounded generators on slow code, then raising the deadline instead of bounding sizes.
- Fixing a property failure without adding the counterexample as an explicit example.
- Random tests with no printed seed (not reproducible).

## Checks
- `eos scaffold property-python` / `property-node`: invariant, round-trip and oracle templates that pass as generated.
- CI: the default profile on every PR; a nightly job with `--hypothesis-profile=nightly` or a higher `numRuns`; fuzz jobs on schedule.
- Review: money and parsing code changes come with at least one property, and failures found become pinned examples.

## Sources
- Hypothesis API reference (settings, profiles, `@example`, database): https://hypothesis.readthedocs.io/en/latest/reference/api.html · stateful testing: https://hypothesis.readthedocs.io/en/latest/stateful.html
- fast-check runners: https://fast-check.dev/docs/core-blocks/runners/ · configuration: https://fast-check.dev/docs/configuration/ · reading reports: https://fast-check.dev/docs/tutorials/quick-start/read-test-reports/ · model-based testing: https://fast-check.dev/docs/advanced/model-based-testing/ · numRuns default: https://github.com/dubzzz/fast-check/blob/main/packages/fast-check/src/check/runner/configuration/Parameters.ts
- Atheris: https://github.com/google/atheris · Jazzer.js: https://github.com/CodeIntelligenceTesting/jazzer.js · Go fuzzing: https://go.dev/doc/security/fuzz/ · ClusterFuzzLite: https://google.github.io/clusterfuzzlite/
