---
id: llm/reliability-cost
title: Reliability and cost control for LLM calls (timeouts, retries with Retry-After, fallbacks, rate limits and quotas, streaming, prompt caching, response caching, batch, spend caps and Denial of Wallet)
area: llm
read_when: calling a model API from a request path or job, setting timeouts and retries, adding a fallback provider, streaming answers, using prompt caching or batch, or capping spend per user, tenant or day
verified: 2026-10-10
revisit_days: 60
sources: ["https://github.com/openai/openai-python", "https://developers.openai.com/api/docs/guides/rate-limits", "https://platform.claude.com/docs/en/api/errors", "https://developers.openai.com/api/docs/guides/prompt-caching", "https://platform.claude.com/docs/en/build-with-claude/prompt-caching", "https://developers.openai.com/api/docs/guides/spend-limits", "https://developers.openai.com/api/docs/guides/latency-optimization", "https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/"]
---
# Reliability and cost

A model API is a slow, rate-limited, metered, sometimes-overloaded dependency. Treat it like a payment provider: explicit timeouts, bounded retries, idempotent work, a budget, and a plan for when it is down. General patterns: `api/reliability`, `api/rate-limits-auth`, `ops/capacity-cost`.

## Decision guide

**1. Set timeouts yourself.** The official OpenAI SDKs default to a **10-minute** timeout and 2 retries; Anthropic's SDK also retries twice by default. Ten minutes is wrong for a web request. Set a per-call timeout from your latency budget (e.g. 20–30 s for chat, longer for batch jobs), always set `max_output_tokens` / `max_tokens`, and stream long generations (Anthropic recommends streaming or batch for long requests and returns 504 `timeout_error` otherwise).

**2. Retry only what is transient, and listen to the server.**
- Retry: connection errors, 408, 429 rate limits, 5xx, Anthropic 529 `overloaded_error`, OpenAI 503 `server_is_overloaded`. Honour `Retry-After` when present (OpenAI documents it as the minimum wait); otherwise exponential backoff **with jitter**.
- Do not retry: 400/422 validation errors, auth errors, content refusals, or 429s caused by a **hard spend limit or exhausted quota** (OpenAI's hard spend limit returns 429 too: read the error code).
- One retry layer only: if you wrap the SDK, set its `max_retries` to 0 or account for its retries in your budget. Retries multiply cost and latency; cap total attempts and total time.
- Streams can fail after a 200 (mid-stream error events): handle partial output and decide whether to resume, retry or show what arrived.

**3. Fallbacks, chosen in advance.** Same model in another region or a second provider, a smaller model, a cached answer, or a graceful "try again" with the request saved. A fallback model must pass the same eval (`llm/evals-in-production`) and the same privacy terms (`llm/privacy-residency`); prompts often need per-provider variants. Use a circuit breaker so a dead provider is not hammered.

**4. Rate limits and quotas are yours too.** Provider limits are per organization/project (requests and tokens per minute). Add your own per-user, per-tenant and per-IP limits and daily token/money quotas, enforced **before** the call; queue background work with a concurrency cap. OWASP LLM10 (Unbounded Consumption) names Denial of Wallet: attackers running up your bill. Mitigations it lists include rate limiting, user quotas, timeouts and throttling.

**5. Spend caps in layers.** Provider-side: project budgets, spend alerts and hard limits where offered (OpenAI's hard limit makes requests fail with 429; it is a last resort, not your budget). App-side: cost per request computed from usage (`llm/observability-otel`), caps per run/user/tenant/day, alerts at 50/80/100%, and a kill switch flag per feature.

**6. Prompt caching (cheap, mostly automatic).**
- Put stable content first (tools, system prompt, examples, long documents), variable content last; caching is a **prefix match**, so a timestamp at the top breaks it.
- OpenAI: minimum 1,024 tokens for GPT-5.6 and later; writes cost 1.25× and reads 0.1× the input rate on most current models (0.05× on GPT-6.1 Sol); `prompt_cache_retention` `in_memory` or `24h` (default depends on Zero Data Retention); usage reports `cached_tokens`.
- Anthropic: automatic or explicit `cache_control` breakpoints; 5-minute default lifetime, 1-hour option; writes cost more than base input (1.25× for 5 minutes, 2× for 1 hour) and reads 0.1× on most models; minimum 512 tokens on current 5.x models (more on some older ones); a too-short prefix is silently not cached, so check `cache_creation_input_tokens` / `cache_read_input_tokens`.
- Watch the cache hit ratio after every prompt change.

**7. Response caching (your own).** Cache whole answers only for deterministic, non-personal requests (classification of a product title, translation of UI strings), keyed by prompt version + model + normalized input; never share cached answers across tenants. Semantic (embedding-similarity) caching risks returning a wrong answer for a similar-looking question: measure it with evals first.

**8. Cheaper paths.** Batch APIs (about 50% cheaper, results within 24 hours on OpenAI and Anthropic) for offline work; OpenAI Flex processing for slower, cheaper jobs; smaller models via routing (`llm/choosing-models`); shorter outputs (output tokens usually cost more than input); fewer agent steps. OpenAI's latency guide: generate fewer tokens, use fewer input tokens, make fewer requests, parallelize.

**9. Streaming for UX.** Stream to show progress, but validate structured output only when complete, and keep a server-side timeout on the whole stream. For channels that cannot stream (SMS, USSD, WhatsApp), keep answers short and send a quick acknowledgement first (`llm/multilingual-channels`).

## Examples
```python
client = OpenAI(timeout=30.0, max_retries=0)  # one retry layer: ours


@retry(
    on=(RateLimit, Overloaded, APIConnectionError),
    attempts=3,
    wait=retry_after_or_jitter(base=1, cap=20),
    give_up_if=lambda e: getattr(e, "code", "") in ("insufficient_quota",),
)
def answer(q, user):
    quota.check_and_reserve(user, est_tokens=1200)  # per-user daily cap, before the call
    return client.responses.create(model=MODEL, input=build(q), max_output_tokens=600)
```

## Anti-patterns
- SDK default 10-minute timeout on a user-facing route; no `max_tokens`.
- Retrying spend-limit 429s or validation errors; nested retries (yours × SDK's).
- No per-user quota on a public chatbot; spend alerts only at the provider.
- A timestamp or user name at the top of the system prompt (defeats prompt caching).

## Checks
- [ ] Every call has a timeout, an output-token cap and a single bounded retry policy honouring `Retry-After`.
- [ ] Per-user/tenant/day token and money quotas are enforced before calls; kill switch per feature.
- [ ] Fallback path defined and evaluated; circuit breaker on provider failures.
- [ ] Prompt layout is cache-friendly; cache hit ratio and cost per task are monitored.

## Sources
- OpenAI Python SDK (timeouts, retries): https://github.com/openai/openai-python
- OpenAI rate limits (Retry-After, error codes): https://developers.openai.com/api/docs/guides/rate-limits · spend limits: https://developers.openai.com/api/docs/guides/spend-limits
- Anthropic API errors (429, 504, 529, mid-stream errors): https://platform.claude.com/docs/en/api/errors
- OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Anthropic prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- OpenAI latency optimization: https://developers.openai.com/api/docs/guides/latency-optimization
- OWASP LLM10:2025 Unbounded Consumption: https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/
