---
id: testing/llm-evals
title: Testing LLM features with evals - datasets, graders (code, model, human), regression gates in CI, non-determinism
area: testing
read_when: building or changing a feature that calls an LLM (prompt, model, retrieval, tool use), choosing how to grade outputs, adding an eval gate to CI, or a model/provider upgrade
verified: 2026-10-10
revisit_days: 90
sources: ["https://platform.openai.com/docs/guides/evaluation-best-practices", "https://platform.claude.com/docs/en/test-and-evaluate/develop-tests", "https://www.promptfoo.dev/docs/intro/"]
---
# Testing LLM features (evals)

Unit tests check deterministic code. An LLM feature also needs **evals**: a dataset of realistic inputs, a grader that scores each output against written criteria, and a pass threshold that gates changes to prompts, models, retrieval or tools. Without them every change is judged by "it looked fine on three examples" (OpenAI calls this vibe-based evaluation). Prompt-injection and misuse evals: `security/llm-agent-security` and the agent-security pack.

## Decision guide

**1. Test the deterministic parts normally.** Prompt assembly, tool-call schema validation, output parsing, retries, rate limiting, redaction and cost caps are ordinary code: unit and integration tests with the model call stubbed (record a few real responses as fixtures). Only the model's judgement needs evals.

**2. Define success first** (Anthropic). Specific and measurable for the task: "extracts the invoice total within 1 cent on 98% of cases", "answers only from the provided documents", "refuses to give medical dosage". Cover the happy path, edge cases (empty, very long, other languages, ambiguous), and abuse cases.

**3. Build the dataset.**
- Start small with real or realistic cases; grow it from production failures and user reports. Volume of automatically graded cases beats a few hand-graded ones (Anthropic).
- Make it look like production traffic (OpenAI lists unrepresentative datasets as an anti-pattern): real lengths, languages, typos. Remove personal data first (`testing/test-data`).
- Keep a held-out set that prompt authors (human or agent) do not tune against.

**4. Pick the grader, cheapest that works.**
| Grader | Use for | Notes |
|---|---|---|
| Code | exact match, JSON schema, regex, numeric tolerance, "cited a source id", tool called with the right arguments | fastest, deterministic: prefer it |
| Similarity | paraphrase consistency (embedding cosine), summary overlap (ROUGE-L) | weak proxy; calibrate |
| Model (LLM-as-judge) | tone, faithfulness to sources, rubric criteria | use a clear rubric with a pass/fail line, ask for reasoning before the score, prefer pairwise or criteria checks over open "rate 1-10"; models favour longer answers, so control for length; check agreement with human labels before trusting it |
| Human | calibrating the other graders, high-stakes launches | slow; sample, use a rubric, take consensus |

**5. Handle non-determinism.** Outputs vary run to run. Pin the model version and settings in the eval config, run each case several times where it matters, and gate on a pass rate per criterion (for example "≥ 95% of cases pass schema, ≥ 90% faithful") rather than on a single run. Compare against the current production prompt/model, not against perfection.

**6. Wire it in.**
- On PRs that touch prompts, model config, retrieval or tool definitions: run the fast code-graded subset (minutes, a capped number of API calls).
- Nightly or before release: the full set, including model-graded criteria.
- Every model or provider upgrade is a change: run the full set before switching. Keep results (score per case) as artefacts to diff.
- Tools: a small script in your test framework is enough to start; promptfoo (MIT) is an open-source CLI with declarative test cases for evals and red-teaming. eos's own `eos library eval` is a minimal example of rubric-based grading with regexes.

**7. After launch, keep evaluating.** Sample production traffic (with consent and redaction), grade it the same way, and feed failures back into the dataset.

## Anti-patterns
- Judging prompt changes by eye on a handful of examples; one generic metric ("helpfulness") for everything.
- An LLM judge with no rubric, the same model grading itself, or never checked against humans.
- Exact-match assertions on free text in unit tests (flaky); real API calls in the unit suite.
- Tuning the prompt against the whole eval set until it passes (overfitting); no held-out cases.
- Upgrading the model because a release note says it is better, without running your evals.

## Checks
- Repository has an eval set (cases + rubric + threshold) next to each LLM feature; CI runs the code-graded subset on relevant changes.
- Eval config pins model ids and parameters; API keys come from CI secrets, never from the repo.
- Review: prompt/model PRs show before/after eval scores.

## Sources
- OpenAI, Evaluation best practices: https://platform.openai.com/docs/guides/evaluation-best-practices
- Anthropic, Define success criteria and build evaluations: https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
- promptfoo documentation: https://www.promptfoo.dev/docs/intro/
