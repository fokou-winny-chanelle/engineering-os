---
id: llm/tools-mcp
title: Tool and function calling design, and MCP servers for your product (tool surface, schemas, server-side checks, error messages, output size, MCP 2026-07-28, auth, transport hardening)
area: llm
read_when: giving a model tools (function calling), designing tool names, arguments and results, exposing your product to AI clients through an MCP server, or reviewing tool permissions
verified: 2026-10-10
revisit_days: 90
sources: ["https://developers.openai.com/api/docs/guides/function-calling", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview", "https://www.anthropic.com/engineering/writing-tools-for-agents", "https://www.anthropic.com/engineering/building-effective-agents", "https://modelcontextprotocol.io/specification/2026-07-28/changelog", "https://modelcontextprotocol.io/specification/2026-07-28/server/tools", "https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization", "https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http"]
---
# Tools and MCP servers

A tool is an API whose caller is a model that can be confused or manipulated. Design it like a public API for a careful but literal-minded intern, and enforce every rule on the server. Security rules (trifecta, least privilege, approvals): `security/llm-agent-security`.

## Decision guide

**1. Few, task-shaped tools.** OpenAI suggests fewer than 20 functions available at the start of a turn (a soft limit; load more with tool search). Anthropic's tool-writing guide recommends tools for high-impact workflows rather than thin API wrappers: `schedule_event` instead of `list_users` + `list_events` + `create_event`; `search_contacts` instead of `list_contacts`. Combine calls that always happen in sequence.

**2. Do not make the model fill what code knows** (OpenAI). If the order id, user id, tenant or currency is known from the session, pass it in code, not as an argument. The model should never choose whose data it reads.

**3. Schemas that prevent invalid states.**
- JSON Schema with enums, formats and required fields; strict mode (`strict: true`) on OpenAI and Anthropic so arguments match the schema.
- Avoid ambiguous pairs (`on: bool, off: bool`, OpenAI's example). Use units in names (`amount_xaf`, `timeout_s`).
- Write descriptions that pass the "intern test" (OpenAI): purpose, each parameter's format, what is returned, when not to use the tool.

**4. Enforce on the server, every call.** Validate arguments again; check the **user's** permission (not the agent's); cap amounts, counts and rates; make writes idempotent with a key. Money, deletion, sending messages and anything irreversible return a *proposal* the UI shows to the user with the exact parameters; the action runs only after the user confirms (MCP's tools spec: there SHOULD always be a human in the loop able to deny tool invocations).

**5. Results the model can use.**
- Return natural identifiers and meaningful fields, not opaque UUID dumps (Anthropic found resolving UUIDs to readable names reduced hallucination); offer a `response_format: concise | detailed` option where both are needed.
- Paginate, filter and truncate large results with sensible defaults (Claude Code caps tool results at 25,000 tokens by default) and say how to get more.
- Errors as actionable text ("`date` must be YYYY-MM-DD; got 12/10/2026"), not stack traces. Never echo secrets or other users' data.
- Treat tool results as untrusted input for the next model step: they may contain injected instructions.

**6. Evaluate tools, not just prompts.** Anthropic spent more time on tools than on the prompt for its SWE-bench agent (absolute file paths fixed a class of errors). Build realistic multi-step tasks, run them in a simple loop, and read the transcripts: wrong tool chosen, bad arguments, too many calls, and token use.

**7. MCP: when your product should be an MCP server.** Expose an MCP server when customers want to use your product from their own AI clients (Claude, ChatGPT, IDEs, agents). Inside your own app, call your functions directly; MCP adds a network hop and an auth surface you may not need.

**8. MCP specifics (spec 2026-07-28, check your SDK supports it).**
- This revision is stateless: no `initialize` handshake or session header; every request carries protocol version and capabilities in `_meta`; servers implement `server/discover`. Keep cross-call state in explicit handles passed as tool arguments.
- Remote servers use OAuth 2.1 with Protected Resource Metadata (RFC 9728); clients send a resource indicator (RFC 8707). Servers MUST accept only tokens issued for themselves and "MUST NOT accept or transit any other tokens" (no token passthrough to upstream APIs).
- Streamable HTTP: validate `Origin` on every connection (DNS rebinding), bind local servers to 127.0.0.1, authenticate all connections.
- Clients must treat tool annotations as untrusted unless the server is trusted; return tools from `tools/list` in a stable order (helps clients' prompt caches); use `outputSchema` with `structuredContent` for typed results.
- Tool descriptions are prompts read by other people's models: keep them factual, versioned and reviewed; changing them is a release.

## Examples
```python
@tool(strict=True)
def propose_refund(order_ref: str, amount_xaf: int, reason: Literal["damaged", "late", "other"]) -> Proposal:
    """Propose a refund for one of the CURRENT user's orders. Does not pay: the user must confirm.
    order_ref: the human-readable ref shown to the user, e.g. 'CMD-2026-0412'."""
    order = orders.get_for_user(session.user_id, order_ref)  # permission from the session
    if amount_xaf <= 0 or amount_xaf > order.paid_xaf:
        raise ToolError("amount_xaf must be 1..%d" % order.paid_xaf)
    return Proposal(action="refund", order_ref=order_ref, amount_xaf=amount_xaf, idempotency_key=new_key())
```

## Anti-patterns
- `run_sql`, `http_get(url)`, `send_email(to, body)` style generic tools for an agent that reads untrusted text.
- Tools that take `user_id` or `tenant_id` from the model; permission checks only in the prompt.
- Tool results of thousands of rows; raw exceptions; no idempotency on writes.
- A remote MCP server without auth, accepting any bearer token, or listening on 0.0.0.0 for local use.

## Checks
- [ ] Tool list per agent step is minimal and documented in a permission table.
- [ ] Every tool re-validates arguments and authorises against the session user; writes are idempotent.
- [ ] Irreversible actions go through a user confirmation that shows the real parameters.
- [ ] Tool use has its own eval tasks; MCP servers pass auth, `Origin` and token-audience tests.

## Sources
- OpenAI function calling (best practices, strict mode, tool search): https://developers.openai.com/api/docs/guides/function-calling
- Anthropic tool use: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- Anthropic, Writing effective tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, Building effective agents (agent-computer interface): https://www.anthropic.com/engineering/building-effective-agents
- MCP 2026-07-28 changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog · tools: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- MCP authorization: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization · Streamable HTTP: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
