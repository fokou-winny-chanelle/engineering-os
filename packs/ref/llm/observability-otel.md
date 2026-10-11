---
id: llm/observability-otel
title: Observability for LLM apps (OpenTelemetry GenAI semantic conventions, spans for model calls, tools and agents, token and cost tracking, content capture off by default, what to alert on)
area: llm
read_when: instrumenting model calls, tools, retrieval or agent runs, tracking tokens and cost per feature or tenant, choosing an LLM tracing tool, or deciding whether to log prompts and outputs
verified: 2026-10-10
revisit_days: 60
sources: ["https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/README.md", "https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/client-inference.md", "https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-token-metrics.md", "https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md", "https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/registry/attributes/gen-ai.md", "https://pypi.org/project/opentelemetry-instrumentation-openai-v2/", "https://github.com/Arize-ai/openinference", "https://github.com/traceloop/openllmetry"]
---
# Observability for LLM apps

Use OpenTelemetry (general setup: `ops/opentelemetry`) and the **GenAI semantic conventions** so traces stay portable between backends. The conventions now live in their own repository (open-telemetry/semantic-conventions-genai, Apache-2.0); their status is **Development**, and names changed during 2026, so pin instrumentation versions and re-check this ref when you upgrade.

## Decision guide

**1. One span per model call, tool call and agent run.**
- Model call (inference): name `{gen_ai.operation.name} {gen_ai.request.model}` (e.g. `chat gpt-6-luna`), kind CLIENT. Key attributes: `gen_ai.operation.name` (`chat`, `generate_content`, `embeddings`, …), `gen_ai.provider.name` (`openai`, `anthropic`, `gcp.gen_ai`), `gen_ai.request.model`, `gen_ai.response.model` (the exact snapshot served), `gen_ai.request.max_tokens`, `gen_ai.request.temperature`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `error.type`.
- Prompt identity: `gen_ai.prompt.name` and `gen_ai.prompt.version` (from your prompt file's `id` and `version`), so a quality or cost change maps to a prompt release.
- Agents and tools: `invoke_agent {gen_ai.agent.name}` and `execute_tool {gen_ai.tool.name}` spans, `gen_ai.conversation.id` to group a session; retrieval spans with `gen_ai.operation.name = retrieval`. MCP has its own conventions (trace context travels in `_meta` in MCP 2026-07-28).
- Add your own attributes for business context: feature, tenant id (not names), lane/route, eval run id.

**2. Content capture is opt-in, and should stay off in production by default.** Prompts, outputs, system instructions and tool definitions (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`) are Opt-In attributes because they hold personal and sensitive data. The OpenAI instrumentation captures content only when `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` is set. If you need content for debugging or evals: redact PII first, sample, restrict access, set short retention, and say so in your privacy notice (`llm/privacy-residency`). Never put API keys or full documents in attributes.

**3. Token and cost tracking.**
- Record the provider's reported usage (input, output, cached, reasoning tokens) from every response, including streaming (ask for usage in the final chunk where the API needs it) and failed or truncated calls.
- Compute cost in your code from a **dated price table you maintain** from each provider's pricing page; providers change prices and add multipliers (cache writes, long context, data residency, batch discounts). Do not hard-code prices you have not checked.
- Aggregate by feature, prompt version, model, tenant and user; show cost per successful task, not just per call. Feed budgets and alerts (`llm/reliability-cost`, `ops/capacity-cost`).
- Metrics: `gen_ai.client.operation.duration` / `gen_ai.client.inference.duration` and the token-usage metrics (current names: `gen_ai.client.inference.usage.input_tokens` and friends; older instrumentations emit earlier names). Check what your instrumentation version actually emits before building dashboards.

**4. Instrumentation options.**
| Option | Notes |
|---|---|
| Official OTel instrumentations (e.g. `opentelemetry-instrumentation-openai-v2`) | closest to the spec; beta versions; enable latest conventions with `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` |
| OpenLLMetry (Traceloop), OpenInference (Arize) | Apache-2.0 instrumentations for many providers and frameworks, OTel-based; attribute names may differ from the spec |
| Framework tracing (Agents SDK, LangGraph/LangSmith, Pydantic AI/Logfire, AI SDK telemetry) | convenient; check it exports OTLP so you are not locked into one backend |
| Manual spans | always possible; `eos scaffold llm-otel` writes a small wrapper with these attributes |

**5. What to alert on.** Error and timeout rate by provider; p95 latency and time to first token for streaming; truncation rate (`finish_reasons` = length / `max_tokens`); schema-validation failures; cache hit ratio dropping (cost jump); spend per hour above budget; agent runs hitting max steps; refusal spikes.

## Examples
```python
with tracer.start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT) as span:
    span.set_attributes(
        {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": model,
            "gen_ai.request.max_tokens": 800,
            "gen_ai.prompt.name": p.id,
            "gen_ai.prompt.version": str(p.version),
            "app.tenant_id": tenant,
        }
    )
    r = client.responses.create(model=model, input=msgs, max_output_tokens=800, timeout=30)
    span.set_attributes(
        {
            "gen_ai.response.model": r.model,
            "gen_ai.usage.input_tokens": r.usage.input_tokens,
            "gen_ai.usage.output_tokens": r.usage.output_tokens,
        }
    )
```

## Anti-patterns
- Logging full prompts and answers to a general log store by default; tenant names or emails as attributes.
- Cost estimated from character counts instead of reported usage; prices copied once and never dated.
- Dashboards built on metric names your instrumentation version does not emit.
- No link between a trace and the prompt version that produced it.

## Checks
- [ ] Every model, tool and agent step produces a span with model, provider, tokens, finish reason and prompt version.
- [ ] Content capture off in production unless redacted, sampled, access-controlled and disclosed.
- [ ] Cost per feature/tenant computed from usage and a dated price table; alerts on spend and truncation.
- [ ] Instrumentation versions pinned; dashboards verified against emitted names.

## Sources
- GenAI semantic conventions (overview, status): https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/README.md
- Client inference spans and metrics: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/client-inference.md · token metrics: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-token-metrics.md
- Agent and tool spans: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md · attribute registry: https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/registry/attributes/gen-ai.md
- OpenTelemetry OpenAI instrumentation (content capture variables): https://pypi.org/project/opentelemetry-instrumentation-openai-v2/
- OpenInference: https://github.com/Arize-ai/openinference · OpenLLMetry: https://github.com/traceloop/openllmetry
