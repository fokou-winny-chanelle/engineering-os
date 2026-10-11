---
id: llm/prompts-structured-output
title: Prompt and context engineering for products (system prompts, prompt files versioned in code, structured outputs with JSON Schema, few-shot examples, context budget and ordering)
area: llm
read_when: writing or changing a system prompt, asking a model for JSON, adding examples, deciding what goes into the context window, or setting up prompt files and their review
verified: 2026-10-10
revisit_days: 90
sources: ["https://developers.openai.com/api/docs/guides/prompt-engineering", "https://developers.openai.com/api/docs/guides/structured-outputs", "https://platform.claude.com/docs/en/build-with-claude/structured-outputs", "https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices", "https://ai.google.dev/gemini-api/docs/structured-output", "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents", "https://developers.openai.com/api/docs/guides/prompt-caching"]
---
# Prompts, context and structured output

A prompt is production code that changes behaviour without a compiler: version it, review it, test it with evals and roll it out like code. OpenAI's prompt guide now says to keep production prompts in your code (its saved "prompt objects" API, `v1/prompts`, is scheduled to shut down on 30 November 2026).

## Decision guide

**1. One prompt file per task, in the repo.** Keep it next to the feature, with the settings that shape its behaviour. eos convention (checked by `eos llm check`):
```markdown
---
id: invoice-extract
version: 4                 # bump on every change to the text or settings
model: gpt-6-luna          # pinned id; config may override per environment
owner: billing
evals: evals/invoice-extract.jsonl
max_output_tokens: 800
inputs: [invoice_text, locale]
untrusted: [invoice_text]  # must sit inside a tag such as <invoice>…</invoice>
---
You extract invoice fields for Cameroonian SMEs. …
<invoice>
{{invoice_text}}
</invoice>
```
Name files `*.prompt.md` or put them under `prompts/`. The PR shows the diff and before/after eval scores.

**2. Write the system prompt at the right altitude** (Anthropic's phrase): clear and direct, specific enough to guide, not a pile of brittle if-then rules. A useful order (OpenAI): identity and goal → instructions and constraints → examples → context. Say what to do when information is missing ("answer `unknown`", "ask one question"), which language to reply in, and what the model must never do. Never put secrets, keys or internal URLs in it: assume the prompt leaks (OWASP LLM07).

**3. Separate instructions from data.** Wrap documents, user text and tool output in tags (`<document id="7">…</document>`) so the model can tell them apart, and say in the instructions that text inside them is data. This helps quality; it does not stop prompt injection (`security/llm-agent-security`).

**4. Structured output: use the provider's schema mode, then validate anyway.**
- OpenAI Structured Outputs (`strict: true` with a JSON Schema) guarantees schema adherence; JSON mode only guarantees valid JSON. Anthropic structured outputs (`output_config.format` with `type: json_schema`, and `strict: true` on tools) use constrained decoding. Gemini accepts a response schema. Each supports a subset of JSON Schema: check the limits page.
- Generate the schema from your types (Pydantic, Zod) and parse into them with the SDK helper.
- Still handle: refusals (OpenAI returns them as a separate field), responses cut off at the token limit (`status: incomplete`, reason `max_output_tokens`), and values that are well-formed but wrong (a total that does not add up). Validate business rules in code.
- Design schemas for the model: enums instead of free strings, `null`/`unknown` allowed where the source may lack the value, a short `reason` field before the answer when reasoning helps, no deep nesting.

**5. Few-shot examples.** Anthropic recommends 3–5 relevant, diverse examples wrapped in `<example>` tags; Anthropic's context-engineering post warns against stuffing a list of every edge case instead of a few canonical examples. OpenAI notes examples can hurt reasoning models: test both ways on your evals. Use realistic FR/EN inputs, including Cameroonian names, XAF amounts and phone formats.

**6. Context is a budget.** Anthropic calls it an "attention budget": as context grows, recall degrades ("context rot"). Send the smallest set of high-signal tokens: retrieved passages rather than whole manuals, a summary rather than full chat history, only the tools this step needs. Order for both quality and prompt caching (`llm/reliability-cost`): stable parts first (system prompt, tool definitions, fixed reference text), then per-request documents, then the question last (Anthropic: queries at the end improve quality on long inputs).

**7. Parameters belong to the prompt.** Model id, reasoning effort, temperature (where the model supports it), `max_output_tokens`, tool choice and schema are part of the prompt's version; changing any of them is a prompt change.

## Examples
```python
class Invoice(BaseModel):
    supplier: str
    niu: str | None  # taxpayer number if printed, else null
    total_xaf: int  # whole francs, no decimals
    currency: Literal["XAF", "EUR", "unknown"]


resp = client.responses.parse(
    model=cfg.model,
    instructions=prompt.system,
    input=prompt.render(invoice_text=text),
    text_format=Invoice,
    max_output_tokens=800,
)
inv = resp.output_parsed  # then: check lines sum to total_xaf in code
```

## Anti-patterns
- Prompts as string literals spread across handlers; prompt edits merged without an eval run.
- Parsing JSON out of free text with regex when a schema mode exists; trusting schema-valid output as correct.
- Secrets or business rules that must hold (prices, limits, permissions) enforced only by the prompt.
- Ever-growing prompts patched with one rule per bug; whole chat history and every tool in every call.

## Checks
- [ ] Each prompt is a versioned file with model, owner, evals and output limit; `eos llm check` passes.
- [ ] Untrusted inputs are delimited and listed; no secrets in prompts.
- [ ] Structured output uses schema mode plus code validation, and handles refusal and truncation.
- [ ] Prompt PRs show eval scores before and after.

## Sources
- OpenAI prompt engineering (version prompts in code, message roles, Markdown/XML): https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- Anthropic structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic prompting best practices (examples, XML tags, long context): https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Anthropic, Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
