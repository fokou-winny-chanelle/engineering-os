---
id: testing/coverage-ai-code
title: Coverage (what it means, ratchets, changed-line gates) and testing AI-written code without test cheating
area: testing
read_when: setting or arguing about coverage targets, a diff-coverage gate failed, reviewing tests an AI agent wrote, or an agent changed, skipped or weakened tests to get green
verified: 2026-10-10
revisit_days: 120
sources: ["https://testing.googleblog.com/2020/08/code-coverage-best-practices.html", "https://coverage.readthedocs.io/en/latest/branch.html", "https://coverage.readthedocs.io/en/latest/config.html", "https://vitest.dev/config/coverage", "https://github.com/Bachmann1234/diff_cover", "https://arxiv.org/abs/2510.20270", "https://metr.org/blog/2025-06-05-recent-reward-hacking/"]
---
# Coverage and testing AI-written code

Coverage tells you which code no test executed. It does not tell you that executed code is checked: a test with no assertion covers everything it calls. Use it to find untested code, not to prove tests are good (mutation testing, `testing/mutation`, does that better).

## Decision guide

**1. Kinds of coverage.** Line (statement) coverage is the default; branch coverage also requires both sides of each `if` (coverage.py `[run] branch = true`; Vitest's v8 and istanbul providers report branches too). Prefer branch coverage on money, auth and parsing code.

**2. Targets, from Google's guidance.** No ideal number; 60% "acceptable", 75% "commendable", 90% "exemplary" for a project, and chasing 90→95% is rarely worth it. Per-commit (changed-line) coverage of 99% is reasonable with 90% as a good lower threshold. What is *not* covered matters more than the percentage.

**3. Gate changed lines, ratchet the total.**
- **Diff coverage** (the gate): `eos diff-coverage coverage.xml --base origin/main` checks only lines added in this branch, from Cobertura XML (pytest-cov `--cov-report=xml`) or LCOV (the `lcov` reporter in Vitest or Jest, `flutter test --coverage`). Defaults: 80% for all changed lines, 90% for changed lines on risky paths (money/auth words, `lanes.risky`); tune in `.eos/config.json` → `testing`. New source files missing from the report are listed as unmeasured. The stack CI templates run it on pull requests; the `risky` lane of `eos verify` runs it on a fresh local report. The open-source `diff-cover` tool does the same job if you prefer it (`--compare-branch`, `--fail-under`).
- **Ratchet** the project total instead of a fixed high bar: coverage.py `fail_under` raised as coverage grows, or Vitest `coverage.thresholds.autoUpdate`, which raises thresholds when coverage improves. Never lower a threshold without a human (`eos test-integrity` flags it).

**4. What not to cover.** Generated code, migrations, thin `main` entry points, vendored code: exclude by config with a comment, not with scattered `# pragma: no cover`. Trivial getters do not need tests just for the number.

**5. AI agents and test cheating.** Coding agents sometimes make tests pass without fixing the code. ImpossibleBench (2025) built tasks whose tests contradict the spec, so any pass is cheating; models cheated often, from editing tests to operator overloading, and the rate depended on prompt, test access and feedback loop. METR saw recent models patch scorers and timers; telling the model "please do not cheat" barely changed the rate. So enforce with tooling and review, not instructions alone.
| Cheat | Defence in eos |
|---|---|
| delete or skip a failing test, add `xfail`/`.only`, loosen an assertion, lower a threshold | `eos test-integrity` flags new skips, removed asserts, lowered thresholds and gate-config edits (incl. `tests/quarantine.json`) for human approval; protected paths (`.eos/protected.txt`) cover CI workflows and lockfiles |
| special-case the test input (`if input == "test@example.com"`) or hard-code the expected value | property tests and held-out examples the agent did not see (`testing/property-fuzz`); review |
| mock the unit under test, assert on the mock | review against `testing/unit-design`; mutation testing on risky code |
| patch the clock, the test runner or `conftest.py` | conftest/config changes show up as gate changes; review |
| "all tests pass" without running them | `eos verify` and CI are the source of truth, not the agent's summary |

**6. Workflow for agent-written tests.** Write or approve the acceptance tests (or at least their names and cases) before the agent implements. Ask for tests that fail first, then pass. Read the diff of tests before the diff of code. Keep the rule from the testing pack: if a test is wrong, the agent stops and explains; it does not edit the test to pass. Agent sessions themselves: `security/llm-agent-security`.

## Anti-patterns
- A project-wide 100% mandate (produces assertion-free tests and `no cover` pragmas).
- Coverage as the only quality signal; coverage gates on total only, so new code can be untested if old code is well covered.
- Lowering thresholds or excluding files to pass a gate; accepting "fixed the tests" from an agent without reading them.
- Generating tests from the implementation ("snapshot what it does") for logic that is supposed to match a spec.

## Checks
- `eos diff-coverage <report> [--base ref] [--min N --risky-min N] [--json]`: exit 1 below threshold, 2 when no report; writes to the GitHub step summary.
- Stack CI: "Diff coverage" step on pull requests (repository variable `DIFF_COVERAGE_MIN` overrides).
- `eos test-integrity --base origin/main` in CI; the code-review pack requires it clean or explained.

## Sources
- Google Testing Blog, Code Coverage Best Practices (2020): https://testing.googleblog.com/2020/08/code-coverage-best-practices.html
- coverage.py branch coverage: https://coverage.readthedocs.io/en/latest/branch.html · configuration (`fail_under`): https://coverage.readthedocs.io/en/latest/config.html
- Vitest coverage config (`thresholds.autoUpdate`): https://vitest.dev/config/coverage · diff-cover: https://github.com/Bachmann1234/diff_cover
- Zhong, Raghunathan, Carlini, ImpossibleBench (2025): https://arxiv.org/abs/2510.20270
- METR, Recent Frontier Models Are Reward Hacking (2025): https://metr.org/blog/2025-06-05-recent-reward-hacking/
