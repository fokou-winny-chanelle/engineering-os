---
id: llm/agents-workflows
title: Agents in products (workflow or agent, orchestration patterns, state and memory, human-in-the-loop, guardrails, stop conditions and budgets, context management)
area: llm
read_when: designing a multi-step LLM feature, deciding between a fixed workflow and an autonomous agent, adding memory, approvals, guardrails or turn limits, or debugging an agent that loops, stalls or overspends
verified: 2026-10-10
revisit_days: 90
sources: ["https://www.anthropic.com/engineering/building-effective-agents", "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents", "https://openai.github.io/openai-agents-python/running_agents/", "https://openai.github.io/openai-agents-python/guardrails/", "https://openai.github.io/openai-agents-python/human_in_the_loop/", "https://docs.langchain.com/oss/python/langgraph/interrupts", "https://modelcontextprotocol.io/specification/2026-07-28/server/tools"]
---
# Agents in products

Anthropic's definitions: **workflows** orchestrate LLMs and tools through predefined code paths; **agents** let the model direct its own process and tool use. Workflows are predictable and cheap to test; agents are flexible and harder to bound. Start with the simplest thing that works and add autonomy only where it measurably helps.

## Decision guide

**1. Choose the lightest pattern that meets the eval** (all from Building effective agents):
| Pattern | Use when | Example |
|---|---|---|
| Single call + retrieval/tools | one well-defined step | classify a support ticket |
| Prompt chaining (with code gates between steps) | fixed subtasks in order | draft → check rules in code → translate |
| Routing | inputs fall into distinct classes | billing vs technical vs sales, or easy→small model |
| Parallelization (sectioning / voting) | independent parts, or several opinions | guardrail model screens while main model answers |
| Orchestrator–workers | subtasks are not known in advance | multi-file changes, research |
| Evaluator–optimizer | clear criteria and iteration helps | translation polish with a rubric |
| Agent loop | open-ended, many steps, recoverable errors, sandboxed | coding or ops assistant |

**2. Keep state in your system, not the transcript.** Store the run (step, inputs, tool results, approvals) in your database or a durable runtime so a crash, deploy or approval wait can resume. LangGraph (durable execution, interrupts) and the OpenAI Agents SDK (`RunState` serialize/resume) provide this; a job table with a state column also works.

**3. Memory, deliberately.**
- *Short-term*: the conversation/thread, trimmed or compacted (summarize old turns, drop stale tool output; Anthropic calls tool-result clearing the safest light-touch compaction).
- *Long-term*: explicit facts with source, owner, timestamp and user visibility ("Remember that I prefer French"). Let users view and delete memories; scope by user and tenant; never store secrets or special-category data without a legal basis (`llm/privacy-residency`).
- Memory written from untrusted content can carry injected instructions into future sessions; treat it as untrusted on read.

**4. Context management for long tasks** (Anthropic context engineering): context is a finite "attention budget"; prefer just-in-time retrieval via tools over preloading; keep structured notes outside the window (to-do file, progress log); give sub-agents clean contexts and take back short summaries.

**5. Human-in-the-loop where the cost of a mistake is high.** Approval before irreversible, external or money-moving actions, showing the exact parameters; review queues for low-confidence outputs; easy handover to a person on every customer channel. MCP's tools spec says there SHOULD always be a human able to deny tool invocations. Approval fatigue is real: approve plans or batches, and make low-risk actions not need approval.

**6. Guardrails in layers.** Input checks (topic, abuse, PII) and output checks (schema, policy, citations, leakage) run as code or small models around the main call; the OpenAI Agents SDK has input, output and tool guardrails with tripwires. Guardrails reduce risk but do not stop prompt injection: the real control is limited capability (`security/llm-agent-security`: lethal trifecta, Rule of Two).

**7. Stop conditions and budgets — every loop has all of these:**
- max turns/iterations (the Agents SDK raises `MaxTurnsExceeded`; Anthropic recommends stopping conditions such as a maximum number of iterations);
- max tokens and money per run, per user and per day, checked before each call;
- wall-clock timeout per run and per tool call;
- loop detection (same tool + same arguments repeated) and a "no progress" check;
- a defined final state: done, needs human, or failed with reason, shown to the user.

**8. Multi-agent only with a reason.** Handoffs and sub-agents help with separate permission sets or very large contexts; they multiply cost and failure modes. One agent with good tools usually wins first.

## Examples
```python
for step in range(MAX_STEPS):  # 8
    if budget.spent_xaf(run) >= budget.cap_xaf(run):
        return finish(run, "needs_human", "budget")
    reply = llm.call(run.context(), tools=allowed_tools(run.stage), timeout=30)
    if reply.final:
        return finish(run, "done", reply.text)
    for call in reply.tool_calls:
        if repeated(run, call, times=3):
            return finish(run, "needs_human", "loop")
        if call.tool in NEEDS_APPROVAL:
            return pause_for_approval(run, call)  # resumable
        run.add(execute(call, user=run.user, timeout=15))
return finish(run, "needs_human", "max_steps")
```

## Anti-patterns
- An autonomous agent for a task a three-step workflow handles; frameworks adopted before the plain loop is understood.
- `while True` loops, no money cap, no timeout; agent state only in memory.
- One agent with every tool and a user's full permissions reading untrusted email or web pages.
- Long-term memory the user cannot see or delete; approvals that hide what will actually run.

## Checks
- [ ] Pattern choice written down with the eval that justified it.
- [ ] Every loop has max steps, token/money caps, timeouts, loop detection and defined end states.
- [ ] Runs are persisted and resumable; approvals show exact parameters and are logged.
- [ ] Memory is scoped, visible and deletable; tool permissions per stage are minimal.

## Sources
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- OpenAI Agents SDK, running agents (max_turns): https://openai.github.io/openai-agents-python/running_agents/ · guardrails: https://openai.github.io/openai-agents-python/guardrails/ · human-in-the-loop: https://openai.github.io/openai-agents-python/human_in_the_loop/
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- MCP tools (human in the loop): https://modelcontextprotocol.io/specification/2026-07-28/server/tools
