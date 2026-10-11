---
id: llm/evals-in-production
title: Evals as a release gate and in production (regression gate in CI with thresholds and baseline, per-language and safety slices, LLM-as-judge pitfalls and calibration, online monitoring, feedback loop)
area: llm
read_when: adding an eval gate to CI for prompts, models or retrieval, validating an LLM judge, choosing pass thresholds, monitoring answer quality in production, or upgrading a model
verified: 2026-10-10
revisit_days: 90
sources: ["https://developers.openai.com/api/docs/guides/evaluation-best-practices", "https://platform.claude.com/docs/en/test-and-evaluate/develop-tests", "https://arxiv.org/abs/2306.05685", "https://www.promptfoo.dev/docs/integrations/github-action/", "https://ai.pydantic.dev/evals/"]
---
# Evals in CI and in production

Basics (datasets, grader types, non-determinism): `testing/llm-evals`. This ref is about making evals **block bad changes** and **watch live quality**. OpenAI lists "vibe-based evals" as an anti-pattern and recommends continuous evaluation on every change.

## Decision guide

**1. What counts as a change.** Prompt text, model id or snapshot, parameters (temperature, reasoning effort, max tokens), tool definitions, retrieval settings (chunking, embedding model, top-k, reranker), guardrail prompts, and provider SDK upgrades. Each runs the eval gate. Prompt files carry a `version` that must be bumped (`eos llm check`; `llm/prompts-structured-output`).

**2. The gate, concretely** (`eos scaffold llm-evals` writes it):
- `evals/llm/cases.jsonl`: one case per line with `id`, input, expectations, and `tags` (`lang:fr`, `lang:en`, `safety`, `rag`, feature names).
- A runner that calls the real model with pinned settings, grades with code first, and writes `evals/llm/results.json` (per case: id, pass, tags).
- `evals/llm/gate.json`: `min_pass_rate` overall, `min_by_tag` (e.g. `safety: 1.0`, `lang:fr: 0.85`), `max_drop` versus the committed baseline, `min_cases`.
- `eos llm gate evals/llm/results.json` fails on any breach, and on baseline cases that disappeared (deleting hard cases is not a fix). `--update` rewrites the baseline: a reviewed commit, like a snapshot update.
- CI: on PRs touching prompts, model config, evals or LLM code, run the fast code-graded set with a capped number of calls; nightly and before release run everything including judge-graded criteria. Keys come from CI secrets, never forked-PR runs.

**3. Thresholds from data, not hope.** Run the current production setup several times to see the natural spread, set `max_drop` above that noise, and gate per slice: an overall 92% can hide French at 70%. Safety cases (injection attempts, data leakage, refusing out-of-scope requests) should pass 100%.

**4. LLM-as-judge: useful, biased, must be calibrated.**
- Known biases (Zheng et al. 2023): **position** (prefers the first or second answer), **verbosity** (prefers longer), **self-enhancement** (prefers its own model family's output), and weak maths/reasoning grading. They also found strong judges agree with humans over 80% of the time, about as often as humans agree with each other, on their benchmarks.
- Mitigations: pass/fail or pairwise with order swapped both ways; a rubric with explicit criteria and examples; ask for reasoning before the verdict; control for length; use a different model family from the one being judged where possible.
- Calibrate: label 50–100 outputs by hand (native speakers for FR and local languages), measure judge–human agreement, re-check when the judge model changes. Version the judge prompt like any prompt.

**5. Online monitoring.** Offline sets miss what real users do.
- Log per request: prompt id + version, model, tokens, latency, finish reason, tool calls, retrieval ids, user feedback (`llm/observability-otel`).
- Sample production traffic (after PII redaction and within your privacy notice) and grade it asynchronously with the same graders; alert on drops by slice.
- Track cheap signals: thumbs down, regenerate, handover-to-human rate, empty/refusal rate, schema failures, `max_tokens` truncations, cost per successful task.
- Turn every confirmed failure into a new eval case (with consent and redaction).

**6. Rollouts.** New model or prompt behind a flag; shadow (run both, show the old) or a small percentage canary; compare online metrics and cost; keep the old version runnable for rollback. Providers retire snapshots: schedule the eval run before the deprecation date, not after.

**7. Tools.** A 100-line runner is fine. promptfoo (MIT) has a GitHub Action and declarative assertions; Pydantic Evals is another. Do not start on OpenAI's hosted Evals platform: OpenAI is deprecating it (read-only for existing users from 31 Oct 2026, shutdown 30 Nov 2026). Keep datasets and graders in your repo so a vendor change does not take them away. Whatever you use, the gate must produce per-case results you can diff.

## Examples
```json
{"min_pass_rate": 0.9, "min_by_tag": {"safety": 1.0, "lang:fr": 0.85}, "max_drop": 0.03, "min_cases": 30,
 "baseline": "evals/llm/baseline.json"}
```
```text
$ python3 .eos/bin/eos.py llm gate evals/llm/results.json
  error: tag lang:fr pass rate 0.78 < 0.85 (18/23)
  error: pass rate dropped 0.94 → 0.89 (max drop 0.03)
eos llm gate: FAILED (64 cases)
```

## Anti-patterns
- Changing the model "because it's newer" without running the eval; evals only on the happy path in English.
- A judge from the same model family grading its own output with no human calibration.
- Lowering thresholds or deleting failing cases to make CI green; results not kept as artefacts.
- No production sampling, so silent quality drift goes unnoticed until users leave.

## Checks
- [ ] Every LLM-affecting change runs the gate; thresholds per slice; safety slice at 100%.
- [ ] Judge agreement with human labels measured and recorded; judge prompt versioned.
- [ ] Production sampling + feedback signals monitored with alerts; failures flow back into the dataset.
- [ ] Model/prompt changes roll out behind a flag with rollback.

## Sources
- OpenAI, Evaluation best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Anthropic, Create strong empirical evaluations: https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
- Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (2023): https://arxiv.org/abs/2306.05685
- promptfoo GitHub Action: https://www.promptfoo.dev/docs/integrations/github-action/
- Pydantic Evals: https://ai.pydantic.dev/evals/
