---
id: llm/choosing-models
title: When to use an LLM, and choosing and routing models (deterministic first, model tiers, pinning, routing, batch/flex, provider landscape verified from official model pages)
area: llm
read_when: deciding whether a feature needs an LLM at all, picking a provider or model tier, setting up routing between a cheap and a strong model, or planning a model upgrade
verified: 2026-10-10
revisit_days: 60
sources: ["https://www.anthropic.com/engineering/building-effective-agents", "https://developers.openai.com/api/docs/models", "https://developers.openai.com/api/docs/guides/model-selection", "https://platform.claude.com/docs/en/about-claude/models/overview", "https://ai.google.dev/gemini-api/docs/models", "https://docs.mistral.ai/getting-started/models/", "https://arxiv.org/abs/2406.18665", "https://developers.openai.com/api/docs/guides/batch", "https://platform.claude.com/docs/en/build-with-claude/batch-processing", "https://developers.openai.com/api/docs/guides/flex-processing"]
---
# When to use an LLM, and which model

An LLM is a slow, costly, non-deterministic function that is very good at reading and writing language. Use it where that strength is the product, and keep everything else in ordinary code. Anthropic's advice after working with many teams: find the simplest solution, add complexity only when needed, and often a single well-prompted call with retrieval is enough.

## Decision guide

**1. Deterministic code first.** Use code (rules, SQL, regex, a lookup table, a classic classifier) when:
- the answer must be exact, auditable or repeatable: money, tax, balances, permissions, dates, unit conversion;
- the input is already structured (form fields, a mobile money callback, a CSV);
- the rule fits in a decision table someone can review.

Use an LLM when the input is free text, speech or images, or the output is language: extract fields from a messy invoice photo, classify a WhatsApp message, draft a reply, summarise, translate, answer from documents. A common shape: **the LLM turns language into structured data; code validates it and does the action.**

**2. Write down what "good" means before choosing a model.** Success criteria, a small eval set (`llm/evals-in-production`), a latency budget (time to first token and total) and a cost budget per request or per user per month. Without them, model choice is guesswork.

**3. Providers and tiers (official model pages, read 2026-10-10).** Each big provider sells a strong, a balanced and a cheap/fast tier. Names change every few months, so re-check the models page before you pin.
| Provider | Strong | Balanced | Fast / cheap | Notes |
|---|---|---|---|---|
| OpenAI | GPT-6 Astra | GPT-6.1 Sol | GPT-6 Luna | reasoning effort setting per request; Responses API |
| Anthropic | Claude Fable 5.1 / Opus 5.5 | Sonnet 5.5 | Haiku 5.5 | 1M-token context on all four; dated retirement ("not sooner than") per model |
| Google | Gemini 3.1 Pro (preview) | Gemini 3.8 Flash | Flash-Lite | stable, preview, `-latest` (hot-swapped) and experimental names |
| Mistral | Mistral Large 4 | Medium 3.5 | Small 4, Ministral 3 | several open-weight models (Apache 2.0) you can self-host |

Prices are on each provider's pricing page; they change and are not repeated here.

**4. Pick the cheapest tier that passes your evals.** OpenAI's model-selection guide says the same: try the same inputs on several models and settings and keep the lightest one that meets your quality bar. Start with the balanced tier to prove the feature, then try the cheap tier on the eval set; move up only for the cases that fail.

**5. Pin versions; treat upgrades as changes.** Use a stable or dated model id, never a `-latest` alias in production (Gemini's `-latest` alias is hot-swapped with two weeks' email notice for breaking changes). Record the model id and settings next to the prompt (`llm/prompts-structured-output`). Every model change runs the full eval set before switching, and the old id stays configured as a rollback.

**6. Route only when the data says so.** Routing sends easy requests to a cheap model and hard ones to a strong model (Anthropic lists it as a workflow pattern; RouteLLM reports cost cut by more than 2x on some benchmarks without losing quality). Options, simplest first: route by request type in code (a known task gets a known model); a cheap classifier call; escalate to the strong model when the cheap answer fails validation. Measure on your eval set that routing saves money without losing quality.

**7. Not everything is real time.** Back-office jobs (nightly summaries, re-embedding, eval runs, enrichment) can use batch APIs: OpenAI and Anthropic both document a 50% discount with up to 24-hour turnaround. OpenAI's flex tier is cheaper but slower with occasional unavailability.

**8. Open-weight and self-hosted** (gpt-oss, Mistral's Apache-2.0 models and others) make sense for strict data residency, offline/edge use or very high volume. You then own GPUs, scaling, safety filtering and upgrades; compare total cost honestly.

**9. Keep the provider swappable.** Put calls behind one small module (`complete(task, input) -> typed result`) so the model, provider or SDK can change in one place. A framework is optional (`llm/frameworks`).

## Examples
- Invoice photo → fields: cheap vision-capable tier with structured output; code checks totals (sum of lines = total) and the tax ID format; failures go to a stronger model, then to a human.
- "Is this message a payment complaint?": try the cheap tier with five labelled examples; if the eval passes at 98%, ship it; keep a keyword rule as a fallback when the API is down.
- Never use an LLM to compute the XAF amount due; it may read the amount, code computes and checks it.

## Anti-patterns
- An LLM for a job a regex, SQL query or rule table does exactly.
- Choosing the strongest model "to be safe" with no eval or cost budget; switching on a release note.
- `-latest` aliases in production; model ids scattered through the codebase.
- Letting the model do arithmetic, permission decisions or final money movements.

## Checks
- [ ] A written reason why this feature needs an LLM, and what code does around it.
- [ ] Success criteria, eval set, latency and cost budget exist before model choice.
- [ ] Model ids pinned in one config place, with a rollback id; upgrade runs the full eval.
- [ ] Offline/batch work uses batch or flex pricing where the provider offers it.

## Sources
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- OpenAI models: https://developers.openai.com/api/docs/models · model selection: https://developers.openai.com/api/docs/guides/model-selection
- Anthropic models overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Gemini models (version name patterns): https://ai.google.dev/gemini-api/docs/models
- Mistral models: https://docs.mistral.ai/getting-started/models/
- RouteLLM (Ong et al., 2024): https://arxiv.org/abs/2406.18665
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch · Flex processing: https://developers.openai.com/api/docs/guides/flex-processing
- Anthropic Message Batches: https://platform.claude.com/docs/en/build-with-claude/batch-processing
