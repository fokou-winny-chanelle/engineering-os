---
id: agent-security
title: AI agent and LLM security (product features and our own coding agents)
kind: phase
mode: both
when: building LLM/agent features, RAG, tool calling, or editing MCP/agent configs and prompts
description: Use for LLM, RAG or agent features and MCP/agent configs: prompt injection, tool permissions, exfiltration, sandboxing.
globs: ["**/mcp.json", "**/.mcp.json", "**/mcp*.json", "**/prompts/**", "**/*.prompt.md", "**/*llm*", "**/*agent*"]
next: [security, testing-qa]
---
# AI agent and LLM security

## Entry
Any feature where a model reads untrusted text or calls tools, and any change to MCP servers, agent hooks or permissions in this repo. Maps to the OWASP Top 10 for LLM Applications and for Agentic Applications (ASI01–ASI10).

## Standards
1. **Outside input is untrusted.** Web pages, emails, files, issues, tool/MCP outputs, RAG documents and memory can carry instructions (prompt injection, ASI01). Models can't reliably tell data from instructions, so security must never depend on the prompt.
2. **Break the lethal trifecta.** No single agent run may have all three of:
   - private data;
   - untrusted content;
   - a way to send data out (HTTP, email, links, images, PR comments).

   Remove one leg in code: an egress allow-list, no tools after reading untrusted content, or a quarantined model with no tools.
3. **Least privilege for tools (ASI02/ASI03).**
   - Smallest tool set; read-only tokens by default, scoped to one repo or tenant.
   - No human or production credentials in agent environments.
   - Destructive actions (delete, pay, send, deploy, merge) need code checks plus human approval.
4. **Validate model output like user input.**
   - Schema-validate tool arguments.
   - Never pass model text to a shell, `eval`, SQL or HTML without the usual parameterisation and encoding (ASI05).
   - Render markdown safely, with no auto-loading remote images (an exfiltration channel).
5. **Sandbox execution.** Agent-run code goes in an isolated container or VM: no secrets, limited network, CPU/time limits, throwaway disk, no production data.
6. **MCP supply chain (ASI04).**
   - Trusted sources only, pinned by version.
   - Tool descriptions reach the model and can hide instructions ("tool poisoning"). Review them, and re-review on change ("rug pull").
   - Secrets go in env files outside git, never in the MCP JSON. Fewer servers = less attack surface.
7. **Memory/RAG poisoning (ASI06).** Record the source of stored memory and documents; users can see and delete memory; filter by tenant inside the vector query.
8. **Multi-agent (ASI07/08).** Authenticate agent-to-agent calls, schema-validate messages, cap steps, cost and recursion.
9. **Approvals (ASI09)** show the exact action and its parameters, not the model's summary.
10. **Observe and limit.** Trace model and tool calls (content off or redacted), cap rate, tokens and cost per user, set timeouts and max steps.
11. **Evaluate, adversarially too.** Prompts are versioned files; an eval gate (thresholds per language and a 100% safety slice) runs on every prompt, model or retrieval change; red-team before launch.

## Deliverables
- Data-flow diagram with the trifecta legs and the one removed, tool/permission table, eval and injection sets, threat-model entries.

## Automated checks
- `eos llm check` (prompt files: frontmatter, version bump, untrusted inputs delimited) and `eos llm gate` (eval thresholds and baseline) via `eos scaffold llm-evals`, with Semgrep rules for model output reaching exec/SQL/HTML, keys in client code and missing limits. Injection suite in CI. `eos guard` hooks stay enabled.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `security/llm-agent-security` · `testing/llm-evals` · `llm/choosing-models` · `llm/prompts-structured-output` · `llm/tools-mcp` · `llm/agents-workflows` · `llm/rag` · `llm/evals-in-production` · `llm/reliability-cost` · `llm/privacy-residency` · `llm/multilingual-channels` · `llm/frameworks`.

## Exit checklist (Definition of Done)
- [ ] No run combines private data, untrusted input and egress. Enforced in code, not in the prompt.
- [ ] Tool permissions are minimal. Destructive actions need human approval showing the real parameters.
- [ ] MCP servers are pinned and their descriptions reviewed. No secrets in agent configs.
- [ ] Injection tests pass. Logs and cost limits are in place.

## Handoff → security / testing-qa
Pass the trifecta analysis, permission table, eval results and accepted risks.

## Stop & escalate
Stop if asked to give an agent production credentials or payment or deletion powers without approval, to disable guard hooks, or to send user data to a new model provider. These need a human decision and a privacy check.
