# The AI-Assisted Engineering Blueprint

**A stack-agnostic engineering operating system for building software with AI agents, from first idea to production operations.**

*Written for senior engineers and tech leads, as a reusable template for any project, language or team.*
*Version 2 (stack-agnostic). The companion starter repo is `engineering-os` v0.7.0 (`engineering-os.zip`); section 26 is the v0.3.0 senior review, section 27 the v0.4.0 research-driven upgrade, section 28 the v0.5.0 upgrade (any project state, self-guiding, any repo shape), section 29 the v0.6.0 velocity audit and section 30 the v0.7.0 deep knowledge library. Worked stack packs: Python (FastAPI, Flask), TypeScript/Next.js, React Native/Expo and Flutter.*
*Research dates: 9 October 2026 (sections 0–26), 10 October 2026 (sections 27–29 and `RESEARCH.md`) and 10–11 October 2026 (section 30). Versions and features were checked against official docs and package registries on that date (see [Sources](#25-sources)). These tools change monthly, so re-check before you pin anything.*

---

## How to read this document

- **Section 0** is the one-page summary. Read it first.
- **Sections 1–4** describe the *operating system*: principles, layers, the 18 phase packs, and how context loads just in time (with the token budget and the anti-loop safeguards).
- **Sections 5–10** cover the *AI mechanics*: memory, self-checking and retros, tool adapters (Cursor, Cline, Claude Code, Codex), the BMAD lifecycle, cost, and MCP.
- **Section 11** covers *reproducibility*: the `engineering-os` repo, one-command bootstrap, project init, and updates and versioning.
- **Sections 12–16** cover the *engineering side*: how stack packs work, two worked stack packs (Python, TypeScript/Next.js), monorepo and CI/CD, and production readiness.
- **Sections 17–25** are the rollout plan, repository trees, key files, honest caveats, maintenance, the open decisions, glossary, Definition of Done and sources.
- **Section 26** is the v0.3.0 senior review: what was weak or missing, what was fixed, and what was deferred and why.
- **Section 27** is the v0.4.0 research-driven upgrade: independent research beyond the original brief (full cited report: `RESEARCH.md` / `RESEARCH.pdf`), what changed, token numbers and what was deferred.
- **Section 28** is the v0.5.0 upgrade: existing and rewrite projects (`eos adopt`, ratchet gates), the `eos next` navigator, and repo shapes from modular monolith to multi-repo workspace.
- **Section 29** is the v0.6.0 velocity audit: where the system slowed work down, risk lanes, escape hatches, what was cut, and measured before/after numbers. **Where it conflicts with earlier sections, section 29 wins.**
- **Section 30** is the v0.7.0 deep knowledge library: 134 expert references across 12 areas that agents read only when doing that work, the checks that enforce them, and the one checklist of what a human still has to review. It adds to section 29 and does not change the lanes.

Short definitions appear the first time a term is used. There is a glossary in [Section 23](#23-glossary).

> **Labels used in this document**
> - **[Verified]**: confirmed in official docs or registries on the research date, with a link.
> - **[Tested]**: run in the `engineering-os` test suite or in a scratch environment on the research date.
> - **[Recommendation]**: my engineering judgement. The reasoning is given, and you may disagree.
> - **[Heuristic]**: a rule of thumb, such as a size budget. It is not a published standard, so tune it.

---
## 0. Executive summary

### The core idea in one paragraph

AI agents are fast, tireless junior-to-mid engineers. They have no long-term memory, and they tend to "make the test pass" by any means. Strong AI-native teams don't get good results from a magic prompt. They build a **system around the agent**:
- written intent (specs and acceptance criteria) that the agent works from;
- small tasks that fit in one session;
- project memory stored as files in Git;
- **deterministic checks the agent cannot switch off**;
- a second agent, and then a human, reviewing the work;
- production safety nets (feature flags, canaries, SLOs).

DORA's 2025 research says the same thing with data: AI increases throughput, but it is associated with more instability unless teams have strong version control, small batches, good internal platforms and a clear AI policy ([DORA AI Capabilities Model](https://dora.dev/research/2025/dora-report), [RedMonk summary](https://redmonk.com/rstephens/2025/12/18/dora2025/)).

**Version 2 makes this system stack-agnostic.** The standards for *how a senior engineer works* (requirements, architecture, API and data design, testing, security, review, release, operations, documentation, maintenance) are the same in Python, TypeScript, Go, PHP or Kotlin. Only the commands and idioms change. So the system is split in two:
- **Phase packs** (18 of them, language-free) describe *what good looks like* at each phase. Each one has entry criteria, standards, deliverables, automated checks, an exit checklist and a handoff.
- **Stack packs** (Python, FastAPI, Flask, TypeScript, Next.js, plus a template) supply the *commands and idioms*. They are detected automatically from marker files such as `pyproject.toml` or `next.config.ts`.

Everything ships as a git repo, `engineering-os`. One command installs it on a machine (`./bootstrap.sh`), and one command adds it to a project (`eos init`). It generates thin adapters for Cursor, Cline, Claude Code and Codex from one canonical source, `AGENTS.md` plus the packs, so every tool sees the same rules.

### Top 10 recommendations

1. **Adopt the two-axis model: phases × stacks.** Write standards once per *phase*, and keep language specifics in *stack packs*. A new language costs one `eos new-stack` and roughly a 1,000-token pack, not a new process. ([Section 3](#3-phase-packs-the-senior-engineering-lifecycle), [Section 12](#12-stack-packs-how-they-work))
2. **Keep the always-on context tiny, and load everything else just in time.** Root `AGENTS.md` holds about 1k tokens: core rules, the commands table and a two-line pointer to the pack index. Packs attach by file glob or by intent (skills). Session start is **about 1.7k tokens in every tool**, and about 4.6k while editing a FastAPI route (v0.1.0: 2.7–3.1k and ~7.4k) [Tested; Section 4.2]. Budgets are enforced by `eos check` in pre-commit and CI. ([Section 4](#4-context-loading-token-budget-and-anti-loop-safeguards))
3. **One source of truth, many thin adapters.** `AGENTS.md` (read by Cursor, Cline and Codex, and by Claude Code through an `@AGENTS.md` import) plus `.eos/packs/` are canonical. Cursor `.mdc` rules, `.clinerules`, `.claude/rules` and the skills folders are *generated*, and drift fails the build. ([Section 7](#7-tool-adapters-cursor-cline-claude-code-codex))
4. **"Done" is a green deterministic check, not the model's opinion.** Each stack declares a `fast_check` and a `full_check`. The stop hook runs pre-commit on the changed files when the agent claims it is finished, and sends failures back. CI runs it all again. ([Section 6](#6-self-checking-reviewer-agents-and-retros))
5. **Anti-loop safeguards in three layers:**
   - rules: stop after 3 failed fixes, when the diff grows well past the plan, or when a long session gets confused;
   - a loop-guard hook: the same command on the same code state more than 3 times → ask;
   - a capped stop hook: after 3 attempts it forces a handoff to a human.

   ([Section 4.4](#44-anti-loop-safeguards))
6. **Protect the oracle.** Agents can't edit CI, hooks, lockfiles, merged migrations, accepted ADRs or `.eos/` (guard hooks). `eos test-integrity` flags weakened tests and requires a human label in CI. Mutation testing on critical modules shows that the tests can fail. ([Section 6.6](#66-guardrails-against-agents-cheating-tests))
7. **Memory in three scopes, each with a size limit and an owner:**
   - personal profile (≤400 tokens, global);
   - project memory (ADRs, `memory/active-context.md` ≤40 lines, `progress.md`, lessons);
   - session handoff (≤30 lines).

   Retros turn repeated mistakes into the cheapest fix that lasts: *a check, then a pack line, then a lesson*. ([Section 5](#5-the-agent-memory-system))
8. **Secrets never touch git.** MCP configs are rendered per tool from one canonical `mcp/servers.json` that contains only variable *names*. Real values live in `~/.config/engineering-os/secrets.env` (chmod 600), or in Cline's private settings file when Cline needs literal values. gitleaks runs in pre-commit, in a global git hook and in CI. ([Section 10.4](#104-secrets-out-of-git-one-canonical-mcp-list-rendered-per-tool))
9. **Use BMAD v6.12.1 as the lifecycle engine, and let eos supply the standards.** BMAD personas (analyst, PM, architect, UX, dev) get eos phase packs injected through `_bmad/custom/*.toml` `persistent_facts`. That injection was verified with BMAD's own resolver [Tested]. ([Section 8](#8-the-lifecycle-bmad-as-the-workflow-engine))
10. **Roll out in 6 phases over about 8 weeks, shipping product code from week 1.** The "extreme" setup is the end state, not the entry fee. ([Section 17](#17-phased-rollout-plan))

### Open decisions you must make (details in [Section 22](#22-open-decisions))
The big ones:
- the type checker and the JS linter per stack;
- whether to enable global git hooks;
- how strict the guard's "ask" list is;
- whether Cline may hold MCP secrets on disk;
- the primary PR review bot;
- the premium model for planning and review;
- your hosting target;
- the BMAD upgrade timing (v6 stable vs the Skills-CLI layout on `main`).

---
## 1. Principles behind the system

These are the ideas everything else follows from. When a tool changes, keep the principle and swap the tool.

| # | Principle | What it means in practice |
|---|-----------|---------------------------|
| P1 | **Specs before code** | No agent writes production code without a written intent: a spec, story or ticket with acceptance criteria. |
| P2 | **Small batches** | One story ≈ one session ≈ one PR. DORA lists small-batch work as one of seven capabilities that amplify AI's benefits. |
| P3 | **Memory lives in Git** | Anything the agent must remember is a file, reviewed in PRs, versioned with the code. Not in chat history, not only in a vendor's cloud memory. |
| P4 | **Context is a budget** | Every token in the prompt costs money and attention. Load the minimum, scoped to the files being touched. |
| P5 | **Machines check machines** | Deterministic tools (types, linters, tests, scanners) are the first reviewer. AI reviewers come second. Humans come last but decide. |
| P6 | **The oracle is protected** | The agent can never edit the thing that judges it (tests it did not write, CI, thresholds) without a human seeing it. |
| P7 | **Least privilege everywhere** | Agents, MCP servers and CI tokens get only the permissions the current role needs. |
| P8 | **Production is the real test** | Feature flags, canaries, SLOs and runbooks limit the blast radius of mistakes you did not catch. |
| P9 | **Right-size the ceremony** | A typo fix does not need a PRD. A payment ledger does. BMAD itself is designed around this ("Small changes go straight to build"). |
| P10 | **Standards are stack-agnostic; commands are not** | Phase packs say *what* good looks like in any language; stack packs supply the commands. A new language is a new pack, not a new process. |
| P11 | **Checks over prose** | Every rule that can become a lint, test, type or hook should become one; then delete the prose. Context tokens are for judgement, not policing. |
| P12 | **Reproducible by default** | One repo, one bootstrap command, one init command, versioned standards; any machine or teammate gets the same system. |

---

## 2. The Engineering OS: architecture and layers

### 2.1 Two axes: phases × stacks

```
                    ┌──────────── Phase packs (language-free: WHAT good looks like) ────────────┐
                    ideation → discovery → requirements → ux-design → architecture → data-modeling
                    → api-design → backend / frontend / mobile → infra-devops → testing-qa → security
                    → code-review → release → operations → documentation → maintenance
                                                 ×
   Stack packs (HOW, in this language):  python ─ python-fastapi ─ python-flask ─ typescript ─ nextjs ─ <yours>
   each declares: markers · globs · fast_check · full_check · pre-commit fragment · CI job
```

A phase pack never names a language-specific command. It says "the stack's boundary lint" or "the stack's dependency audit". The stack pack fills in `uv run lint-imports` or `pnpm audit`. This keeps each file small, and it means an upgrade to the security standard reaches every language at once.

### 2.2 The layers

| Layer | Content | Source of truth | Loaded | Budget [Heuristic, enforced] |
|---|---|---|---|---|
| **L0 Personal** | Your preferences across all projects: language, answer style, engineering defaults, "never" list | `engineering-os/personal/PROFILE.md` → rendered into each tool's global instructions by `bootstrap` | Always | ≤400 tokens |
| **L1 Core** | 7 working rules, stop conditions, the loading rules, memory rules, the stack commands table, a pointer to the pack index | `core/AGENTS.core.md` → the eos blocks in the project `AGENTS.md` | Always | ≤1,000 (whole `AGENTS.md` ≤1,600) |
| **L2 Stack** | Toolchain, commands, idioms and pitfalls for one ecosystem | `.eos/packs/stacks/<id>.md` | When a matching file is touched (globs) | ≤1,200 each |
| **L3 Phase** | Entry, standards, deliverables, automated checks, exit checklist, handoff, stop and escalate | `.eos/packs/phases/<id>.md` | By file glob and/or by intent (skill) | ≤1,200 each |
| **L4 Project memory** | ADRs, active context, progress, lessons, the team's "Project specifics" | `docs/adr/`, `memory/`, `docs/ai/lessons.md`, `AGENTS.md` | Active context at session start; the rest on demand | active-context ≤40 lines |
| **L5 Session** | Plan, chat, handoff | `memory/handoff.md`, plan files | This session | handoff ≤30 lines |
| **L6 Enforcement** | Pre-commit, CI, agent hooks, `eos check`, `eos test-integrity`, branch protection | `.pre-commit-config.yaml`, `.github/workflows/`, `.cursor/hooks.json`, … | Always; costs **zero tokens** | n/a |

**Rule of thumb [Recommendation]:** push knowledge *down* this table over time. Prose in L1–L3 costs tokens on every relevant request, and the model can ignore it. A check in L6 costs nothing at runtime and cannot be ignored. Every rule has a natural lifecycle: *incident or lesson → pack line → automated check → delete the prose.*

### 2.3 Where things live

| | `engineering-os` repo (yours, one per person or team) | Each project after `eos init` |
|---|---|---|
| Canonical content | `core/`, `packs/`, `personal/`, `mcp/`, `integrations/bmad/` | `AGENTS.md` and `.eos/packs/` (a copy, editable per project) |
| Code | `bin/eos.py` (one stdlib-only Python file) | `.eos/bin/eos.py` (vendored, so hooks and CI need nothing installed) |
| Tool adapters | n/a | generated: `.cursor/rules/eos-*.mdc`, `.clinerules/eos-*.md`, `.claude/rules/eos-*.md`, skills in `.agents/`, `.cline/` and `.claude/` |
| State | `VERSION`, `versions.toml`, `CHANGELOG.md` | `.eos/manifest.json` (eos version, choices, file hashes) |

**Why vendor a copy into each project?** Three reasons. Teammates and CI need no global install. The project pins the exact standards it was built under. And a project can tune a pack locally; `eos update` never silently overwrites those edits (see [Section 11.4](#114-updates-and-versioning)).

---
## 3. Phase packs: the senior engineering lifecycle

### 3.1 Anatomy of a phase pack

Every pack is a Markdown file with short frontmatter and the same seven sections. `eos check` validates both. [Tested]

```markdown
---
id: api-design
title: API design (contract-first)
kind: phase
mode: both            # files = attach by glob · intent = skill only · both
when: designing or changing HTTP/gRPC/GraphQL/event contracts      # one line, shown in .eos/packs/INDEX.md
description: Use when designing or changing an API contract ... (≤160 chars for intent/both packs; listed to the model every request as the skill description)
globs: ["**/openapi*.yaml", "**/*.proto", "**/*.graphql", "**/asyncapi*.yaml"]   # no commas/braces (Cursor limitation)
next: [backend, frontend, testing-qa]
---
## Entry            what must be true before starting (inputs, approvals)
## Standards        the senior-level rules, short and testable
## Deliverables     files that must exist at the end, with paths
## Automated checks what CI/pre-commit verifies (by tool type; stack packs give commands)
## Exit checklist   the Definition of Done for this phase, as checkboxes
## Handoff          what the next phase receives, and where it is written
## Stop & escalate  when the agent must stop and ask a human
```

The **Stop & escalate** section is what makes a pack safe for agents. It names the situations where guessing is expensive. Examples: "a breaking change is needed", "money rounding rule unclear", "a migration would lock a large table".

### 3.2 Phase catalogue

| Phase | Mode | Key deliverables | Automated checks (examples) | Next |
|---|---|---|---|---|
| **ideation** | intent | `docs/ideas/<slug>.md`: problem, options table, riskiest assumption, kill criteria | none by design | discovery |
| **discovery** | intent | `docs/discovery/brief.md`: personas, jobs-to-be-done, metrics, non-goals; spike reports | Markdown lint, link check | requirements |
| **requirements** | both | PRD/spec, epics and stories with **EARS** acceptance criteria (ACs), NFR table | AC-ID traceability to test names (optional script) | ux-design, architecture |
| **ux-design** | both | flows and a state matrix (empty/loading/error), Figma links, token and component list | Storybook per state, axe, no raw colours outside tokens | architecture, frontend |
| **architecture** | both | `docs/architecture/overview.md` (context, containers, quality attributes, failure modes), ADRs | boundary lint (stack), ADR index check | data-modeling, api-design, infra, security |
| **data-modeling** | both | schema change + migration, data classification, ADR for structural changes | migration lint (e.g. squawk), migrate from empty, models-vs-migrations drift | api-design, backend |
| **api-design** | both | contract file (OpenAPI/proto/GraphQL/AsyncAPI) + changelog + consumer note, generated clients | spec lint, breaking-change diff (oasdiff, `buf breaking`), contract tests, generated-code freshness | backend, frontend, testing-qa |
| **backend** | files | code + unit/integration tests, logs/metrics, PR summary with AC IDs | stack full check | testing-qa, code-review |
| **frontend** | files | components + stories + component tests + e2e for the main AC path; screenshots | stack full check, a11y | testing-qa, code-review |
| **mobile** (brief) | files | feature + unit/UI tests, release notes | platform lint and types, UI tests on an emulator, both-platform build | testing-qa, release |
| **infra-devops** | files | IaC/CI change, plan output in the PR, env docs | fmt/validate/tflint, checkov/trivy config, actionlint, hadolint, image scan | security, release, operations |
| **testing-qa** | files | tests per layer (unit, integration, **contract**, e2e, **performance**, **mutation**) | stack tests, diff coverage, `eos test-integrity`, nightly perf and mutation | code-review, security |
| **security** | both | threat model (STRIDE-lite), security test cases (IDOR, injection, replay), audit report | secrets scan, SAST (Semgrep/CodeQL), dependency audit, container/IaC scans, DAST baseline | code-review, release |
| **code-review** | intent | findings (severity, location, evidence, fix), verdict, follow-up tickets | required CI green, review bot ran, CODEOWNERS approval | release |
| **release** | both | tag, changelog, notes, rollout plan with guardrails, rollback steps, migration order | release CI, SBOM, attestation, smoke tests per step | operations |
| **operations** | both | SLO doc, alerts and dashboards as code, runbooks, postmortems | alert-rule lint, runbook-link check, synthetic checks | maintenance, documentation |
| **documentation** | files | README/how-to/reference/ADR updates (Diátaxis), changelog | Markdown lint, link check, generated-docs freshness, `eos check` budgets | n/a |
| **maintenance** | intent | small behaviour-preserving PRs, debt register, upgrade notes | full checks, `eos test-integrity`, scheduled audit, dead-code tools | code-review |

*Mode* controls loading (see [Section 4](#4-context-loading-token-budget-and-anti-loop-safeguards)). **Files** packs attach automatically when matching files are edited. **Intent** packs are skills that load when the task matches their description. **Both** do both. The full text of each pack is in `engineering-os/packs/phases/`. Each pack is 600–1,100 tokens [Tested].

### 3.3 Right-sizing the ceremony

Not every change walks all 18 phases. [Recommendation, consistent with BMAD's "planning path sized by intent"]:

| Change size | Phases you actually touch |
|---|---|
| Typo, copy change, small bug | backend/frontend → testing-qa → code-review (the stop hook and CI do the rest) |
| Feature inside an existing design | requirements (story + EARS ACs) → api-design/data-modeling if contracts change → backend/frontend → testing-qa → security if trust boundaries change → code-review → release |
| New product or service, or anything moving money | All phases, with human approval at requirements, architecture, security and release |

---
## 4. Context loading, token budget and anti-loop safeguards

### 4.1 Just-in-time loading: four mechanisms

**Context engineering** means deciding exactly what the model sees at each step. Anthropic's guidance on agents is to find "the smallest possible set of high-signal tokens", and to let agents pull extra context in progressively rather than pre-loading it ([Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)). eos implements this four ways:

| Mechanism | Trigger | Implementation per tool [Verified in each tool's docs; generated by `eos sync`, Tested] |
|---|---|---|
| **Always-on core** | every request | `AGENTS.md` (Cursor, Cline and Codex read it natively; Claude Code via `CLAUDE.md` → `@AGENTS.md`) |
| **Scoped rules by glob** | a matching file is in context | Cursor `.cursor/rules/eos-<id>.mdc` with `globs:` and `alwaysApply: false` (no `description`, so the rule is never listed); Cline `.clinerules/eos-<id>.md` with `paths:`; Claude Code `.claude/rules/eos-<id>.md` with `paths:`. A phase pack's rule carries only *Standards* and *Automated checks* plus a pointer to the full pack. Stack-pack globs are prefixed with the stack's directory (`web/**/app/**`) |
| **Skills by intent** | the task matches a description | `SKILL.md` folders: `.agents/skills/` (Cursor, Codex), `.cline/skills/`, `.claude/skills/`. Only the name and description are always visible; the body loads on demand |
| **Pack index** (fallback) | tools without scoped rules (e.g. Codex), or a human | generated `.eos/packs/INDEX.md`, one line per pack (`- security: touching auth, payments… → .eos/packs/phases/security.md`). `AGENTS.md` only carries a two-line pointer to it, so tools that auto-attach packs don't pay ~650 tokens for the index on every request |

**Stack detection by marker files** [Tested]. `eos init` scans to depth 3 and skips `node_modules`, `.venv`, `dist` and similar folders.
- `pyproject.toml`, `requirements.txt`, `uv.lock`, `Pipfile`, … → `python`. If the marker text mentions `fastapi` or `flask`, the `python-fastapi` or `python-flask` flavour pack is added.
- `package.json` or `tsconfig.json` → `typescript`; `next.config.*` → `nextjs` (which requires `typescript`).
- Ecosystems without a pack (`go.mod`, `Cargo.toml`, `composer.json`, `pom.xml`, `pubspec.yaml`, …) are *reported* with the hint `eos new-stack <id>`.

The package manager comes from the lockfile, then from the `packageManager` field (default pnpm), and is substituted into commands and CI. Override with `eos init --stacks python:services/api,nextjs:web`.

### 4.2 The token budget

Tokens are estimated at 4 characters per token; real tokenisers differ by roughly ±20%. Measured on a FastAPI (`api/`) + Next.js (`web/`) fixture with all four tools, using the real generated files [Tested, v0.2.0]. "Session start" = `AGENTS.md` + the tool's global profile + listed skill names/descriptions (+ `CLAUDE.md` notes and listed rule descriptions where the tool shows them). "Editing a route" = the path rules that attach when `api/app/api/routes/users.py` is in context.

| Tool | Session start, v0.1.0 → v0.2.0 | MCP tool schemas at start | Path rules while editing a route, v0.1.0 → v0.2.0 |
|---|---|---|---|
| Cursor | 3,114 → **1,724** | tool names only: Cursor loads MCP descriptions on demand ([Dynamic context discovery](https://cursor.com/blog/dynamic-context-discovery)) | 4,346 → **2,864** |
| Cline | 2,743 → **1,700** | **all enabled schemas on every request**: 4,450 + Postman + Figma (unmeasured) → **1,250** (Context7 only) | 4,331 → **2,899** |
| Claude Code | 2,816 → **1,747** | tool names only: MCP tool search is on by default ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)) | 4,331 → **2,899** |
| Codex | 2,743 → **1,700** | deferred behind `tool_search` on supported models ([openai/codex#29486](https://github.com/openai/codex/pull/29486)) | none: Codex reads `.eos/packs/INDEX.md` and one pack when needed |

MCP schema sizes (name + description + input schema, chars/4, measured 9 Oct 2026 with `tools/list`): GitHub `repos` read-only toolset ≈3,200 tokens for 13 tools (local `github-mcp-server` v2.0.2, as a proxy for the remote `/x/repos/readonly` endpoint); Context7 ≈1,250 for 2 tools; Playwright MCP 0.0.83 ≈4,600 for 25 tools. Postman and Figma need auth to list tools and were **not measured**. Cline's own users report 20k+ tokens for "hi" with five servers on ([cline/cline#9398](https://github.com/cline/cline/issues/9398)).

**v0.3.0 re-measurement** (same script, same fixture, run on the v0.2.0 tag and on v0.3.0): session start Cursor 1,715 → 1,740, Cline 1,691 → 1,716, Claude Code 1,738 → 1,763, Codex 1,691 → 1,716. The +25 tokens are one new escalation line in the core rules. Path rules while editing a route are unchanged (2,864 Cursor, 2,899 Cline/Claude Code). The table above was measured a few commits before the v0.2.0 tag, which is why it differs by about 9 tokens. Cline's MCP schemas in the default profile go from 1,250 to ≈4,450 on purpose: GitHub is now on for implementation work ([Section 26](#26-senior-review-v030)).

Where the v0.2.0 numbers come from:

| Item | ~Tokens | Present |
|---|---|---|
| Personal profile (global) | ~280 | always |
| `AGENTS.md`: core rules (~670), stack/commands table, 2-line pack pointer, team section | ~980 | always |
| Skill descriptions (12 intent/both packs) | ~320 | always (listed by every tool) |
| Path rule for one phase pack (Standards + Automated checks) | 410–700 | when a matching file is in context |
| Path rule for one stack pack (whole pack body) | 610–800 | when a file in that stack's directory matches |

**Budgets are enforced, not hoped for.** `eos check` runs in pre-commit and CI and fails when: a pack exceeds 1,200 tokens; a path rule exceeds 800; the eos blocks exceed 1,000; `AGENTS.md` exceeds 1,600; the profile exceeds 400; all skill descriptions together exceed 500, or one exceeds 160 characters; or a memory file exceeds its line cap (active-context 40, handoff 30, lessons 40, progress 200) [Tested].

What keeps context small in practice [Recommendation]:
- **Fresh session per story or task.** Long chats re-send history on every turn.
- **Paste the failing test name and about 20 relevant log lines**, not 2,000 lines. The stop hook already sends back at most 40 lines / 3,000 characters and saves the full log to `.eos/state/last-check.log` [Tested].
- **Stable prefix.** Nothing volatile (dates, counters, "current version" claims) lives in always-on files, and `AGENTS.md` and the rules don't change during a session, so provider prompt caches stay valid ([OpenRouter prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)).
- **MCP profiles per task** (v0.3.0): `eos mcp use minimal|build|review|api|design|debug-ui` switches servers per tool. The default `build` profile (GitHub read-only + Context7) costs Cline ≈4,450 tokens per request; `minimal` (Context7 only) costs ≈1,250 ([Section 10](#10-mcp-strategy)).
- **Ignore files** (`.cursorignore`, `.clineignore`) for build output, generated clients, fixtures and archives.

### 4.3 Why not one big rules file?

A single 10k-token rules file costs those tokens on every request. It also dilutes attention: the model weighs "how we write migrations" while it edits CSS. And it drifts when three tools each keep a slightly different copy. Scoped packs and generated adapters fix all three problems. The trade-off is that a rule only applies when its trigger fires. That is why the 7 core rules and the stop conditions stay always-on, and why safety-critical policy (secrets, protected paths, hook bypass) is enforced by **hooks**, not prose.

### 4.4 Anti-loop safeguards

Agents can loop: the same failing fix, the same command, a diff that keeps growing. eos uses three independent layers. Any one of them can stop a loop.

| Layer | Mechanism | Limit | What happens |
|---|---|---|---|
| **1. Rules** (always-on, in `AGENTS.md`) | stop conditions | 3 real fix attempts on the same failure · the same command and result 3× · diff well past the plan or touching a protected path · a long session that gets confused | The agent writes `memory/handoff.md` (tried / hypotheses / next step) and asks a human |
| **2. Loop-guard hook** (`eos guard`, before every shell command) | fingerprint = command + `git status` + `git diff` hash; read-only commands (`rg`, `grep`, `git status/log/diff`, `cat`…) are exempt | more than 3 identical runs on an unchanged code state | Cursor/Claude Code: **ask** the human. Cline: **cancel** with a message (Cline hooks cannot "ask"). Editing code changes the fingerprint, so a normal test → fix → test cycle is never blocked [Tested] |
| **3. Stop hook** (`eos guard cursor-stop` / `claude-stop`) | when the agent says it is done, run `pre-commit run --files <files changed in this session>` (your pre-existing dirty files are ignored; gitleaks waits for commit time; a timeout lets the agent stop) | attempt 1–2: send failures back · attempt 3: "STOP, write the handoff, ask the human" · then allow stop. Cursor's own `loop_limit: 3` also caps it | Prevents both "done but broken" and infinite fix loops [Tested] |

Hard blocks complement these and are **always denied**:
- `--no-verify`, `SKIP=` (hook bypass) and `git config core.hooksPath`;
- force-push;
- `rm -rf` of `/`, `~` or `.`;
- `curl … | sh`;
- `chmod -R 777`;
- printing the environment or secret variables;
- reading `.env*` and private-key files;
- writing to protected paths or outside the project.

**Human approval ("ask")** is required for:
- `git push`, `git reset --hard`, `git rebase`;
- `terraform`/`kubectl`/`helm`;
- publishing packages;
- running migrations or destructive SQL;
- DB clients;
- `gh` mutations;
- `ssh`/`sudo`;
- cloud CLIs;
- in Cursor, MCP tools whose names look like writes (`create`, `delete`, `merge`, …).

A command made only of read-only tools never prompts, even when its text mentions a risky word: `rg "DELETE FROM"`, `grep -r psql docs` or `git commit -m "docs: kubectl apply"` run straight away. A false prompt costs a human round-trip and teaches the agent to avoid searching. Anything that runs what it mentions (`bash -c`, `xargs`, `$(…)`, backticks, `find -exec`) still gets the full checks, and reading `.env` still asks [Tested].

The guard **fails open** (it logs to `.eos/state/guard.log` and allows) if it crashes, so a bug never bricks your editor. The trade-off is that hooks are defence in depth, not a security boundary (see [Section 20](#20-honest-caveats)).

### 4.5 The v0.2.0 context audit: what was wasting tokens or reasoning

An adversarial review of v0.1.0 against current tool docs and model-vendor guidance. The guiding sources:
- Anthropic: aim for "the smallest possible set of high-signal tokens", and prefer canonical examples over "a laundry list of edge cases" ([Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)). Newer Claude models are more responsive to the system prompt, so "dial back any aggressive language" such as CRITICAL/MUST ([Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)).
- OpenAI: contradictory or vague instructions make the model spend reasoning tokens reconciling them, and over-firm "be THOROUGH" wording causes over-gathering ([GPT-5 prompting guide](https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/gpt-5/gpt-5_prompting_guide.ipynb)).
- Cursor: keep rules focused; don't copy style guides (use a linter) or document common commands; skip rarely-applicable edge cases; a rule with `globs` and no `description` is auto-attached by path ([Cursor rules](https://cursor.com/docs/context/rules)).
- Claude Code: files over 200 lines "consume more context and may reduce adherence"; a `CLAUDE.md` that imports `@AGENTS.md` never makes Claude read it twice ([Claude Code memory](https://code.claude.com/docs/en/memory)).
- Cline reads `.clinerules/` and `AGENTS.md` but not `.cursor/rules`, so the adapters don't overlap ([Cline rules](https://docs.cline.bot/customization/cline-rules)). Codex concatenates `AGENTS.md` files up to `project_doc_max_bytes` (32 KiB by default) ([Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)).

| # | Finding in v0.1.0 | Why it hurt | Fix in v0.2.0 |
|---|---|---|---|
| 1 | The 22-line Context map sat in `AGENTS.md` | ~500 tokens per request in tools that already auto-attach packs and list skills: the same packs were described twice | Moved to generated `.eos/packs/INDEX.md`; `AGENTS.md` keeps a 2-line pointer |
| 2 | "both" packs were Cursor rules *with* a `description` and skills too | Cursor listed the description twice (~350 tokens) and could load the same body twice | Path rules never carry a description; the skill is the only intent trigger |
| 3 | Path rules carried the whole phase pack (entry, deliverables, exit checklist, handoff) | Phase-gate ceremony re-sent on every edit of a matching file | Rules carry only *Standards* and *Automated checks* plus a pointer; skills keep the full pack |
| 4 | Next.js glob `**/app/**` matched FastAPI's `api/app/*.py` | ~800 tokens of wrong-stack rules while editing Python, plus conflicting advice | Stack-pack globs are prefixed with the detected stack directory |
| 5 | Core rule: plan + wait for approval when a change touches more than 3 files | Ceremony on trivial refactors; approval round-trips | Plan + approval only for schema, public API, money, auth, infra or multi-module work; small changes: make, verify, report |
| 6 | "Paste the command and the tail of its output" (core) and "show the commands you ran and their output" (profile), next to "keep it short" | Forced verbose output; contradictory instructions cost reasoning | Each check reported in one line; output only for failures |
| 7 | "Ask, don't guess" for everything | Stalls on low-risk gaps | Ask for unclear requirements, money or security; otherwise state the assumption and continue |
| 8 | Bold walls, "~40 tool calls" heuristic, rewrite memory "at the end of every task", read memory at every session start | Emphasis inflation; arbitrary limits; churn and re-reads on trivial tasks | Plain text; the 40-call rule is gone; memory written only when there is state worth keeping and read when resuming |
| 9 | `progress.md` could grow forever; handoff cap was 40 in `eos check` but 30 in the docs | Unbounded files that later get read into context | `eos check` caps progress at 200 lines, handoff at 30 |
| 10 | Stop hook ran on every dirty file, including the human's own work in progress | The agent was sent to "fix" unrelated files on every stop (a loop trigger) | Only files changed in the current agent session are checked |
| 11 | Stop hook returned up to 60 uncapped lines and ran gitleaks (a Go build on first run); a timeout looked like a failure | Long logs re-fed into context; on a slow link a timeout made the agent retry pointlessly | 40 lines / 3,000 characters, full log on disk; gitleaks skipped at stop (still on commit); timeout lets the agent stop |
| 12 | `rg "DELETE FROM"`, `grep psql`, `git commit -m "…kubectl apply…"` triggered approval prompts; `git status` counted toward the loop guard | False prompts cost a human round-trip and teach the agent to avoid searching | Read-only command chains skip the ask patterns (except `.env`) and the loop guard |
| 13 | Four MCP servers on by default | Cline sends every enabled schema on every request (≥4,450 tokens here) | Two on by default; a per-server `clients` list kept GitHub out of Cline (v0.3.0 replaces this with per-task profiles, [Section 26](#26-senior-review-v030)) |
| 14 | BMAD dev persona injected testing-qa + all stack packs via `persistent_facts`; architect injected three packs | ~4-5k tokens per dev session, duplicating path rules that attach anyway | Dev injects one sentence; architect injects only the architecture pack |
| 15 | "TypeScript 7 (native compiler) is current" in a pack; duplicate stack "Definition of Done" sections | Volatile claims go stale; duplicates of the core rule | Removed |

**Not changed, and why:**
- **Phase packs keep their 7-section structure.** The full text is what a skill loads when a phase starts, and the sections drive `eos check`. Only the path-rule slice was cut.
- **Broad language globs on `backend`/`frontend`** (`**/*.py`, `**/*.tsx`). In a typical service almost every source file is server or UI code, so narrower globs would mostly miss. The slice keeps each under ~650 tokens.
- **Some security globs over-match** (`**/*token*` also matches design-token files). A false attach costs ~700 tokens; a missed security rule costs more.
- **The core still has 7 rules and 4 stop conditions.** Each one is either enforced by a hook or check, or is a judgment rule a check can't express (risk-scaled planning, when to ask).
- **Tool system prompts are not ours.** Cursor, Cline, Claude Code and Codex add their own system prompts and tool definitions; eos can't shrink those, and their size isn't published consistently, so they aren't in the table.

---
## 5. The agent memory system

Agents forget everything between sessions. "Memory" here means **files the agent reads at the start of (or during) a task**. The goal is that a brand-new chat, on any of your tools, knows the essentials of the project in a few thousand tokens.

### 5.1 Three scopes, seven layers

Memory is organised by **scope** (who it belongs to and how long it lives). Each scope has an owner, a size limit and an update rule.

| Scope | Layer | What lives there | Files (eos default) | Loaded when | Updated by / when |
|---|---|---|---|---|---|
| **Personal** (global, all projects) | L0 Profile | Language and answer style, engineering defaults, "never" list | `engineering-os/personal/PROFILE.md`, rendered by `bootstrap` to `~/.cursor/rules/eos-profile.mdc`, `~/.agents/AGENTS.md` (Cline), `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md` | Always | You. Edit the repo copy, then re-run `bootstrap` |
| | L0 Personal skills | Retro, handoff, new-stack | `~/.agents/skills`, `~/.cline/skills`, `~/.claude/skills` (copied with a `.eos-managed` marker) | On demand | The engineering-os repo |
| **Project** (in Git, reviewed in PRs) | L1 Core | Rules, commands table, pack-index pointer, Project specifics | `AGENTS.md` (eos blocks plus a team-owned section; BMAD may add its `<!-- bmad:context -->` block) | Always | eos blocks: `eos sync`/`update`. Team section: humans, via PR |
| | L2/L3 Packs | Stack and phase standards | `.eos/packs/**` → generated adapters | Just in time | Tech lead, via PR; then `eos sync` |
| | L4 Durable knowledge | Decisions, designs, contracts | `docs/adr/` (+ `INDEX.md`), `docs/architecture/`, contracts, `_bmad-output/` | On demand (pointers) | Architect/PM roles, approved by a human |
| | L4 Working memory | Now / next / blockers; done items; lessons | `memory/active-context.md` (≤40 lines), `memory/progress.md` (append-only), `docs/ai/lessons.md` (≤30 lines) | Active context at session start | The agent at the end of each task; reviewed in the PR |
| **Session** | L5 | Plan, conversation, handoff | plan file, `memory/handoff.md` (overwritten each time, ≤30 lines) | This session, and the next one if a handoff was written | The agent, when it stops (loop limit, blocker, end of session) |
| *(optional)* | L6 Graph memory | Cross-project hints | Memory MCP server | On demand via tools | Agent, with your approval |

**Why this order matters:** project-scope files are reviewed in PRs like code, so they are trustworthy. Session files change constantly, so they are short and get overwritten. Graph memory is the least transparent (the data is hidden in a store), so treat it as a cache of hints, never as the source of truth.

### 5.2 What each tool actually reads [Verified]

| Tool | Reads |
|------|-------|
| **Cursor** | `AGENTS.md` (root and subdirectories), `CLAUDE.md` (always applied), `.cursor/rules/*.mdc` (plain `.md` files in that folder are **ignored**), User Rules, Team Rules. Rule activation: `alwaysApply: true` → always; `globs` → when a matching file is in context; `description` only → agent decides; none → only when `@`-mentioned. ([Cursor Rules](https://cursor.com/docs/rules)) |
| **Cline** | `.clinerules/` or `.cline/rules/` (Markdown, optional `paths:` frontmatter; no frontmatter = always active; `paths: []` = disabled), `.cursorrules`, `.windsurfrules`, `AGENTS.md`, global `~/.agents/AGENTS.md`. ([Cline Rules](https://docs.cline.bot/customization/cline-rules)) |
| **Cursor Bugbot** | `.cursor/BUGBOT.md` (root always; nested ones for files below them). It does **not** read `.cursor/rules/*.mdc`. ([Bugbot docs](https://cursor.com/docs/bugbot)) |
| **BMAD** | Its skills (`.agents/skills/`, `.cline/skills/`), `_bmad/` config, `_bmad/custom/*.toml` overrides, `AGENTS.md` block, `_bmad-output/` artifacts |
| **Skills (both tools)** | Cursor: `.cursor/skills/` and `.agents/skills/` (`SKILL.md` with `name`, `description`, optional `paths`) ([Cursor Skills](https://cursor.com/docs/skills)); Cline: `.cline/skills/<name>/SKILL.md`, flat layout ([Cline Skills](https://docs.cline.bot/customization/skills)) |
| **Claude Code** | `CLAUDE.md` (root, nested, `~/.claude/CLAUDE.md`), files it imports with `@path` (eos: `@AGENTS.md`), `.claude/rules/*.md` (optional `paths:`), skills in `.claude/skills/` ([Claude Code memory](https://code.claude.com/docs/en/memory)) |
| **Codex** | `AGENTS.md` from `~/.codex/` and from the repo root down to the working directory; skills in `.agents/skills/` ([Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)) |

### 5.3 The anti-duplication rule

The fastest way to confuse an agent is to say the same thing in three places with small differences.

[Recommendation, implemented in eos]
- **Write each instruction exactly once.** `AGENTS.md` is canonical for project-wide facts, and `.eos/packs/*.md` is canonical for phase and stack standards.
- **Never hand-edit an adapter.**
  - `.cursor/rules/eos-*.mdc`, `.clinerules/eos-*.md`, `.claude/rules/eos-*.md` and the `eos-*` skills are generated by `python .eos/bin/eos.py sync`.
  - Each generated file starts with a "generated from … edit the pack" comment.
  - `eos check` (pre-commit and CI) fails on drift [Tested].
- Your own extra rules are fine. Name them without the `eos-` prefix and eos will never touch them.
- `BUGBOT.md` and `.coderabbit.yaml` contain **review checklists only**, pointing back to the packs.
- Do **not** keep a legacy `.cursorrules` file. Cline also reads it, so it becomes a hidden duplicate.

### 5.4 What goes in AGENTS.md (and what stays out)

BMAD's `bmad-project-context` documentation has the best short rule I found: directory trees, tech-stack lists and copies of `package.json` scripts **do not** belong, because "agents read code better than prose about code, and the copy goes stale". What *earns a line* is ([Set and Maintain Project Context](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/existing-codebases/set-and-maintain-project-context.md)):

- policy (frozen paths, generated files, branch rules, security/compliance);
- what config files cannot say (e.g. "the integration suite needs Postgres running; use `make test-int`");
- conventions that differ from ecosystem defaults;
- observed pitfalls (mistakes agents actually made);
- cross-component rules and required versions;
- pointers to where work lands and which nested files to read first.

A full example is in [Section 19.1](#191-agentsmd-generated).

### 5.5 Architecture Decision Records (ADRs)

An **ADR** is a short file recording one significant decision: context, options, decision, consequences. Use the light *MADR* format (Markdown ADR). Number them (`docs/adr/0007-use-outbox-for-ledger-events.md`), never edit an accepted ADR's decision — supersede it with a new one. Agents should be told in AGENTS.md: *"Before changing anything listed in docs/adr/INDEX.md, read the ADR; if your change contradicts it, stop and propose a new ADR."* This single line prevents a whole class of "the agent silently re-architected my system" problems.

### 5.6 Working memory (`memory/`)

Cline's documented **Memory Bank** pattern uses a `memory-bank/` folder with six files that the agent reads at the start of each task and updates at the end ([Cline Memory Bank](https://docs.cline.bot/best-practices/memory-bank)). With BMAD and ADRs you already have the *durable* half of that (brief, PRD, architecture, decisions). So eos keeps only a **slim working memory**, seeded once by `eos init` and owned by the project:

```
memory/
  active-context.md   # rewritten when work stops unfinished or after a meaningful change: Now / Next / Blockers / Recent decisions (≤ 40 lines)
  progress.md         # append one line per finished item (date | item | PR); archive yearly
  handoff.md          # overwritten when an agent stops (goal, state, tried, hypotheses, next step, needs-a-human-for)
docs/ai/lessons.md    # YYYY-MM-DD | context | do / don't | automation ticket   (≤ 30 lines)
```

The rules that maintain these files live in the core `AGENTS.md` block ("Memory rules"), so every tool follows the same protocol.

### 5.7 Knowledge-graph / memory MCPs

The reference MCP **Memory** server stores entities and relations in a local knowledge graph and exposes tools such as `read_graph`, `search_nodes` and `open_nodes` ([MCP memory server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)). [Recommendation] Treat it as optional (add in Phase 5 of the rollout). Good uses: cross-project personal knowledge ("in the last three projects, MTN MoMo callbacks arrived out of order"). Bad uses: anything that should be reviewed — architecture, rules, decisions. Those belong in Git.

### 5.8 Keeping memory fresh and small

| Mechanism | How |
|---|---|
| **Enforced size budgets** [Heuristic, Tested] | `eos check` in pre-commit and CI: packs ≤1,200 tokens, path rules ≤800, eos blocks ≤1,000, `AGENTS.md` ≤1,600, profile ≤400, all skill descriptions ≤500 tokens (each ≤160 chars). Line caps: active-context 40, handoff 30, lessons 40, progress 200. |
| **Overwrite, don't append** | `active-context.md` and `handoff.md` are *rewritten*, so they cannot grow. Only `progress.md` is append-only (one line per item). |
| **Lesson lifecycle** | mistake seen twice → lesson line → automated check → delete the lesson. The `eos-retro` skill does this and prunes (see [Section 6.9](#69-retros-that-update-the-rules)). |
| **"Record" the moment an agent errs** | One line per pitfall in *Project specifics* or `lessons.md`, with the reason (or BMAD `bmad-project-context` with intent *Record*). |
| **Refresh after big changes** | After a refactor or framework upgrade: run `eos detect` (stack changes), then `eos update`, then `bmad-project-context` → *Refresh*. |
| **Monthly audit** | Delete anything a linter, type or hook already enforces. "If a tool enforces it, the rule is redundant." |
| **Ownership** | `CODEOWNERS` assigns `AGENTS.md`, `.eos/`, `.cursor/`, `.clinerules/`, `.claude/`, `docs/adr/` to the tech lead. `.eos/**` and accepted ADRs are also write-protected for agents by the guard hook. |
| **Archive** | Finished epics' plans move to `_bmad-output/archive/` and are listed in `.cursorignore`/`.clineignore`. |

### 5.9 Update rules at a glance

| File | Who writes | When | Rule |
|---|---|---|---|
| `PROFILE.md` | you | rarely | ≤400 tokens; preferences only, no project facts |
| `AGENTS.md` eos blocks | `eos sync`/`update` | on pack or stack change | never hand-edit (it will be overwritten) |
| `AGENTS.md` Project specifics | team | when a newcomer (human or AI) gets something wrong | one line per fact; no directory trees or dependency lists |
| `docs/adr/NNNN-*.md` | agent drafts, human accepts | each hard-to-reverse decision | never edit an accepted ADR; supersede it |
| `memory/active-context.md` | agent | when work stops unfinished or after a meaningful change | rewrite, ≤40 lines |
| `memory/progress.md` | agent | each finished item | append one line |
| `memory/handoff.md` | agent | when it stops without finishing | overwrite, ≤30 lines |
| `docs/ai/lessons.md` | agent proposes, human approves | mistake seen twice | ≤30 lines; delete when automated |

---

## 6. Self-checking, reviewer agents and retros

### 6.1 The standard loop for one story

```
          ┌───────────── spec / ticket with EARS acceptance criteria ─────────────┐
          ▼                                                                       │
 [1 PLAN]  agent reads AGENTS.md + spec + relevant code → writes plan file         │
          │   (human approves plan for risky stories: plan_checkpoint)              │
          ▼                                                                       │
 [2 RED]   agent writes failing tests from acceptance criteria → runs them → FAIL  │
          ▼                                                                       │
 [3 GREEN] agent implements the smallest change → runs tests → PASS               │
          ▼                                                                       │
 [4 GATES] format, lint, types, arch boundaries, unit+integration tests, security │
          │   (hooks run fast checks after each edit; full set before "done")       │
          ▼                                                                       │
 [5 REVIEW] reviewer (different model) reviews diff AGAINST the spec → triage     │
          │   patch / defer / decision-needed                                       │
          ▼                                                                       │
 [6 PR]    CI gates + review bot + human review (mandatory on protected paths) ───┘
```

`bmad-build` already implements steps 1, 3, 5 (investigate → plan → implement → review → fix). You add **step 2 (TDD-first)** through the dev agent customisation and **step 4** through the eos stop hook, pre-commit and CI.

### 6.2 Plan/Act separation

- **Cline**: Plan mode is read-only exploration; Act mode edits. For big changes `/deep-planning` writes `implementation_plan.md` and opens a fresh implementation task ([Cline Plan & Act](https://docs.cline.bot/core-workflows/plan-and-act)).
- **Cursor**: use a planning pass first (Plan mode or a "plan only, don't edit" prompt), save the plan into the story's plan file, then implement in a new chat.
- **BMAD**: `bmad-build-auto` accepts `Halt after planning.` so a human can approve a plan before an unattended run ([Autonomous Development Loops](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/autonomous-development-loops.md)).

### 6.3 Making the dev agent follow the standards (BMAD customisation)

BMAD lets a team shape each persona with `persistent_facts` in `_bmad/custom/<skill>.toml`. These files are committed; personal variants go in `*.user.toml`, which is gitignored ([Adopt BMad Across a Team](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/customize/adopt-bmad-across-a-team.md)). Entries are either sentences or `file:` references (globs allowed), and they **append** to BMAD's defaults. eos ships one override per persona and seeds them with `eos init --bmad`. This is the dev agent's:

```toml
# _bmad/custom/bmad-agent-dev.toml  (from engineering-os/integrations/bmad/custom/)
# Arrays append to BMAD defaults. No `file:` packs here on purpose: stack and testing packs already attach by
# file path in Cursor/Cline/Claude Code, so injecting them again would load ~4-5k tokens twice per session.
[agent]
persistent_facts = [
  "A story is done when the stack full check in AGENTS.md is green; after 3 failed fix attempts on the same check, write memory/handoff.md and ask.",
]
```

[Tested] On a real `bmad-method@6.12.1` headless install, BMAD's own resolver (`python3 _bmad/scripts/resolve_customization.py --skill <dir> --project-root . --key agent.persistent_facts`) returned `persistent_facts` entries merged after the defaults (verified on v0.1.0's overrides, which used `file:` entries; the v0.2.0 files use the same keys). The architect, PM, analyst and UX overrides load the architecture, requirements, discovery and ux-design packs respectively. The dev agent loads no packs on purpose: stack, testing and backend/frontend packs already attach by file path, so injecting them as well cost ~4–5k duplicate tokens per session; data-modeling and api-design reach the architect as skills. *(Re-check the keys with `bmad-customize` whenever you upgrade BMAD; the keys changed in v6.12.)*

### 6.4 Reviewer agents and AI code-review bots

| Layer | Tool | Configure with | Notes |
|-------|------|----------------|-------|
| In-session | `bmad-build` built-in review (quick lens) | `_bmad/custom/bmad-build.toml` | Cheap, catches obvious issues |
| Pre-PR deep review | `bmad-code-review` *thorough* (several lenses in parallel: adversarial, edge-case hunter, verification gap…) | `bmad-customize` to add lenses or run a lens on another model | Use on risky changes; feed it the spec/plan — without intent it can only compare the diff to itself |
| PR bot (choose one primary) | **Cursor Bugbot** | `.cursor/BUGBOT.md` (root + nested); `bugbot run verbose=true` on a PR shows which rules were included | Access included in Pro/Pro+/Ultra per Cursor's pricing page ([Bugbot](https://cursor.com/docs/bugbot)) |
| | **CodeRabbit** | `.coderabbit.yaml` with `reviews.path_instructions` (glob + instructions) | Separate product/pricing; check current plan ([CodeRabbit config](https://docs.coderabbit.ai/reference/configuration)) |
| Deterministic | CodeQL, Semgrep, SonarQube Cloud (optional) | CI | Not AI, but more reliable for known bug classes |
| Human | You (CODEOWNERS) | Branch protection | Mandatory on protected paths |

[Recommendation] Running two AI PR bots doubles the noise more than it doubles the catch rate. Pick **one** bot as primary; use `bmad-code-review` as the targeted deep reviewer.

### 6.5 Hooks: automatic checks inside the agent loop

**Hooks** are scripts that the agent tool runs at fixed moments: before a shell command, before a file edit, when the agent stops. They are deterministic, so the model cannot "forget" them. In eos, every hook calls **one shared guard**, `python3 .eos/bin/eos.py guard <mode>`, so the policy is identical across tools and can be unit-tested [Tested: 29 unit tests].

| Tool | Events wired by `eos init` | Decision vocabulary [Verified] |
|---|---|---|
| **Cursor** (`.cursor/hooks.json`) | `beforeShellExecution`, `preToolUse`, `beforeReadFile`, `beforeMCPExecution`, `stop` (`loop_limit: 3`) | allow / deny / ask (`user_message`, `agent_message`). Exit code 2 = deny. `stop` can return `followup_message`. "ask" on `preToolUse` is accepted but not enforced, so eos uses deny there ([Cursor Hooks](https://cursor.com/docs/hooks)) |
| **Claude Code** (`.claude/settings.json`) | `PreToolUse` (matcher `Bash\|Edit\|Write\|MultiEdit\|NotebookEdit\|Read`), `Stop` | `hookSpecificOutput.permissionDecision`: allow / deny / ask. `Stop` → `{"decision":"block","reason":…}` keeps the agent working. Input `stop_hook_active` prevents infinite loops ([Claude Code hooks](https://code.claude.com/docs/en/hooks)) |
| **Cline** (`.clinerules/hooks/PreToolUse`, executable) | `PreToolUse` | `{"cancel": bool, "errorMessage", "contextModification"}`; there is no "ask". Hooks must be enabled in Cline settings, and they run on macOS/Linux only per the v3.36 docs ([Cline hooks](https://docs.cline.bot/features/hooks)) |
| **Codex** | none generated | relies on its sandbox and approval modes, plus `AGENTS.md`, git hooks and CI ([Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)) |

What the guard enforces:

| Policy | Examples | Decision |
|---|---|---|
| Secret files | `.env`, `.env.*` (except `.example`/`.sample`/`.template`), `*.pem`, `*.key`, `*.p12`, `id_rsa`-style keys, `secrets/**`, `credentials*.json`, `.npmrc`, `.pypirc`, `.netrc`, `~/.aws/credentials`, `~/.kube/config` | deny read and write |
| Protected paths (`.eos/protected.txt`) | `.eos/**`, `.github/workflows/**`, `.pre-commit-config.yaml`, lockfiles, `CODEOWNERS`; `tracked:` prefix = only *already-committed* migrations and accepted ADRs (new ones are allowed) | deny write |
| Outside the project | absolute paths outside the repo root | deny write |
| Hook or check bypass, force-push, `curl \| sh`, `rm -rf /`, printing secrets | see [Section 4.4](#44-anti-loop-safeguards) | deny |
| Pushes (v0.3.0) | with `push_policy: feature-branches`, a push to a non-protected branch is allowed; protected branches, tags, `--delete`, `--all`/`--mirror`, force-with-lease, detached HEAD and pushes inside `sh -c` ask; `--force`/`-f`/`+refspec` are denied even after `git -C dir` | allow / ask / deny |
| Risky but legitimate commands | push (when `push_policy` is `ask`), history rewrite, infra, cluster, publish, migrations, destructive SQL, DB clients, `gh` mutations, ssh/sudo, cloud CLIs. A chain of read-only commands (`rg`, `grep`, `cat`, `git status/log/diff/commit`…) is exempt even if its text mentions one of these; `bash -c`, `xargs`, `$(…)` and `find -exec` are not | ask (Cline: cancel with an explanation, configurable via `cline_ask`) |
| Loop guard | same non-read-only command on the same code state more than 3× | ask |
| MCP write tools (Cursor `beforeMCPExecution`) | tool names containing `create`, `update`, `delete`, `merge`, `push`, `write`, `send`, `deploy`, `run`, … | ask (`mcp_write_ask`). Claude Code and Cline use their own per-tool MCP approval prompts; keep auto-approve off for write tools |
| Stop gate | `pre-commit run --files <changed in this session>` when the agent claims it is done (gitleaks skipped here; it runs at commit) | feed back at most 40 lines / 3,000 chars (full log in `.eos/state/last-check.log`); escalate to a handoff on attempt 3; a timeout allows the stop |

Tune it in `.eos/config.json` (`loop_limit`, `stop_check` = `auto` / `off` / a custom command, `stop_check_timeout`, `cline_ask`, `mcp_write_ask`, `push_policy`, `protected_branches`) and `.eos/protected.txt`. Both are project-owned.

### 6.6 Guardrails against agents "cheating" tests

**Reward hacking** = the agent optimises for "tests pass" rather than "the feature works": editing the test, skipping it, hard-coding the expected value, mocking the thing under test, loosening a threshold, or special-casing test inputs. Recent writing on this recommends keeping the "oracle" (the checks) outside what the agent can edit, auditing test changes, and using mutation testing to prove tests can fail ([Protect the oracle](https://developertoolkit.ai/en/workflows/test/protect-the-oracle/), [arXiv: The Verification Horizon](https://arxiv.org/html/2606.26300)).

Defence in depth [Recommendation]:

1. **Edit guard (hooks):** protected paths cannot be edited by the agent (6.5).
2. **CODEOWNERS + branch protection:** `tests/contract/`, `.github/`, `.eos/`, `pyproject.toml [tool.coverage]`, `vitest.config.*` require your approval.
3. **CI test-diff check:** `eos test-integrity` (below) fails the PR unless a human adds the `test-change-approved` label.
4. **Holdout tests:** contract tests generated from OpenAPI (`schemathesis`) and E2E tests written from the *spec* by a different agent/session than the implementer.
5. **Mutation testing:** `mutmut` (Python) and Stryker (JS/TS) on critical modules (ledger, fees, idempotency) weekly or on PRs touching them. If mutants survive, tests are too weak.
6. **Property-based tests** (`hypothesis`, `fast-check`): harder to "special-case" than example tests.
7. **Coverage as a floor, not a goal:** require coverage *not to drop* (diff coverage), not a magic number.
8. **Review prompt:** reviewers must answer: "Did this change modify any test? Was each modification justified by the spec?"

**What `eos test-integrity` checks** [Tested]. It runs in the `eos-core` CI job against the PR base, and includes untracked files when run locally. It flags:
- added skip, only or xfail markers (`@pytest.mark.skip`, `it.only`, `t.Skip`, …);
- added suppressions (`# type: ignore`, `noqa`, `eslint-disable`, `@ts-expect-error`, `pragma: no cover`);
- a net removal of assertions in test files;
- deleted test files;
- lowered coverage or mutation thresholds;
- edits to quality-gate config.

Any finding fails CI unless a human adds the PR label `test-change-approved`.

### 6.7 Background and cloud agents

- **Cursor Cloud Agents** (formerly Background Agents) run in a remote VM configured by `.cursor/environment.json` (Dockerfile or snapshot, `install`, `start`, terminals, ports) ([Cursor Cloud Agents](https://cursor.com/docs/cloud-agents), [setup](https://cursor.com/docs/cloud-agent/setup)). Good for: well-specified stories after the patterns are set, dependency upgrades, flaky-test investigation. They push branches/PRs you review.
- **BMAD `bmad-build-auto`** is the unattended *worker* for one ticket; it never picks the next ticket. An orchestrator (you, an AI session, or the **BMad Loop** module) dispatches workers. It requires subagent support; if unavailable it halts with `blocked`.
- [Recommendation] Unattended runs only after the first stories of an epic have been built interactively (BMAD says early stories "settle the architecture... Give those decisions human attention before automating repetitions").
- Use **Git worktrees** (one folder per branch) to let two agents work in parallel without stepping on each other.

### 6.8 Evals for your AI system

Treat prompts, rules and skills as code that can regress.
- `evals/agent-tasks/` — the mini task set from 9.7, re-run after big rule changes or when switching models.
- `evals/review/` — 5 PRs with known seeded bugs; does your review setup catch them? (Good way to choose between Bugbot and CodeRabbit.)
- Record results in `evals/RESULTS.md` with date, model, pass rate, cost.

---

### 6.9 Retros that update the rules

Self-optimisation needs a loop that *changes the system*, not just a chat that says "lesson learned". eos ships a personal skill, **`eos-retro`**. It never auto-runs (`disable-model-invocation: true`). You invoke it after a story, an incident or a bad session:

1. **Collect evidence. Don't rely on memory.** Use git log, PR comments, CI failures, `memory/progress.md` and `memory/handoff.md`, and `docs/ai/lessons.md`.
2. **List the mistakes.** Give each one an impact, a root cause (missing context? wrong pack? no check? vague spec?) and a count of how often it has happened.
3. **Pick the cheapest fix that lasts**, in this order of preference: **automated check** (lint rule, test, type, hook, protected path) > **one pack line** > **one lesson line**.
4. **Prune.** Delete lessons that are now enforced, and run `eos check` so every file stays within budget.
5. **Propose diffs.** Apply them only after the human approves; rule changes are reviewed like code.
6. **Upstream general fixes.** If a fix would help every project, it goes to the `engineering-os` repo, and `eos update` delivers it everywhere. That is how the system improves across projects instead of within one.

BMAD's `bmad-retrospective` (per epic) produces the *what happened*; `eos-retro` turns it into *what changes*.

---

## 7. Tool adapters: Cursor, Cline, Claude Code, Codex

### 7.1 Your tools and their roles

| Tool | Role in the system | Notes |
|------|-------------------|-------|
| **Cursor Pro+** | Main IDE and main agent (planning, implementation, reviews), Bugbot for PR review, optional Cloud Agents | Plans: Pro $20/mo, Pro+ $60/mo, Ultra $200/mo, each with two usage pools: "Cursor Models" and "Other Models" (third-party models at API price). Cursor's own guide says daily Agent users "typically" spend $60–$100/mo total usage. [Verified] ([Cursor Models & Pricing](https://cursor.com/docs/models-and-pricing)) |
| **Cline (inside Cursor)** | Second agent with *your own* API key (OpenRouter). Use for cheap models, Plan/Act mode, long tasks you want to control step by step | Install from Cursor's extension marketplace (Open VSX), extension ID `saoudrizwan.claude-dev`; choose provider "OpenRouter" ([Cline install docs](https://docs.cline.bot/getting-started/installing-cline)) |
| **OpenRouter** | One API key, many model vendors; spend caps per key | Per-key credit limit with daily/weekly/monthly reset ([OpenRouter limits](https://openrouter.ai/docs/api_reference/limits)) |
| **BMAD Method v6.12.1** | Lifecycle framework: analyst/PM/architect/UX/dev agent personas + planning, build and review skills | Free, MIT licence. Latest stable npm `bmad-method` 6.12.1 (4 Oct 2026). [Verified] |
| **MCP servers** | Give agents controlled access to GitHub, Postman, Figma, docs, DB (read-only) | See [Section 10](#10-mcp-strategy) |
| **GitHub + Actions** | Source of truth, CI/CD gates, branch protection, attestations | |
| **Claude Code** (optional) | Terminal/IDE agent; strong for long refactors and reviews in a fresh context | Reads `CLAUDE.md` → `@AGENTS.md`; eos generates rules, skills and hooks ([Claude Code docs](https://code.claude.com/docs/en/memory)) |
| **Codex** (optional) | OpenAI's coding agent (CLI/IDE/cloud) | Reads `AGENTS.md`; MCP in `~/.codex/config.toml` ([Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)) |
| **engineering-os** | The operating system in this document: packs, adapters, guard hooks, memory templates, bootstrap/init | Your fork; v0.3.0 ([Section 11](#11-reproducibility-the-engineering-os-repo)) |

### 7.2 How Cursor and Cline split the work

[Recommendation] Use Cursor's agent as the default and Cline as a deliberate second tool, not as a duplicate.

| Use **Cursor Agent** when… | Use **Cline + OpenRouter** when… |
|---|---|
| You are doing interactive implementation and want tight IDE integration | The task is bulky but low-risk (docs, test scaffolding, mechanical refactors, translations FR/EN) |
| You want Cursor's first-party models from the larger included pool | You want to try a cheaper or specialist model without touching your Cursor quota |
| You need Bugbot, Cloud Agents or Cursor hooks | You want explicit **Plan → Act** gating, `/deep-planning`, `/smol` (compress) and `/newtask` (hand-off) ([Cline Plan & Act](https://docs.cline.bot/core-workflows/plan-and-act), [Cline commands](https://docs.cline.bot/core-workflows/using-commands)) |
| | You want a *different model family* to review the work of the first one (cross-model review catches different bugs) |

---

### 7.3 The adapter matrix: one source, four tools

`AGENTS.md` is the shared standard: a plain Markdown file read by many agents ([agents.md](https://agents.md/)). Everything else is a *thin adapter* that `eos sync` generates from `.eos/packs/` [Tested]:

| Concern | Cursor | Cline | Claude Code | Codex |
|---|---|---|---|---|
| Always-on project rules | `AGENTS.md` | `AGENTS.md` | `CLAUDE.md` containing `@AGENTS.md` (import) | `AGENTS.md` (root and nested) |
| Scoped rules by path | `.cursor/rules/eos-<id>.mdc` (`globs`, `alwaysApply: false`, never a `description`) | `.clinerules/eos-<id>.md` (`paths:`) | `.claude/rules/eos-<id>.md` (`paths:`) | `.eos/packs/INDEX.md`, read on demand |
| Skills (intent packs) | `.agents/skills/eos-<id>/SKILL.md` | `.cline/skills/eos-<id>/SKILL.md` | `.claude/skills/eos-<id>/SKILL.md` | `.agents/skills/…` (shared with Cursor) |
| Guard hooks | `.cursor/hooks.json` | `.clinerules/hooks/PreToolUse` | `.claude/settings.json` | n/a (sandbox and approvals) |
| Personal profile (global) | `~/.cursor/rules/eos-profile.mdc`; paste into *User Rules* if it isn't picked up | `~/.agents/AGENTS.md` (eos block) | `~/.claude/CLAUDE.md` (eos block) | `~/.codex/AGENTS.md` (eos block) |
| MCP (global) | `~/.cursor/mcp.json` with `${env:VAR}` | `cline_mcp_settings.json` (literal values, chmod 600) | `claude mcp add --scope user …` script | `~/.codex/config.toml` with `bearer_token_env_var` |
| BMAD skills | `.agents/skills/bmad-*` | `.cline/skills/bmad-*` | `.claude/skills/bmad-*` | `.agents/skills/bmad-*` |

Sources: [Cursor rules](https://cursor.com/docs/rules), [Cursor skills](https://cursor.com/docs/skills), [Cursor hooks](https://cursor.com/docs/hooks), [Cline rules](https://docs.cline.bot/customization/cline-rules), [Cline skills](https://docs.cline.bot/customization/skills), [Cline hooks](https://docs.cline.bot/features/hooks), [Claude Code memory and rules](https://code.claude.com/docs/en/memory), [Claude Code skills](https://code.claude.com/docs/en/skills), [Claude Code hooks](https://code.claude.com/docs/en/hooks), [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md), [Codex MCP](https://developers.openai.com/codex/mcp). The BMAD tool-id → folder mapping comes from `npx bmad-method@6.12.1 install --list-tools` [Tested].

**Choosing tools per project:** `eos init --tools cursor,cline,claude,codex`. The default is the tools you chose at bootstrap, otherwise Cursor and Cline. Unused adapters are simply not written. Adding a fifth tool (Copilot, Gemini CLI, Windsurf, …) means adding one adapter function in `bin/eos.py`. The packs don't change.

### 7.4 Rules for running several agents

- Both or all agents read the same `AGENTS.md`, so they share project memory automatically.
- **Never let two agents edit the same files at the same time.** Use separate branches or Git worktrees.
- Use a *different* tool or model family to review the work of the first one. Cross-model review catches different bugs.

---

## 8. The lifecycle: BMAD as the workflow engine

### 8.1 BMAD in October 2026 — what is current (verify before you follow old tutorials)

Many tutorials still show v4 or early-v6 commands. On 9 Oct 2026 there are **two current "shapes" of BMAD**, and the difference matters:

| | **Stable release v6.12.1** (npm, 4 Oct 2026) | **`main` branch / docs website** (unreleased at research time) |
|---|---|---|
| Install | `npx bmad-method install` (classic installer; pin with `npx bmad-method@6.12.1 install`; prerelease: `@next`) | `npx skills add bmad-code-org/BMAD-METHOD` (Skills CLI), then ask the `bmad` skill to run `bmad setup` |
| Guide skill | `bmad-help` | `bmad` hub (`bmad setup`, `bmad status`) |
| Stories / tracking | `bmad-create-epics-and-stories` → `bmad-sprint-planning` | `bmad-ticket` (epics, ordered `tickets.toml`) |
| Implementation | `bmad-build` / `bmad-build-auto` | same |
| Sources | [v6.12.1 install doc](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.1/docs/start/install-bmad.md), [v6.12.1 skills reference](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.1/docs/reference/skills-and-agents.md) | [README on main](https://github.com/bmad-code-org/BMAD-METHOD), [docs.bmad-method.org install](https://docs.bmad-method.org/start/install-bmad/) |

**[Recommendation]** For a reusable template, **pin the stable release** (`npx bmad-method@6.12.1 install`, choose the BMad Method module and both Cursor and Cline as tools) and treat the Skills-CLI layout as the *next* version to migrate to once it is released. Always trust `bmad-help` inside your installed version over any web tutorial, including the official website, which already documents `main`.

What is the same in both shapes [Verified]:
- **Prerequisites:** Node.js 20.12+ for the installer, and **uv** for skills that run Python helper scripts (including `bmad-build`).
- **Where skills land:** Cursor → `.agents/skills/`; Cline → `.cline/skills/`. Config and scripts go in `_bmad/`; outputs (PRDs, specs, stories, plans) in `_bmad-output/`. Team customisations go in `_bmad/custom/*.toml` (committed); personal ones in `*.user.toml` (gitignored).
- **Five named agents:** Analyst (Mary) `bmad-agent-analyst`, PM (John) `bmad-agent-pm`, Architect (Winston) `bmad-agent-architect`, Developer (Amelia) `bmad-agent-dev`, UX Designer (Sally) `bmad-agent-ux-designer`. The Technical Writer persona is "on hiatus"; project context is handled by `bmad-project-context`.
- **Planning skills:** `bmad-brainstorming`, `bmad-forge-idea`, `bmad-deep-recon` (research), `bmad-product-brief`, `bmad-prfaq`, `bmad-prd` (create/update/validate), `bmad-ux`, `bmad-architecture`, `bmad-spec`, `bmad-correct-course`, `bmad-retrospective`, `bmad-party-mode` (several personas in one discussion), `bmad-advanced-elicitation`.

Recent changes worth knowing [Verified] ([releases](https://github.com/bmad-code-org/BMAD-METHOD/releases)):
- **v6.11 (Aug 2026):** "Quick Dev becomes Build". `bmad-quick-dev` → `bmad-build`, `bmad-dev-auto` → `bmad-build-auto`; `bmad-create-story`/`bmad-dev-story` deprecated; the official implementation chain became `bmad-sprint-planning → bmad-build → bmad-code-review`; review skills merged into `bmad-review` with *lenses* (`adversarial`, `edge-case-hunter`, `verification-gap`, …); `bmad-project-context` writes one verified block into `AGENTS.md`. Old names still work through forwarding shims until v7.
- **v6.12 (Sep 2026):** Build decides the ceremony *after* investigating the change; review triage records a verdict and evidence for every finding; `bmad-project-context` adopts a hand-written `AGENTS.md` instead of rewriting it; `persistent_facts` ships empty (breaking for some customisations).
- **Tracks.** The v6 docs describe three planning tracks — **Quick Flow** (bug fixes, small features, 1–15 stories, tech-spec only), **BMad Method** (products/platforms, 10–50+ stories, PRD + Architecture + UX), **Enterprise** (compliance, multi-tenant, 30+ stories, adds Security + DevOps docs) ([v6 getting started](https://github.com/bmad-code-org/BMAD-METHOD/blob/e36f219c/docs/tutorials/getting-started.md)). The newest docs express the same idea as a *planning path sized by intent*: well-defined small intent → `bmad-spec` → `bmad-build`; epic-sized → spec + stories; project-sized (≈20+ sessions) → full planning documents, then a spec per epic ([Choose a Planning Path](https://docs.bmad-method.org/plan/choose-a-planning-path/)). Your fintech product is a **BMad Method track project with Enterprise elements** (security and DevOps documents), because it moves money.
- **Add-on modules:** Test Architect (enterprise testing), BMad Loop (builds, verifies and runs retros for a whole epic unattended), Creative Intelligence Suite, and a builder module (being replaced by "Toolsmith" on `main`).
- French documentation exists in the repo (`docs/fr/`), useful for francophone teammates.

### 8.2 The lifecycle, phase by phase

Each phase has: a BMAD skill, an output artifact (a file in Git), a model tier, and a gate (what must be true to move on).

| Phase | BMAD skill(s) / agent | Artifact (in Git) | Model tier* | Gate to next phase |
|-------|-----------------------|-------------------|-------------|--------------------|
| 0. Brainstorm | `bmad-brainstorming`, `bmad-forge-idea` (Analyst) | `brainstorm-*.md`, `forge-*.md` | Premium or mid | Idea survives the "forge" or is killed cheaply |
| 1. Product understanding | `bmad-deep-recon` (cited research), `bmad-product-brief`, optional `bmad-prfaq` (Amazon-style "working backwards") | `research-*.md`, `brief-*.md`, `prfaq-*.md` | Premium | Problem, users, constraints and success metrics written down |
| 2. PRD | `bmad-prd` (PM) — create / update / **validate** | `prd-*.md` | Premium | PRD validated; non-goals explicit; regulatory notes (e.g. COBAC/BEAC or data-protection obligations relevant to your fintech) listed for human/legal review |
| 3. UX | `bmad-ux` (UX Designer) + Figma MCP | `DESIGN.md`, `EXPERIENCE.md`, `ux-*.md` | Premium/mid | Key flows and states (empty, error, loading) defined |
| 4. Architecture | `bmad-architecture` (Architect) | `architecture-*.md` + ADRs in `docs/adr/` | Premium | ADRs for every hard-to-reverse decision; module boundaries defined (they become import-linter / dependency-cruiser rules) |
| 5. Specs & stories | `bmad-spec` per epic → `bmad-create-epics-and-stories` (v6.12.1) / `bmad-ticket` (next) | `spec-*.md`, epics/stories (`tickets.toml` in next) | Premium/mid | Each story fits one Build session; acceptance criteria testable (EARS format, see 8.4) |
| 6. Sprint planning | `bmad-sprint-planning` (readiness check + sprint status file) | sprint status file | Mid | Ordered, dependency-aware backlog |
| 7. Implementation | `bmad-build` (interactive) or `bmad-build-auto` (unattended, needs subagents) | Code + tests + plan file (`status: built`) | Daily driver (Cursor models) or cheap (Cline) | Stack full check + pre-commit green ([Section 15.3](#153-local-quality-gates-pre-commit-one-hook-manager)) |
| 8. Review | Built-in quick review → `bmad-code-review` *thorough* for risky changes → PR bot → human | Findings appended to the plan's `## Code Review` | Premium for thorough review; different model family than the author if possible | No unresolved high-severity findings; human approval on protected paths |
| 9. Release | CI/CD ([Section 15](#15-monorepo-and-automation)) + release pack | Tag, changelog, SBOM, attestation | — | All CI gates; canary healthy |
| 10. Operations | Runbooks, SLO dashboards; `bmad-correct-course` when reality diverges; `bmad-retrospective` per epic | `docs/runbooks/`, postmortems, retro notes | Mid | Error budget respected; lessons → `eos-retro` → checks/packs |

\*Model tiers are explained in [Section 9.2](#92-model-routing-by-role).

BMAD's own advice on review depth is worth copying exactly: use *quick* reviews in the personal loop, bump to *thorough* on high-risk changes, and make sure every PR passes a thorough `bmad-code-review` eventually, for example through a PR bot ([Review a Change](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/review-a-change.md)). It also warns that non-trivial findings on a *third* review pass usually mean the problem is upstream (design or spec), not in the code.

### 8.3 Spec-driven development: BMAD vs GitHub Spec Kit vs Kiro

**Spec-driven development (SDD)** means the written specification is the primary artifact; code is generated and checked against it.

| | **BMAD Method** | **GitHub Spec Kit** | **Kiro-style specs** |
|---|---|---|---|
| What it is | Full lifecycle method with agent personas, planning, build, review, retros | Open-source toolkit (CLI `specify`, latest v1.1.2, 7 Oct 2026) adding SDD commands to many agents | Spec format of the Kiro IDE (AWS) |
| Flow | brief → PRD → UX → architecture → spec → tickets → build → review → retro | `/speckit-constitution` once; then `/speckit-specify → plan → tasks → implement → converge`, with optional `clarify`, `checklist`, `analyze` gates | `.kiro/specs/<feature>/requirements.md → design.md → tasks.md` |
| Requirements style | Free-form PRD and spec with acceptance criteria | Spec + checklists | **EARS** notation: "WHEN [condition] THE SYSTEM SHALL [behaviour]" |
| Persistent context | `AGENTS.md` block + `_bmad/custom` | "constitution" (project principles) | "steering" files: `product.md`, `tech.md`, `structure.md` |
| Best for | Products and multi-epic projects; teams wanting roles and reviews | Feature-level SDD inside an existing process; very tool-agnostic | Teams using Kiro; the EARS format is useful anywhere |
| Sources | [BMAD](https://github.com/bmad-code-org/BMAD-METHOD) | [Spec Kit README](https://github.com/github/spec-kit/blob/main/README.md), [quickstart](https://github.github.com/spec-kit/quickstart.html) | [Kiro specs](https://kiro.dev/docs/specs/feature-specs/), [Kiro steering](https://kiro.dev/docs/steering.md) |

**[Recommendation] Where each fits in your system:**

- **BMAD is the backbone** (lifecycle, roles, build loop, review, retros).
- **Borrow from Kiro:** write acceptance criteria in EARS form inside BMAD specs and tickets. They become test names almost one-to-one, which makes TDD-first agents more reliable.
- **Borrow from Spec Kit:** the *constitution* idea — a short list of non-negotiable principles. In this blueprint it lives in `docs/standards/constitution.md` and is referenced from `AGENTS.md`. Also copy the "**converge**" idea: repeat implement → verify-against-spec until nothing is missing.
- **Do not install Spec Kit and BMAD in the same repo** for the same work. Two frameworks produce two sets of artifacts and confuse agents about which one is authoritative. Use Spec Kit only if a client or team already runs it.

### 8.4 Acceptance criteria template (EARS)

```markdown
### Story 2.3 — Idempotent transfer creation

**Acceptance criteria (EARS)**
- AC1: WHEN a client POSTs /v1/transfers with an Idempotency-Key that was already used
       with the same body, THE SYSTEM SHALL return the original response and status code
       without creating a new transfer.
- AC2: IF the same Idempotency-Key is reused with a different body,
       THEN THE SYSTEM SHALL return 422 with error code IDEMPOTENCY_KEY_REUSED.
- AC3: WHILE a request with a given key is still processing,
       THE SYSTEM SHALL return 409 to concurrent requests with that key.

**Test mapping:** tests/api/test_transfers_idempotency.py::test_ac1_* … test_ac3_*
**Out of scope:** key expiry policy (see ADR-0012)
**Human review required:** yes (money movement)
```

---

### 8.5 How BMAD and the eos packs fit together

BMAD answers *"what do we do next, and who does it?"* The eos packs answer *"what does good look like, and how do we prove it?"* They connect through `_bmad/custom/*.toml` `persistent_facts` ([Section 6.3](#63-making-the-dev-agent-follow-the-standards-bmad-customisation)):

| BMAD step (skill) | Persona | eos packs injected | Output location |
|---|---|---|---|
| `bmad-brainstorming`, `bmad-forge-idea` | Analyst (Mary) | ideation | `docs/ideas/` or `_bmad-output/` |
| `bmad-product-brief`, `bmad-prfaq`, `bmad-deep-recon` | Analyst | discovery | `_bmad-output/planning-artifacts/` |
| `bmad-prd`, `bmad-spec`, `bmad-create-epics-and-stories` | PM (John) | requirements | same |
| `bmad-ux` | UX (Sally) | ux-design | same |
| `bmad-architecture` | Architect (Winston) | architecture, data-modeling, api-design | same + `docs/adr/` |
| `bmad-sprint-planning`, `bmad-build`, `bmad-build-auto` | Dev (Amelia) | testing-qa + all stack packs (the others attach by path) | code + tests |
| `bmad-code-review`, `bmad-review` | n/a | code-review, security | PR comments |
| `bmad-retrospective` | n/a | then **eos-retro** | `docs/ai/lessons.md`, pack/check PRs |
| `bmad-project-context` | n/a | writes its `<!-- bmad:context -->` block inside the team-owned part of `AGENTS.md` | `AGENTS.md` |

`eos init --bmad` runs the headless installer, which was verified on 9 Oct 2026 [Tested]:
`npx -y bmad-method@6.12.1 install --directory . --modules bmm --tools cursor,cline --yes`.
On a scratch project this produced 29 skills each in `.agents/skills` and `.cline/skills`, plus `_bmad/` and `_bmad-output/`. eos then seeds the five persona overrides. A project without BMAD loses nothing. The phase packs stand on their own as skills and rules.

---

## 9. Token and cost efficiency

### 9.1 Where the money actually goes

Agent cost is roughly *(tokens in + tokens out) × price × number of turns*. The biggest levers, in order [Recommendation]:

1. **Number of turns** — vague tasks cause long, wandering sessions. Fix with specs and story-sized tasks.
2. **Input tokens per turn** — always-on rules, big files, huge tool outputs, long chat history. Fix with context engineering.
3. **Price per token** — fix with model routing and caching.

Cursor's docs say it directly: "your model selection affects how quickly your included usage is consumed" ([Cursor pricing](https://cursor.com/docs/models-and-pricing)).

### 9.2 Model routing by role

I deliberately do **not** name a single "best model": rankings change monthly and Cursor's model list on 9 Oct 2026 already includes several generations from OpenAI, Anthropic, Google, SpaceXAI/Cursor, Moonshot, Z.ai and Meta. Define *tiers*, then map today's models to tiers in one file and revisit monthly. Since v0.3.0 that file is `personal/models.toml` in engineering-os (tiers `premium`, `strong`, `cheap`; a task → tier map; budget caps), and `eos models` reads it: `eos models implement` prints the tier and models for a task, `eos models debug --failures 2` escalates one tier, `eos models --check` verifies every model id against the live OpenRouter catalogue and prints today's price, and `eos models --usage` compares your key's spend with the caps [Tested].

| Tier | Used for | Where to run it | How to pick the model |
|------|----------|-----------------|-----------------------|
| **T1 — Premium reasoning** | PRD validation, architecture, ADRs, threat modelling, *thorough* code review of money/security code, hard debugging | Cursor "Other Models" pool, or OpenRouter in Cline | The strongest reasoning model you can afford; use sparingly and in fresh, focused chats |
| **T2 — Daily driver** | `bmad-build` on normal stories, interactive coding | Cursor "Cursor Models" pool (on 9 Oct 2026: Grok 4.7/4.6/4.5 and Composer 2.5, which Cursor says get "significantly more included usage") [Verified] | Fast, good tool use, good at following AGENTS.md |
| **T3 — Cheap bulk** | Test scaffolding from EARS criteria, docstrings, i18n strings, mechanical refactors under a strong test net, changelog drafts, summarising logs | Cline + OpenRouter | Cheapest model that passes your mini eval (9.7) |
| **T4 — Free / experimental** | Throwaway experiments | OpenRouter `:free` variants | Only for non-sensitive code; free variants are rate-limited (below) |

The shipped example ids (all present in `https://openrouter.ai/api/v1/models` on 9 Oct 2026, with that day's list prices per million input/output tokens) [Verified]:

| Tier | Tasks | Example ids | USD per 1M in / out |
|---|---|---|---|
| premium | plan, architecture, review, security, hard debugging | `anthropic/claude-opus-5.5`, `openai/gpt-6-astra` | 4 / 20; 10 / 50 |
| strong | implement, test, refactor, normal debugging | `anthropic/claude-sonnet-5.5`, `openai/gpt-6.1-sol` | 2 / 10; 2 / 10 |
| cheap | docs, bulk, summaries, commit messages | `anthropic/claude-haiku-5.5`, `deepseek/deepseek-v4.1-flash`, `openai/gpt-6-luna` | 0.10 / 0.50; 0.30 / 1.20; 0.10 / 0.50 |

These are examples, not a ranking: the tier comes from each provider's own positioning on its model page, and prices change. Run `eos models --check` rather than trusting this table. In Cline, turn on "Use different models for Plan and Act" and put a premium model on Plan and a strong one on Act ([Cline Plan & Act](https://docs.cline.bot/core-workflows/plan-and-act)) [Verified].

**Rules of thumb [Recommendation]:**
- **Optimise for outcome per task, not price per token.** A premium model that fixes a hard bug in one pass is cheaper than three cheap passes plus your review time. Spend premium on planning and review; that is where mistakes are cheapest to catch.
- **Escalate after two failed attempts** at the same problem (the core rules now say so), instead of grinding on a weaker model.
- The **reviewer should differ from the author** (different model family when possible). Same-model review tends to share the same blind spots.
- **Never put money/auth/crypto changes on T3/T4.**
- Prefer **non-"fast" variants** unless latency matters; Cursor lists fast modes at roughly 2× price for several models ([Cursor pricing](https://cursor.com/docs/models-and-pricing)).
- **Long context is not free.** Several models bill long-context requests at a multiple of standard rates (Cursor's table shows 2× above 256k input tokens for some). Avoid "attach the whole repo".

### 9.3 OpenRouter: budgets are a setting, not a design constraint

[Verified] from [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits) and [Spend controls](https://openrouter.ai/docs/guides/best-practices/spend-controls):

- **Per-key credit limit** with `limit_reset` = daily, weekly or monthly. Create **one key per tool/purpose** (e.g. `cline-dev`, `ci-review-bot`) with its own cap, so a runaway agent loop cannot drain the account.
- Check remaining budget any time: `GET https://openrouter.ai/api/v1/key` (fields `limit_remaining`, `usage_daily`, …).
- **Free model limits:** with less than 10 credits ever purchased: 20 requests/minute and **50 requests/day** on `:free` models; with at least 10 credits purchased: **1000 requests/day**. With $5 in credits you are in the 50/day tier — buying $10 total raises it.
- Workspace **guardrails** can restrict allowed models/providers and enforce data-policy settings (e.g. zero-data-retention providers) — useful when client code is confidential.
- A negative balance can cause `402` errors even on free models.

**Prompt caching** (re-using an already processed prompt prefix at a discount): OpenRouter supports provider caching; for Anthropic models you add `cache_control` (5-minute default TTL, optional 1 hour); Gemini 2.5+ caches implicitly ([OpenRouter prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)). Practical effect for you: **keep the stable part of the prompt stable** — the same AGENTS.md and rules at the top, the changing part at the bottom — and avoid editing always-on rules mid-session, because that invalidates the cache.

**How eos treats Cline spend since v0.3.0** [Recommendation, from the limits above and the measurements in [Section 4.2](#42-the-token-budget)]:
- The budget is yours to set, not something the system is designed around. Put the cap where it is enforced: an OpenRouter **per-key limit with a daily, weekly or monthly reset** on the key Cline uses. Mirror the numbers in `personal/models.toml` `[budget]` (0 = no cap) so `eos models --usage` warns at 80% (`warn_at`).
- Every step of Cline's agent loop is a separate request that re-sends the system prompt, rules, history and the schemas of every enabled MCP server. Standing context still costs tokens per step, so eos keeps the always-on files small. But it no longer removes useful tools to save money: GitHub is on in the default `build` profile (≈3,200 tokens per request), and you switch profiles per task (`eos mcp use review --tools cline`), or flip one server in Cline's MCP panel mid-task.
- Use Cline for whatever it does best for you (Plan/Act with different models, OpenRouter's model choice), not only for "small tasks". Prefer a fresh task per story: history is re-sent on every step.
- If you stay on the free tier for experiments, buying 10 credits in total moves `:free` models from 50 to 1,000 requests a day (limits above).

### 9.4 Cursor usage tips (Pro+)

[Recommendation, based on Cursor's documented pricing model]
1. Default to a model from the **Cursor Models pool** for implementation; switch to an "Other Models" premium model only for T1 jobs.
2. **New chat per story** (BMAD says the same: "Start a fresh chat"). Long chats re-send history every turn.
3. Watch the **usage dashboard** weekly; Cursor shows both pools there.
4. Use `@file` and `@folder` precisely instead of letting the agent search everything; keep `.cursorignore` up to date (build output, lockfiles, generated clients, fixtures, `_bmad-output/archive/`).
5. Keep **always-apply rules tiny**; make everything else `globs`-scoped or description-triggered (see [Section 4](#4-context-loading-token-budget-and-anti-loop-safeguards)).
6. Use **Plan mode / planning first** when a change touches a schema, a public API, money, auth or infra, or spans several modules: a 2-minute plan prevents a 30-minute wander. Small local changes don't need one.
7. Pro/Pro+/Ultra include access to Cloud Agents and Bugbot per Cursor's docs, but agent runs consume usage; enable them per repo deliberately.

### 9.5 Context engineering techniques

**Context engineering** = deciding exactly what information the model sees at each step.

| Technique | How to apply it here |
|-----------|----------------------|
| Small always-on core | Root `AGENTS.md` ≤ 1,600 tokens, enforced by `eos check` [Heuristic]; only facts the code cannot tell |
| Scoped rules | `.cursor/rules/*.mdc` with `globs`; `.clinerules/*.md` with `paths:` frontmatter; Cline evaluates `paths` against mentioned, open, visible and edited files ([Cline rules](https://docs.cline.bot/customization/cline-rules)) |
| Progressive disclosure | `AGENTS.md` *points* to `.eos/packs/INDEX.md`, which points to packs, instead of copying them ([Section 4](#4-context-loading-token-budget-and-anti-loop-safeguards)) |
| Repo map | A generated, compact map of modules and public interfaces (`docs/ai/repo-map.md`), regenerated in CI, so agents don't read 40 files to find one function |
| Summarise, don't paste | Paste the failing test name and 20 relevant log lines, not 2,000 lines |
| Compaction | Cline: Auto Compact near the context limit, `/smol` to compress, `/newtask` to hand off a summary ([Cline Auto Compact](https://docs.cline.bot/features/auto-compact)); Cursor: start a fresh chat with the plan file |
| Plan files as hand-off | BMAD Build writes a plan file; the next session reads the plan, not the old chat |
| Keep input to bmad-spec short | BMAD notes a practical ceiling of "a few tens of thousands of tokens, roughly a 40-page document" for `bmad-spec`; condense first ([Choose a Planning Path](https://docs.bmad-method.org/plan/choose-a-planning-path/)) |
| Ignore files | `.cursorignore`, Cline's `.clineignore`, and the guard hook blocking reads of secrets ([Section 6.5](#65-hooks-automatic-checks-inside-the-agent-loop)) |

### 9.6 A tiny cost dashboard

[Recommendation] Once a week, record in `docs/ai/cost-log.md`: Cursor usage per pool (from dashboard), OpenRouter usage per key (`/api/v1/key`), number of stories merged. Cost per merged story is the number to watch; if it rises, look for bloated rules or vague stories first.

### 9.7 A mini eval for choosing cheap models

An **eval** is a repeatable test of an AI system's quality. Keep 5–10 real, small, already-solved stories from your own repos (with their tests) in `evals/agent-tasks/`. When considering a new cheap model, run each task in Cline on a throwaway branch and score: tests pass? lint/types pass? diff size reasonable? any forbidden edits? This takes an hour and is far more reliable than public leaderboards for *your* stack. BMAD also ships a `bmad-eval` skill (in its toolsmith area) for evaluating skills themselves.

---

## 10. MCP strategy

**MCP (Model Context Protocol)** is the standard way agents call external tools (GitHub, Figma, Postman, databases…). Every MCP server you add is **new attack surface and new tokens in the prompt** (tool descriptions are sent to the model).

### 10.1 MCP servers per role

| Role / phase | MCP servers | Access level |
|-------------|-------------|--------------|
| Analyst / PM (research, PRD) | Web search/fetch, docs (e.g. Context7), GitHub (issues read) | Read-only |
| UX | **Figma** (read designs, variables/tokens) | Read-only |
| Architect | GitHub (read), docs, diagram tools | Read-only |
| Developer | GitHub (read code/issues, create branch/PR), **Postman** (collections, read), docs, **Postgres read-only on local/dev DB**, Playwright (browser for E2E debugging) | Write only to *branches*; DB read-only role |
| QA | Playwright, Postman (run collections against preview), Sentry/observability (read) | Read + run against non-prod |
| Ops (later) | Observability (read), cloud provider (read) | Read-only; production writes never via agent |

[Recommendation] Since v0.3.0 eos uses **profiles**: `minimal` (Context7), `build` (default: Context7 + GitHub read-only), `review` (GitHub + Context7), `api` (Postman + GitHub + Context7), `design` (Figma + Context7; + Playwright since v0.7.1), `debug` (read-only local Postgres + Context7, v0.7.1), `debug-ui` (Playwright + Context7) and `off`. `eos mcp use <profile|phase> [--tools cline]` switches them; a phase id works too (`eos mcp use ux-design` → design). In Cline every server whose secrets are set is written to its settings file and the profile sets `"disabled"`, so you can also flip one in Cline's MCP panel ([Cline MCP](https://docs.cline.bot/mcp/mcp-overview)) [Verified, Tested]. Cursor, Claude Code and Codex now keep only tool names in context and load a schema when needed, but Cline sends every enabled server's schemas on every request (measured sizes in [Section 4.2](#42-the-token-budget)).

### 10.2 Least privilege

- **Separate tokens per server**, scoped to the minimum: e.g. a fine-grained GitHub token limited to the repo(s), with *contents: read*, *pull requests: write* — no admin, no workflow write.
- **Database MCP**: connect with a dedicated Postgres role that has `SELECT` on non-sensitive schemas only, against local/dev data — never production, never real customer PII.
- **No secrets in any committed config**: eos renders MCP into user-level configs from a canonical list with variable names only (10.4).
- **Prefer official/vendor servers**, pinned to versions; avoid random community servers for anything that touches credentials.

### 10.3 MCP security [Verified + Recommendation]

The MCP spec's security guidance warns against **token passthrough** (a server forwarding your token downstream) and **confused-deputy** problems, and requires servers to validate tokens issued for themselves ([MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [Security Best Practices](https://modelcontextprotocol.io/docs/2025-03-26/tutorials/security/security_best_practices)). OWASP describes **tool poisoning**: malicious instructions hidden in tool descriptions or results ([OWASP MCP Tool Poisoning](https://github.com/OWASP/www-community/blob/master/pages/attacks/MCP_Tool_Poisoning.md)).

Controls:
1. **Allowlist** servers; review tool descriptions when installing and when they change (pin versions).
2. **`beforeMCPExecution` hook**: the eos guard asks for approval on write-like tools in Cursor. Add a server allowlist if you need stricter control (Cursor's docs recommend treating an unexpected server name as deny).
3. **Treat tool output as untrusted input** (it can contain prompt injections — e.g. a GitHub issue body saying "ignore previous instructions").
4. **Never auto-approve** destructive tools (merge PR, delete branch, write DB).
5. **Audit log** of MCP calls (`afterMCPExecution`).
6. Remove servers you haven't used in a month.

---

### 10.4 Secrets out of git: one canonical MCP list rendered per tool

The requirement "MCP configs with secrets kept out of git" is met by construction [Tested, including a leak test that greps every generated file for the secret value]:

1. **`engineering-os/mcp/servers.json`** is committed. It holds URLs, types, `enabled` flags and `${VAR}` placeholders, and **no values**. The defaults:
   - **GitHub**, read-only repos toolset: `https://api.githubcopilot.com/mcp/x/repos/readonly`;
   - **Context7**: `https://mcp.context7.com/mcp`;
   - **Postman**, minimal toolset: `https://mcp.postman.com/minimal`, with an EU host for data residency (off by default since v0.2.0; on in the `api` profile since v0.3.0);
   - **Figma** (remote, OAuth, so no token is stored): `https://mcp.figma.com/mcp` (on in the `design` profile since v0.3.0);
   - **Playwright** (`@playwright/mcp@0.0.83`), on in the `design` and `debug-ui` profiles (since v0.7.1 also `design`, so the critique loop can screenshot and run axe);
   - **Postgres** (`postgres-mcp` 0.3.0 from crystaldba, hash-locked in `mcp/postgres-mcp.lock.txt`), restricted mode, on in the `api` and `debug` profiles (v0.7.1).

   **Guarded launch (v0.7.1).** Playwright and Postgres are rendered for every tool as `python3 <eos>/bin/eos.py mcp run <name>`. That small launcher reads secrets from the environment or `secrets.env` (so no client config holds a database URL). It refuses a Postgres host outside a local allow-list (localhost, 127.0.0.1, ::1, docker service names, plus `EOS_MCP_PG_ALLOWED_HOSTS`), and forces `default_transaction_read_only=on` and a `statement_timeout` on every session. It pins the browser to localhost origins, headless, with an isolated profile and an output directory. A dedicated read-only role (`mcp/postgres-readonly-role.sql`) is the layer that holds even if the others fail. Details, alternatives considered and measured token costs: [mcp/README.md](../mcp/README.md#guarded-servers-launcher-eos) [Tested].

   Which servers are on comes from the active profile per tool (stored in `~/.config/engineering-os/state.json`). `"enabled": false` on a server removes it from every profile, and an optional per-server `"clients"` list still limits a server to some tools. Since v0.3.0 GitHub has no `clients` limit: Cline gets it whenever the profile includes it.

   Endpoints were checked against [GitHub MCP remote server](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md), [Postman remote MCP](https://learning.postman.com/docs/developer/postman-api/postman-mcp-server/postman-mcp-remote-server/), [Figma MCP](https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/), [Context7](https://github.com/upstash/context7) and [Playwright MCP](https://github.com/microsoft/playwright-mcp) [Verified].
2. **Values** live in `~/.config/engineering-os/secrets.env`. It is created from `secrets.env.example` with mode 600, outside any repo, and is also covered by the global gitignore.
3. **`eos bootstrap` renders** the list for each tool. It merges and never clobbers: servers you added by hand are kept, and eos tracks the ones it manages in `state.json`.

| Tool | Rendered to | Secret reference |
|---|---|---|
| Cursor | `~/.cursor/mcp.json` | `"Authorization": "Bearer ${env:GITHUB_MCP_PAT}"` (Cursor interpolates env vars, per [Cursor MCP](https://cursor.com/docs/mcp)) |
| Codex | managed block in `~/.codex/config.toml` | `bearer_token_env_var = "GITHUB_MCP_PAT"` (a name only) |
| Claude Code | `~/.config/engineering-os/claude-mcp.sh` (you run it once) | `claude mcp add --scope user --transport http github <url> --header 'Authorization: Bearer ${GITHUB_MCP_PAT}'`; Claude Code expands `${VAR}` ([Claude Code MCP](https://code.claude.com/docs/en/mcp)) |
| Cline | `…/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` (and `~/.cline/data/settings/cline_mcp_settings.json` when the Cline CLI is installed) | **literal values**, because Cline's MCP docs show literal header values and document no `${VAR}` expansion ([Cline MCP config](https://docs.cline.bot/mcp/configuring-mcp-servers)). The file is private editor storage, never in a repo, and set to chmod 600 (as is its backup) |

**Caveat:** an editor launched from the Dock or Start menu may not inherit shell variables. Launch it from a terminal, use `launchctl setenv` (macOS) or user environment variables (Windows), or wrap it with a secret manager (e.g. 1Password `op run`). `eos doctor` reports which variables are missing without printing their values.

---

## 11. Reproducibility: the `engineering-os` repo

### 11.1 Repo layout

The repo is dotfiles-style: you fork it once and own it. A tree is in [Section 18.1](#181-the-engineering-os-repo).
- `bin/eos.py` is the whole CLI: about 2,000 lines of standard-library Python ≥3.10, with no dependencies.
- `core/`, `packs/`, `personal/`, `mcp/`, `integrations/bmad/` and `git-hooks/` hold the content.
- `tests/` holds 29 unit tests plus `selftest.sh`, an end-to-end check.
- `versions.toml` holds every pin in one place.
- `VERSION` and `CHANGELOG.md` follow SemVer.

### 11.2 One-command machine bootstrap

```sh
git clone <your-fork-url> ~/engineering-os
~/engineering-os/bootstrap.sh --tools cursor,cline       # Windows: .\bootstrap.ps1 --tools cursor,cline
$EDITOR ~/.config/engineering-os/secrets.env              # fill tokens (file is chmod 600, outside git)
~/engineering-os/bootstrap.sh --tools cursor,cline       # re-run: renders MCP with your values/names
eos doctor
```

`bootstrap.sh` (POSIX sh, shellcheck-clean [Tested]):
1. checks for git and Python ≥3.10;
2. installs **uv** with the official installer if it is missing ([uv docs](https://docs.astral.sh/uv/)), then pre-commit at the pinned version via `uv tool install`;
3. hands over to `eos bootstrap`.

That step is idempotent, and `--dry-run` shows the plan. It does the following:

| Step | Result |
|---|---|
| Launcher | `~/.local/bin/eos` (`eos.cmd` on Windows), pointing at your clone |
| Personal profile | rendered into each selected tool's global instructions as a managed block, so your own text around it is kept |
| Personal skills | `eos-retro`, `eos-handoff`, `eos-new-stack` copied to the global skills folders, each with a `.eos-managed` marker |
| Secrets file | `~/.config/engineering-os/secrets.env` from the example, mode 600; never overwritten |
| MCP | rendered per tool ([Section 10.4](#104-secrets-out-of-git-one-canonical-mcp-list-rendered-per-tool)) |
| Global gitignore | adds `.env`, `.env.*`, `!.env.example`, `*.eos-bak`, … to your `core.excludesFile` |
| `--global-hooks` (opt-in) | sets `core.hooksPath` to `engineering-os/git-hooks`. Every repo then gets **gitleaks on staged files**, and repos with a `.pre-commit-config.yaml` get their hooks run even if nobody ran `pre-commit install`. Opt out per repo with `git config eos.hooks false` [Tested] |
| `--install-clis` | Homebrew only (gitleaks, shellcheck, actionlint, gh, node, pnpm). Elsewhere it prints the commands from `docs/bootstrap.md` |

**OS notes** [Recommendation]:
- **Linux and macOS** are first-class.
- **Windows** has `bootstrap.ps1`, which uses winget hints and `irm https://astral.sh/uv/install.ps1 | iex`. Everything works there except Cline hooks, which are macOS/Linux only per Cline's docs. Use WSL2 if you rely on them.
- The secrets file on Windows should be restricted with NTFS permissions, because chmod does nothing there.

### 11.3 Project init

```sh
cd my-project && eos init            # or: eos init --stacks python:services/api,nextjs:web --tools cursor,claude --bmad
                                     # (v0.3.0: init runs `pre-commit install` itself when pre-commit is on PATH)
git add -A && git commit -m "chore: add engineering-os"
eos doctor                           # what is left, with the fix command on each line
```

`init`:
- detects stacks;
- copies `.eos/` (packs, CLI, config, protected paths);
- writes or merges `AGENTS.md`. An existing hand-written file keeps its content: eos inserts its blocks after the title [Tested];
- generates the adapters;
- merges hook configs, keeping your entries [Tested];
- seeds `memory/`, `docs/adr/`, `docs/ai/lessons.md`, `.github/renovate.json`, and (v0.3.0) the PR template and story/bug issue forms;
- writes `.pre-commit-config.yaml` (the base plus stack fragments) and the CI workflows (`eos-core.yml` plus one `ci-<stack>.yml` per stack, with path filters);
- appends to `.gitignore`.

It warns about missing `package.json` scripts that the TypeScript pack expects (`lint`, `typecheck`, `test`, `build`). Every file has an ownership policy:

| Policy | Files | On `update` |
|---|---|---|
| **managed** | `.eos/**`, adapters, pre-commit config, CI | replaced if unchanged since the last write (hash in `.eos/manifest.json`); otherwise writes `<file>.eos-new` and reports a CONFLICT |
| **blocks** | `AGENTS.md` eos blocks, global profile blocks | only the content between the markers is replaced |
| **merge** | `.cursor/hooks.json`, `.claude/settings.json` | only entries that call `.eos/bin/eos.py` are replaced |
| **seed** | `memory/*`, ADR template, lessons, renovate, PR/issue templates, `.eos/config.json`, `.eos/protected.txt`, everything from `eos scaffold` | written once, never again |
| **append** | `.gitignore` | adds missing lines only |

### 11.4 Updates and versioning

- **eos itself:** SemVer in `VERSION`. A pack wording fix is a patch. A new pack, rule or check is a minor. A changed layout, command or frontmatter schema is a major. Tag each release (`v0.1.0`) and record it in `CHANGELOG.md`.
- **Upgrading a project:** `git pull` in your clone, then `eos update` in the project. Review `*.eos-new` files and merge them by hand, run `eos check`, and commit `chore: update engineering-os to vX.Y.Z`. `--strict` makes conflicts fail, which is useful in scripted upgrades.
- **Editing standards for one project:** edit `.eos/packs/...`, then run `python .eos/bin/eos.py sync`. This needs no clone, so teammates can do it.
- **Pins:** `versions.toml` holds the defaults for new projects. Renovate (seeded) keeps project pins fresh, including pre-commit hook revs and Actions digests via `helpers:pinGitHubActionDigests`. eos-owned `.eos/**` is excluded from Renovate.
- **Leaving:** `eos uninstall` (v0.3.0) removes generated files you did not edit, strips eos hook entries and `AGENTS.md` blocks, and keeps memory, ADRs, docs, templates and scaffolds. `--force` also removes generated files you edited.
- **New config keys** arrive only in new projects, because `.eos/config.json` is seeded once. To opt an existing project into v0.3.0's push policy, add `"push_policy": "feature-branches"` to its `.eos/config.json`.
- **BMAD:** bump the pin in `versions.toml`, then on a branch re-run `npx bmad-method@<new> install …`, run `eos check`, and commit. Your `_bmad/custom/*.toml` overrides survive.
- **Testing eos itself:** `tests/selftest.sh` runs the following [Tested: all green on 9 Oct 2026]:
  - unit tests, ruff and shellcheck;
  - pack budgets;
  - `init` into three fixtures (a FastAPI + Next.js monorepo, Flask, and Go, which is reported as unsupported);
  - `eos check`, `pre-commit validate-config` and `actionlint` on the generated files;
  - the global hook dispatcher: a good commit passes, a fake token is blocked, a bad commit message is blocked.

  `--full` also runs every generated pre-commit hook on a fresh project. The repo's own `.github/workflows/selftest.yml` runs the unit tests on Linux, macOS and Windows, and the end-to-end selftest on Linux and macOS.

---
## 12. Stack packs: how they work

### 12.1 Anatomy

A stack pack is a folder under `packs/stacks/<id>/` with up to three files:

| File | Purpose |
|---|---|
| `STACK.md` | Frontmatter (detection and commands) plus a body of ≤1,200 tokens: toolchain table, layout, numbered rules, testing, pitfalls |
| `pre-commit.yaml` | A fragment merged into the project's `.pre-commit-config.yaml`: fast hooks at `pre-commit`, slow ones (types, tests) at `pre-push` |
| `ci.yml` | A GitHub Actions job template rendered as `ci-<stack>.yml`, with workflow-level `paths:` filters |

The frontmatter extends the phase-pack format:

```yaml
markers: ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile", "uv.lock"]  # detection
contains: []            # flavour packs: words that must appear in a marker file, e.g. ["fastapi"]
requires: []            # e.g. nextjs requires typescript; python-fastapi requires python
fast_check: "uv run ruff check --fix . && uv run ruff format ."                      # while iterating
full_check: "uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q"  # "done"
ci: python              # which CI template to render ("" = none; flavour packs ride on their parent)
```

`{pm}` in a command is replaced by the detected Node package manager (pnpm, npm, yarn or bun). The commands land in the `AGENTS.md` table that agents must use. So "done" means the same thing in every tool, and the same thing in CI.

### 12.2 Packs shipped in v0.3.0

| Pack | Detects | Adds |
|---|---|---|
| `python` | `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile`, `uv.lock` | uv, ruff, mypy, pytest, import-linter, pip-audit, mutmut; typing, async, money and time rules |
| `python-fastapi` | `python` + "fastapi" in a marker | routers/dependencies/schemas, async rules, OpenAPI export |
| `python-flask` | `python` + "flask" in a marker | app factory, blueprints, APIFlask/flask-smorest for OpenAPI |
| `typescript` | `package.json`, `tsconfig.json` | pnpm, strict `tsc --noEmit`, ESLint or Biome, Vitest, Playwright; a `package.json` scripts contract (`lint`, `typecheck`, `test`, `build`) |
| `nextjs` | `next.config.js/mjs/ts` (+ `typescript`) | Server/Client Component rules, caching, Server Action security, env vars; full check = `build` |
| `_template` | n/a | scaffold for `eos new-stack` |

### 12.3 Adding a stack (e.g. Go, Laravel, Kotlin)

```sh
eos new-stack go --markers go.mod --globs "**/*.go" --title "Go"
# → packs/stacks/go/{STACK.md,pre-commit.yaml,ci.yml} from _template, placeholders filled
```

Then fill it in, using the personal skill `eos-new-stack` as a guide. Every fact must come from that ecosystem's **official docs for the version you use**, linked in the PR. Fill in the toolchain table, `fast_check`/`full_check`, layout, rules (types, validation, errors, money/time, concurrency, config, DB, logging), testing (unit, integration, contract, e2e, mutation tool) and pitfalls. Run `eos budget`, commit to the eos repo, and `eos update` the projects that need it. A Laravel or Go pack is roughly a day of careful work, and every phase pack applies to it unchanged.

### 12.4 Monorepos

Detection records a directory per stack (`python@apps/api`, `nextjs@apps/web`), and commands run in that directory. **Known limitation (still in v0.2.0):** when there are several directories for the same stack (e.g. three Python services), only the first one detected is wired into the hooks and CI. Override with `--stacks python:services/payments`, or extend the CI matrix by hand (see [Section 22](#22-open-decisions)).

---
## 13. Stack pack example A: Python backends (FastAPI and Flask)

This section is the long-form rationale behind the `python`, `python-fastapi` and `python-flask` stack packs. The packs are the short, enforceable version and are what agents load. Treat this section as the worked example of how a senior team chooses a stack's standards; use it as a model when you write packs for Go, Laravel or Kotlin.

### 13.1 Tooling baseline (versions on 9 Oct 2026, from PyPI) [Verified]

| Concern | Tool | Latest seen | Why |
|---------|------|-------------|-----|
| Python | CPython **3.14** | 3.14.8 | Current stable line ([endoflife.date](https://endoflife.date/python)) |
| Env + packages + lockfile + workspaces | **uv** | 0.12.24 | One fast tool for venvs, `uv.lock`, Python versions, workspaces, `uv run` |
| Lint + format | **ruff** | 0.16.10 | Replaces flake8/isort/black/pyupgrade; also has `S` (bandit-derived) rules |
| Types | **mypy** (strict) *or* **pyright** (strict) | mypy 2.4.0 / pyright 1.1.414 | Pick one as the CI gate (open decision); **ty** (Astral) is still beta (0.0.85) — fine as a fast local extra, not as the gate yet ([ty on PyPI](https://pypi.org/project/ty/)) |
| Validation / settings | **pydantic v2** + **pydantic-settings** | 2.14.0 / 2.15.0 | Typed request/response models, typed config from env |
| ORM / SQL | **SQLAlchemy 2.x** (typed `Mapped[...]`), **psycopg 3** or **asyncpg** | 2.1.4 | Mature, async support |
| Migrations | **Alembic** + **squawk** (Postgres migration linter, on generated SQL) | 1.20.0 / 2.68.0 | Safe, reviewable schema changes |
| Architecture boundaries | **import-linter** | 2.15 | Enforces layer rules (domain can't import web, etc.) |
| Tests | **pytest**, **pytest-cov**, **hypothesis**, **testcontainers** (real Postgres), **schemathesis** (OpenAPI fuzzing), **mutmut** (mutation) | 9.1.1 / 7.1.0 / 6.168.5 / 4.15.0 / 4.30.0 / 3.8.0 | Fast unit tests, real DB integration tests, contract fuzzing, test-strength proof |
| Security | **bandit** or ruff `S` rules, **semgrep**, **pip-audit**, **gitleaks** | 1.9.4 / 1.180.0 / 2.10.1 | SAST, dependency CVEs, secrets |
| Observability | **OpenTelemetry** SDK + instrumentations (FastAPI, Flask, SQLAlchemy, httpx), **structlog** | 1.45.1 / 26.1.0 | Traces, metrics, structured logs with trace IDs |
| Frameworks | **FastAPI** 0.143.0, **Flask** 3.1.3 (+ **APIFlask** 3.1.2 or **flask-smorest** 0.47.0 for OpenAPI) | | |

Note: uv now also exposes `uv format` and `uv check` (Turborepo's docs describe `uv check` running a bundled ty) — convenient, but keep ruff/mypy (or pyright) as the explicit CI gates so the rules are visible in config ([Turborepo Python guide](https://turborepo.dev/docs/guides/tools/python)).

### 13.2 Service layout (hexagonal / "ports and adapters", kept simple)

```
apps/api-payments/                # FastAPI service
  pyproject.toml
  src/payments/
    domain/          # pure business logic: entities, value objects (Money), domain services. No I/O, no framework.
    application/     # use cases (CreateTransfer), ports (interfaces), unit-of-work
    infrastructure/  # SQLAlchemy repos, outbox relay, HTTP clients (MoMo/Orange Money adapters), settings
    api/             # FastAPI routers, request/response schemas, dependencies, error mapping
    main.py          # app factory, lifespan, OTel setup
  migrations/        # Alembic
  tests/
    unit/  integration/  contract/  property/
```

**import-linter contract** (enforced in CI and pre-commit):

```toml
# apps/api-payments/pyproject.toml (excerpt)
[tool.importlinter]
root_package = "payments"

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = [
  "payments.api",
  "payments.infrastructure",
  "payments.application",
  "payments.domain",
]

[[tool.importlinter.contracts]]
name = "Domain is framework-free"
type = "forbidden"
source_modules = ["payments.domain"]
forbidden_modules = ["fastapi", "flask", "sqlalchemy", "httpx", "pydantic_settings"]
```

Why this matters with AI agents: agents take the shortest path (e.g. importing the DB session inside a domain function). A machine-checked boundary turns that into an immediate, explainable failure instead of slow architectural decay.

### 13.3 Strictness configuration (excerpt)

```toml
[tool.ruff]
target-version = "py314"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E","F","W","I","N","UP","B","A","C4","DTZ","T20","SIM","RET","PTH","ERA","PL","RUF","S","ASYNC","FAST","TRY","PERF","ANN"]
ignore = ["ANN401"]            # allow Any only where justified with a comment
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004", "ANN"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
warn_unreachable = true
disallow_any_explicit = false

[tool.pytest.ini_options]
addopts = "-q --strict-markers --strict-config"
markers = ["integration: needs Postgres (testcontainers)", "slow"]
xfail_strict = true

[tool.coverage.run]
branch = true
source = ["payments"]
[tool.coverage.report]
fail_under = 85                  # floor; CI also checks diff coverage does not drop
skip_covered = true
```

*(Check the ruff rule codes against your ruff version — `FAST` (FastAPI) and `ASYNC` rule families exist in recent ruff; drop any your version rejects.)*

### 13.4 FastAPI vs Flask — when to use which

| Use **FastAPI** for | Use **Flask** for |
|---|---|
| New JSON APIs, async I/O-heavy services (calling mobile-money/bank APIs, webhooks), OpenAPI-first contracts | Existing Flask code, server-rendered admin tools, simple sync services, teams already fluent in Flask extensions |
| Native Pydantic v2 request/response models and automatic OpenAPI | Add OpenAPI via **APIFlask** or **flask-smorest** (marshmallow) so the contract-first pipeline still works |

[Recommendation] Write the **domain and application layers framework-free** so the same use case can be served from either framework. Only `api/` differs.

### 13.5 Async patterns (FastAPI)

- **Never block the event loop**: no `requests`, no sync DB driver, no `time.sleep` in `async def`. Use `httpx.AsyncClient`, async SQLAlchemy, `anyio`. If you must call sync code, use a sync `def` endpoint (FastAPI runs it in a threadpool) or `anyio.to_thread.run_sync`.
- **Timeouts on every outbound call** (connect + read), plus retries with exponential backoff and jitter only for *idempotent* operations.
- **Lifespan** handler to create/close the HTTP client pool, DB engine and OTel providers.
- **One DB session per request** via dependency; commit in the use case's unit of work, not in routers.
- **Background work**: FastAPI `BackgroundTasks` is for small fire-and-forget tasks; money-related side effects go through the **outbox** + a worker (below).
- Flask: keep it **sync** with a proper WSGI server (gunicorn); Flask's async views run an event loop per request and do not give FastAPI-style concurrency.

### 13.6 Money-safe patterns (fintech)

1. **Money type**: never `float`. Use integer minor units (store `amount_minor: int` + `currency: str`, with the number of decimals taken from ISO 4217 — XAF has 0, EUR has 2) or `Decimal` with explicit quantisation. Wrap in a `Money` value object in `domain/`.
2. **Idempotency keys** on every POST that creates or moves money. Pattern popularised by Stripe ([Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests)); there is also an IETF draft for an `Idempotency-Key` HTTP header ([draft-ietf-httpapi-idempotency-key-header](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)). Implementation: table `idempotency_keys(key, request_hash, status, response_code, response_body, locked_at, created_at)` with a unique constraint on `(tenant_id, key)`; insert-or-lock at the start of the request, store the response at the end, replay on retry, reject same key + different body.
3. **Transactional outbox**: write the business change *and* an `outbox` row in the same DB transaction; a relay publishes outbox rows to the broker/webhooks and marks them sent. Consumers are idempotent (store processed event IDs). ([microservices.io: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html))
4. **Double-entry ledger** for balances: immutable journal entries that sum to zero; balances are derived/cached, never edited directly.
5. **Concurrency**: `SELECT … FOR UPDATE` on the account row or `SERIALIZABLE` transactions with retry on serialization failures; unique constraints as the last line of defence.
6. **Webhooks from providers** (mobile money, cards): verify signatures, store raw payload, dedupe by provider event ID, process asynchronously, reconcile daily against provider statements.
7. **Audit trail**: who/what/when for every state change of a financial object.

### 13.7 Alembic migrations

- One migration per story that needs it; **never edit a merged migration** (hook-protected).
- **Expand → migrate → contract**: add nullable column / new table → backfill in batches → switch code → drop old column in a later release. Required for zero-downtime and for blue/green or canary deploys.
- Review autogenerate output by hand (it misses some changes, e.g. certain constraint/enum changes).
- CI: `alembic upgrade head` on a fresh DB, `alembic downgrade -1` then `upgrade head` again (round-trip), `alembic check` (no pending model changes), and lint the generated SQL (`alembic upgrade head --sql | squawk`) for locking hazards such as adding a non-concurrent index on a big table.

### 13.8 Contract-first OpenAPI

1. For new endpoints, **write or change the OpenAPI contract first** (in the story), or at least the Pydantic schemas, and get it reviewed.
2. Export the spec in CI (`python -m payments.export_openapi > contracts/payments.openapi.json`) and **fail if the committed file differs** (forces the contract change to be visible in the PR).
3. **Breaking-change check**: `oasdiff breaking` between `main` and the PR spec.
4. **Fuzz/contract test**: `schemathesis run` against the running app in CI (finds 500s, schema violations).
5. **Generate the frontend client** from the same file (Section 14.6).

### 13.9 Observability

- **Structured logging** with `structlog` → JSON to stdout; every line carries `trace_id`, `span_id`, `request_id`, `tenant_id` (never PII, never secrets, never full card/phone numbers — mask them).
- **OpenTelemetry**: SDK + `opentelemetry-instrumentation-fastapi` / `-flask` / `-sqlalchemy` / `-httpx`; export OTLP to a collector. Start with traces + RED metrics (Rate, Errors, Duration) per endpoint; add business metrics (transfers created/failed, provider latency).
- **Health endpoints**: `/livez` (process alive) and `/readyz` (DB and critical dependencies reachable).
- **Error tracking**: an exception tracker (Sentry or similar) with release tags so regressions map to deploys.

---

## 14. Stack pack example B: TypeScript and Next.js frontend

This section is the long-form rationale behind the `typescript` and `nextjs` stack packs. Versions are as of 9 Oct 2026; the packs tell agents to check the *installed* version first.

### 14.1 Tooling baseline (npm registry, 9 Oct 2026) [Verified]

| Concern | Tool | Latest seen | Notes |
|---------|------|-------------|-------|
| Framework | **Next.js** | 16.4.0 (6 Oct 2026) | 16.4 makes Cache Components the recommended model and default in `create-next-app` ([Next.js 16.4](https://nextjs.org/blog/next-16-4)). Next.js 16 removed `next lint` and `next build` no longer lints — run the linter explicitly ([Next.js 16](https://nextjs.org/blog/next-16)). A security update was announced for 14 Oct 2026 ([notice](https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026)) — a good reason to automate patch updates. |
| Language | **TypeScript** | 7.0.2 | 7.0 (Jul 2026) is the native Go compiler; it lacks the stable programmatic API until 7.1, so tools that depend on the TS API may need the TS 6 compatibility package ([TS 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)). Check typescript-eslint/Storybook compatibility before upgrading. |
| Package manager | **pnpm** | 12.10.1 | Workspaces, strict dependency resolution |
| Lint/format option A | **ESLint** 10.12 + typescript-eslint + **Prettier** 3.9 | | Largest plugin ecosystem (a11y, React hooks, boundaries) |
| Lint/format option B | **Biome** 2.5.15 | | One fast tool for lint + format; fewer plugins |
| Boundaries | **dependency-cruiser** 18.5 or **eslint-plugin-boundaries** 7.2; **knip** 6.41 for dead code/unused deps | | |
| Unit/component tests | **Vitest** 5.0 + Testing Library | | |
| E2E | **Playwright** 1.64 + **@axe-core/playwright** 4.13 | | Accessibility checks inside E2E |
| Components | **Storybook** 10.6 (+ a11y addon, interaction tests) | | Visual catalogue; agents can be told "build it in Storybook first" |
| Performance | **Lighthouse CI** (`@lhci/cli` 0.15.1 — last release June 2025, so check it still fits your Next version), bundle-size budgets | | |
| Design tokens | **Style Dictionary** 5.6 | | Transforms token JSON → CSS variables / Tailwind theme |
| API client | **orval** 8.41 or **@hey-api/openapi-ts** 0.99 or **openapi-typescript** 7.13 + `openapi-fetch` | | Generated from the backend OpenAPI |

### 14.2 Strict TypeScript

```jsonc
// tsconfig.json (excerpt)
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "useUnknownInCatchVariables": true,
    "verbatimModuleSyntax": true,
    "noEmit": true
  }
}
```

Ban `any` and non-null assertions (`!`) in lint config; require `// reason:` comments on every disable directive (checked in CI, 6.6).

### 14.3 App structure and boundaries

```
apps/web/src/
  app/                 # routes only (thin): layouts, pages, route handlers
  features/<feature>/  # UI + hooks + server actions for one feature; no cross-feature imports
  components/ui/       # design-system primitives (from tokens), no business logic
  lib/api/             # GENERATED client (do not edit) + thin wrappers
  lib/                 # framework-agnostic utilities
```

Rules (dependency-cruiser): `features/A` cannot import `features/B`; `components/ui` cannot import `features`; nothing imports from `lib/api/generated` except `lib/api`; server-only modules (`import "server-only"`) never imported by client components.

### 14.4 Testing and accessibility

- **Vitest** for logic and components; **Playwright** for critical journeys (sign-up, KYC, transfer, failure states), run against preview deployments in CI.
- **axe** in every Playwright journey: fail on serious/critical violations.
- **Storybook** stories for each `components/ui` primitive with a11y addon enabled.
- Target **WCAG 2.2 AA**; test with keyboard only at least once per release.
- **Bilingual UI (FR/EN)**: message catalogues in files, never hard-coded strings; a test that fails on missing keys in either language.

### 14.5 Performance budgets

- Track **Core Web Vitals**: LCP (loading), INP (responsiveness), CLS (visual stability).
- Lighthouse CI with assertions on the main pages (e.g. performance score floor, total JS weight budget) [Heuristic: start from your current numbers and forbid regressions rather than inventing targets].
- Bundle budget per route; fail the PR if a route's JS grows more than an agreed amount.
- Test on **slow 3G/4G and a mid-range Android profile** — very relevant for users in Cameroon and the wider region, where many users are on mobile data.

### 14.6 Generated API client (contract-first, end to end)

```
backend Pydantic models ──► contracts/payments.openapi.json (committed, diffed in CI)
                                   │
                                   ├──► oasdiff breaking-change check
                                   ├──► schemathesis contract fuzzing
                                   └──► orval / hey-api ──► apps/web/src/lib/api/generated (typed client + zod schemas)
```

CI regenerates the client and fails if `git diff --exit-code` shows a difference, so the frontend can never silently drift from the backend. Agents are told in AGENTS.md: *"Never hand-edit `lib/api/generated`; change the backend schema and regenerate."*

### 14.7 Design tokens from Figma

1. Designers define colours, spacing, typography as **Figma Variables**.
2. Export them as JSON (via the Figma MCP, a tokens plugin such as Tokens Studio, or Figma's REST API — check which your Figma plan allows) into `packages/design-tokens/tokens/*.json`, ideally in the W3C Design Tokens Community Group format.
3. **Style Dictionary** builds CSS variables and the Tailwind theme (`packages/design-tokens/dist`).
4. Components use tokens only; a lint rule forbids raw hex colours and pixel values in `components/ui`.
5. Agents with the Figma MCP (read-only) can compare a component against the frame, but tokens flow through the pipeline, not through agent copy-paste.

---

## 15. Monorepo and automation

### 15.1 Monorepo tool choice

| Option | What you get | Python support | When to choose |
|--------|-------------|----------------|----------------|
| **Plain workspaces** (pnpm workspaces + uv workspace) + `Makefile`/`justfile` + CI path filters | Simple, nothing new to learn | Native (uv) | **Start here** [Recommendation]. Enough for 1–5 apps |
| **Turborepo** 2.11 | Task graph, local + remote caching, `--affected` | **Experimental** uv-workspace support behind `futureFlags.experimentalPythonWorkspaces` — Turborepo says to use it in side projects/POCs "where stability is not essential" ([Turborepo Python](https://turborepo.dev/docs/guides/tools/python)) | When CI time hurts and the repo is mostly JS/TS |
| **Nx** 23.3 | Task graph, caching, affected, generators, module-boundary rules, big plugin ecosystem | Via community uv plugins (e.g. `@mgwilt/nx-uv`) | Larger polyglot repos, multiple teams, you want generators and enforced boundaries |

### 15.2 Commit conventions and release

- **Conventional Commits** (`feat(api): add idempotency keys`, `fix(web): …`, `feat!:` for breaking) enforced in the `commit-msg` hook by **conventional-pre-commit** (v4.4.0, part of the eos base; no Node needed). JS-only teams may prefer **commitlint** (21.2).
- **Release tooling** (open decision):
  - **release-please** (17.11; action v5) opens a "release PR" with changelog and version bumps that you merge — friendlier to monorepos with several packages and to human review. [Recommendation for you]
  - **semantic-release** (25.0) releases automatically on every merge to main — great for libraries, less control.
- **Squash merge** with the PR title as the conventional commit.

### 15.3 Local quality gates: pre-commit (one hook manager)

[Recommendation] In a polyglot repo, use the **pre-commit** framework (4.6) as the *only* Git hook manager; it runs Python and JS tools alike. Husky (9.1) + lint-staged (17.6) is the JS-world equivalent; using both creates two hook systems fighting over `.git/hooks`. If you prefer Husky, call `pre-commit` from it, not the other way round.

Three speeds:
| Stage | Runs | Target time [Heuristic] |
|-------|------|-------------|
| `pre-commit` (on staged files) | format, lint, secrets scan, file hygiene, `eos check` (context budgets + adapter drift) | < 10 s |
| `pre-push` | type checks, import-linter, dependency-cruiser, unit tests of changed packages | < 2 min |
| CI | everything, including integration, contract, E2E, security, mutation (scheduled) | < 15 min on PRs |

Agents run the same commands, the stack `fast_check` / `full_check` listed in `AGENTS.md` (a Makefile may wrap them), so "works on the agent's machine" equals "passes CI". The eos stop hook runs the pre-commit stage automatically when an agent claims it is done.

The generated base config is in [Section 19.5](#195-pre-commit-base-corepre-commitbaseyaml).

### 15.4 CI/CD quality gates (GitHub Actions)

| Gate | Tool | Blocks merge? |
|------|------|---------------|
| Changed-paths detection | `dorny/paths-filter` v4 | — (routes jobs) |
| Format/lint | ruff, ESLint/Biome, Prettier | Yes |
| Types | mypy/pyright strict, `tsc --noEmit` | Yes |
| Architecture | import-linter, dependency-cruiser | Yes |
| Unit + integration tests | pytest (+ testcontainers Postgres), Vitest; diff coverage must not drop | Yes |
| Test-integrity check | `eos test-integrity` (6.6): skips, removed asserts, threshold changes | Yes (or requires human label) |
| Contract | OpenAPI export diff, `oasdiff breaking`, schemathesis, regenerated client diff | Yes |
| Migrations | upgrade/downgrade round-trip, `alembic check`, squawk | Yes |
| Security | gitleaks, semgrep, CodeQL, pip-audit, `pnpm audit` | Yes on high/critical |
| E2E + a11y | Playwright + axe on preview environment | Yes on critical journeys |
| Performance | Lighthouse CI, bundle budgets | Warn first, block later |
| AI review | Bugbot or CodeRabbit | Advisory; human resolves |
| Quality platform (optional) | SonarQube Cloud (formerly SonarCloud) quality gate | Optional |
| Build & supply chain (main) | container build, **SBOM** (Syft/`anchore/sbom-action`), **Trivy** image scan, **build provenance attestation** (`actions/attest-build-provenance`, Sigstore-backed) | Yes |

**Supply chain terms:** an **SBOM** (Software Bill of Materials) lists every component in your build. **SLSA** (Supply-chain Levels for Software Artifacts, [slsa.dev](https://slsa.dev/spec/v1.1/)) defines levels of build integrity. **Sigstore** provides keyless signing; GitHub's artifact attestations use it and GitHub documents that they provide **SLSA v1 Build Level 2**, and **Level 3** when the build runs in a reusable workflow the caller cannot modify ([GitHub: artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations), [reaching Build L3](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/increase-security-rating)).

**Hardening the pipeline itself:** pin third-party actions to a commit SHA (Renovate can keep SHAs updated), set `permissions:` to read-only by default per workflow, use OIDC to cloud providers instead of long-lived keys, protect `main` (required checks, required review, no force-push), and use GitHub Environments with required reviewers for production.

eos generates the core and per-stack workflows ([Section 19.6](#196-core-ci-githubworkflowseos-coreyml)); a fuller product pipeline is in [Section 19.12](#1912-full-product-ci-example-extends-the-eos-workflows).

### 15.5 Dependency updates: Renovate

Renovate (44.x) opens PRs for dependency and GitHub Action updates. Configure: group minor/patch per ecosystem, auto-merge patch updates **only** when CI is green and the package is not on a sensitive list, a weekly schedule, `pinDigests` for actions, and the dependency dashboard issue. eos seeds a starting config ([Section 19.7](#197-renovate-seed-githubrenovatejson)).

### 15.6 Preview environments

- **Frontend**: per-PR previews (e.g. Vercel or Netlify preview deployments, or a container per PR).
- **Backend**: an ephemeral environment per PR (container platform or a Kubernetes namespace) with a **throwaway database** seeded from fixtures — never a copy of production data. Some managed Postgres providers support database branching, which makes this cheaper; check your provider.
- E2E tests and the PR bot comment the preview URL; previews auto-delete on merge/close.

### 15.7 Secrets

- **gitleaks** in pre-commit and CI (the `gitleaks-action` needs a free licence key for *organization* repos, not personal ones — [README](https://github.com/gitleaks/gitleaks-action)); enable GitHub **push protection / secret scanning** where available.
- Secrets in a manager (cloud secret manager, Doppler, 1Password, Vault…), injected at runtime; `.env.example` committed, `.env` never.
- The eos guard blocks agents from reading `.env*` and key files (6.5). Rotate any key that ever appeared in an agent chat.

---

## 16. Production-scale readiness

### 16.1 How big-company practices translate for a small team

| Practice | Origin / reference | Small-team version |
|----------|-------------------|--------------------|
| SLOs and error budgets | Google SRE ([SRE book: Embracing Risk](https://sre.google/sre-book/embracing-risk/), [SRE workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)) | 2–3 SLOs per user-facing service (availability, latency of key endpoints, "transfer completes within X"); when the budget is burnt, freeze features and fix reliability |
| Idempotent APIs | Stripe | Idempotency keys on all money-moving POSTs (13.6) |
| Chaos engineering | Netflix ([Chaos Monkey](https://netflix.github.io/chaosmonkey/)) | Quarterly "game day" in staging: kill the DB connection, slow the mobile-money provider, expire a certificate; verify alerts + runbooks. Tools: Toxiproxy-style fault proxies, Chaos Mesh (2.8) if on Kubernetes |
| Progressive delivery (canary, blue/green) | Google, Meta, Netflix | Canary: 5% → 25% → 100% with automatic rollback on SLO burn, or blue/green with instant switch-back. Requires backward-compatible migrations (expand/contract) |
| Feature flags | Meta, everyone | Every risky feature behind a flag (OpenFeature SDK + a provider such as Unleash 8.x, flagd, or a SaaS); flags have owners and expiry dates |
| Blameless postmortems | Google SRE | Template in `docs/postmortems/`; action items become tickets; lessons feed `eos-retro` |
| Code review culture | Google | Small PRs, required review, review checklists (BUGBOT.md / CodeRabbit path instructions) |
| DORA metrics | DORA ([metrics guide](https://dora.dev/guides/dora-metrics)) | Track the five: change lead time, deployment frequency, failed deployment recovery time, change fail rate, deployment rework rate — from GitHub + deploy logs, monthly |

### 16.2 Load testing with k6

**k6** (Grafana, v2.3 on 21 Sep 2026) scripts are JavaScript; run smoke tests on every deploy to staging and full load/stress/soak tests before big launches. Encode SLOs as k6 **thresholds** so the test fails automatically:

```javascript
// load/transfers.k6.js
import http from 'k6/http';
import { check } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export const options = {
  scenarios: {
    ramp: { executor: 'ramping-arrival-rate', startRate: 10, timeUnit: '1s',
            preAllocatedVUs: 50, stages: [{ target: 100, duration: '5m' }, { target: 100, duration: '10m' }] },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],                 // align with your SLO
    'http_req_duration{endpoint:create_transfer}': ['p(95)<400'],
  },
};

export default function () {
  const res = http.post(`${__ENV.BASE_URL}/v1/transfers`,
    JSON.stringify({ amount_minor: 5000, currency: 'XAF', to: 'acct_test_1' }),
    { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': uuidv4() },
      tags: { endpoint: 'create_transfer' } });
  check(res, { 'created': (r) => r.status === 201 });
}
```

(The numbers are placeholders: set them from your SLOs, not from this document. Verify the jslib version URL when you write the script.)

### 16.3 Runbooks and incidents

Every alert links to a runbook in `docs/runbooks/<alert>.md`: symptoms, dashboards, likely causes, safe mitigations (flag off, roll back, scale), escalation, and "what NOT to do" (e.g. never replay provider webhooks without dedupe). Runbooks are excellent agent context too: an agent with read-only observability MCP can follow a runbook to *diagnose*, while a human executes mitigations.

### 16.4 Production checklist per service (minimum)

- [ ] SLOs defined, dashboards and burn-rate alerts exist
- [ ] `/livez` and `/readyz`; graceful shutdown; timeouts and retries configured
- [ ] Structured logs with trace IDs; PII masking tested
- [ ] Idempotency + outbox for all money flows; daily reconciliation job
- [ ] Migrations expand/contract; backups + **tested restore** (restore drill quarterly)
- [ ] Feature flags for risky features; rollback procedure written and tried once
- [ ] k6 smoke test in the deploy pipeline
- [ ] Rate limiting and abuse protection on public endpoints
- [ ] Threat model (STRIDE-lite) reviewed by a human for auth and payments
- [ ] Runbooks for top 5 alerts; on-call/escalation contact list

---

## 17. Phased rollout plan

Rule: **every week ships product code.** Setup work is capped at roughly 30–40% of your time in weeks 1–4, and about 10% afterwards [Heuristic]. Because `engineering-os` already exists, phases 0 and 4 shrink from days to hours. The time goes into *adopting* the standards, not building tooling.

| Phase | When | Do | Done when |
|---|---|---|---|
| **0. Machine + repo** | Day 1 (≈2 h) | Fork `engineering-os`. Write your preferences in `personal/PROFILE.user.md` (git-ignored; the committed `PROFILE.md` is a generic template). Run `./bootstrap.sh --tools cursor,cline` (add `claude,codex` if used). Fill `secrets.env` with **read-only** tokens. Run `eos doctor` and `tests/selftest.sh` | `eos doctor` clean; selftest green on your machine |
| **1. First project** | Day 1–2 | `eos init` in a real repo (a branch). Fill *Project specifics* in `AGENTS.md`. Run `pre-commit install` and `pre-commit run --all-files`; fix or baseline the findings. Turn on branch protection with the `eos-core` checks required | First PR green with eos-core + stack CI; the stop hook observed working once |
| **2. BMAD + first spec** | Week 1–2 | `eos init --bmad` (or the installer by hand) → `bmad-help`; brief → PRD → architecture + first 3 ADRs; first epic → stories with EARS ACs → sprint planning | PRD validated, ADRs merged, first epic sliced |
| **3. Strict gates per stack** | Weeks 2–4 | Turn on what the stack packs list but the repo lacks: strict types, boundary lint, diff coverage, OpenAPI export + breaking-change diff + generated client, migration checks. Use CODEOWNERS for protected paths | All gates blocking; one contract-first endpoint end-to-end |
| **4. Review + cost** | Weeks 3–5 | Pick **one** PR bot; `bmad-code-review` thorough on risky PRs; review eval with 5 seeded-bug PRs; OpenRouter per-key limits; `docs/ai/model-routing.md`; weekly cost log | Seeded bugs mostly caught; cost per story measured |
| **5. Production readiness** | Weeks 5–7 | operations + release packs in practice: OpenTelemetry, SLOs + alerts + runbooks, preview environments, feature flags, Playwright + axe, release-please, SBOM + attestations, k6 smoke | First real deploy via the pipeline with canary or blue/green |
| **6. Extreme mode** | Week 8+ (only when 0–5 are boring) | Mutation testing on critical modules, schemathesis fuzzing, chaos game day, unattended agents (`bmad-build-auto`, Cloud Agents) for well-specified stories, memory MCP, a new stack pack if needed, DORA dashboard | Lead time, change fail rate and cost per story trending the right way |

**Anti-stuck rules:**
1. If a tool takes more than half a day to get working, park it in `docs/ai/parking-lot.md` and move on.
2. Don't add a gate until you have code it would have caught.
3. Run `eos-retro` at the end of every epic. Upstream general fixes to `engineering-os` and tag a release.

---
## 18. Repository trees

### 18.1 The `engineering-os` repo

```
engineering-os/
├── README.md  CHANGELOG.md  VERSION  versions.toml  ruff.toml  .pre-commit-config.yaml  .gitignore
├── bootstrap.sh                      # macOS/Linux/WSL: deps check → uv → pre-commit → eos bootstrap
├── bootstrap.ps1                     # Windows equivalent
├── bin/eos.py                        # the CLI (stdlib only): bootstrap, init, update, sync, check, budget,
│                                     #   detect, doctor, new-stack, test-integrity, guard
├── core/
│   ├── AGENTS.core.md                # always-on rules, stop conditions, loading + memory rules
│   ├── protected.txt  gitignore.txt
│   ├── templates/                    # AGENTS.md, CLAUDE.md, memory/{active-context,progress,handoff}.md,
│   │                                 #   adr/{INDEX.md,0000-template.md}, lessons.md, renovate.json
│   ├── pre-commit/base.yaml          # stack-agnostic hooks (hygiene, gitleaks, conventional commits, eos-check)
│   └── ci/eos-core.yml               # ai-context (eos check + test-integrity) and secrets jobs
├── packs/
│   ├── phases/                       # 18 phase packs (ideation … maintenance)
│   └── stacks/{python,python-fastapi,python-flask,typescript,nextjs,_template}/
│                                     #   STACK.md (+ pre-commit.yaml, ci.yml)
├── personal/PROFILE.md               # L0 memory (≤400 tokens)
├── personal/skills/{eos-retro,eos-handoff,eos-new-stack}/SKILL.md
├── mcp/{servers.json,secrets.env.example,README.md}
├── integrations/bmad/{README.md,custom/bmad-agent-*.toml}
├── git-hooks/{_dispatch,pre-commit,commit-msg,pre-push}   # global hooks (opt-in)
├── docs/{ARCHITECTURE.md,bootstrap.md,SOURCES.md}
├── tests/{test_eos.py,selftest.sh}
└── .github/workflows/selftest.yml
```

### 18.2 A project after `eos init` (FastAPI + Next.js example) [Tested]

```
my-product/
├── AGENTS.md                         # eos blocks (core, stacks table, pack pointer) + team "Project specifics"
├── CLAUDE.md                         # @AGENTS.md (Claude Code)
├── .eos/
│   ├── bin/eos.py                    # vendored CLI (hooks, pre-commit and CI call this)
│   ├── packs/{core.md,phases/*.md,stacks/*.md}   # canonical project copy: edit here, then `eos sync`
│   ├── config.json  protected.txt  manifest.json
│   └── state/                        # gitignored: guard log, loop and stop counters
├── .cursor/{rules/eos-*.mdc,hooks.json}          # 18 glob rules
├── .agents/skills/eos-*/SKILL.md                 # 12 intent skills (Cursor + Codex)
├── .clinerules/{eos-*.md,hooks/PreToolUse}
├── .cline/skills/eos-*/SKILL.md
├── .claude/{rules/eos-*.md,skills/eos-*/,settings.json}
├── memory/{active-context.md,progress.md,handoff.md}
├── docs/adr/{INDEX.md,0000-template.md}  docs/ai/lessons.md
├── .pre-commit-config.yaml           # base + python + typescript fragments
├── .github/
│   ├── renovate.json
│   └── workflows/{eos-core.yml,ci-python.yml,ci-node.yml}
├── apps/api/ (pyproject.toml, uv.lock …)   apps/web/ (package.json, next.config.ts …)
└── _bmad/  _bmad-output/             # only with --bmad
```

### 18.3 Full product monorepo (example target state)

This is the end state for a fintech product built on the Python and Next.js stack packs. eos-generated folders are omitted (see 18.2).

```
my-product/
├── Makefile                          # thin wrapper over the stack commands (check-fast, check, test-int…)
├── pyproject.toml  uv.lock  package.json  pnpm-workspace.yaml  pnpm-lock.yaml  .python-version  .nvmrc
├── release-please-config.json  .release-please-manifest.json
├── .cursor/BUGBOT.md  (or .coderabbit.yaml)  .cursorignore  .clineignore  .editorconfig
├── docs/
│   ├── architecture/                 # C4 diagrams as code, data model, failure modes
│   ├── standards/constitution.md     # non-negotiables (Spec Kit idea), referenced from AGENTS.md
│   ├── ai/                           # model-routing.md, cost-log.md, parking-lot.md, lessons.md
│   ├── runbooks/  postmortems/
├── contracts/payments.openapi.json   # generated + committed
├── apps/
│   ├── api-payments/                 # FastAPI service (layout in 13.2)
│   ├── api-backoffice/               # Flask service (APIFlask/flask-smorest)
│   ├── worker-outbox/                # outbox relay / async jobs
│   └── web/                          # Next.js app
├── packages/
│   ├── py-shared/                    # framework-free domain primitives (Money, ids, errors)
│   ├── design-tokens/                # Figma tokens → Style Dictionary → CSS vars
│   ├── api-client/                   # generated TS client, never hand-edited
│   └── eslint-config/ tsconfig/
├── infra/  load/  evals/  scripts/
└── .github/{CODEOWNERS,pull_request_template.md,workflows/{release.yml,nightly.yml}}
```

---
## 19. Key files

> These are the **actual files** generated by `engineering-os` v0.3.0 on the FastAPI + Next.js fixture from Section 18.2 [Tested]. The repo is the source of truth: when this document and the repo disagree, trust the repo and fix the document.

### 19.1 `AGENTS.md` (generated)

~~~markdown
# AGENTS.md: bp

<!-- eos:core:begin -->
## Working rules
1. Scale the process to the risk. Small, local changes: make them and verify. Write a short plan (goal, files, risks, checks) and wait for approval only when a change touches a schema, a public API contract, money, auth or infra, or spans several modules.
2. Done means the checks pass. Use the fast check while iterating and the full check (table below) before saying done. Report each check in one line (command → pass/fail) and show output only for failures. Say what you did not run.
3. Keep checks honest. Don't delete, skip or loosen tests, asserts, thresholds or lint rules, and don't add ignore comments to get green. Leave CI, hooks, lockfiles and `.eos/` alone unless that is the task. If a test looks wrong, explain why and ask. (Hooks and `eos test-integrity` check this.)
4. Secrets: don't open `.env*` or key files, and refer to env var names only. The guard hook blocks these reads.
5. Changes to money, auth, crypto, PII, migrations or infra need human review: list them in the PR summary.
6. Ask (one question) when requirements, money rules or security behaviour are unclear. For other low-risk gaps, choose the conventional option, state the assumption and continue.
7. Follow existing patterns. For a new dependency, say why and confirm the package exists.

## When stuck
- The same check still fails after 3 real fix attempts: stop, write `memory/handoff.md` (≤30 lines: goal, failing command, what you tried, next step) and ask. The stop hook enforces this.
- The same command gives the same result 3 times: change approach. The loop guard enforces this.
- Two failed attempts at a hard bug or design: say so and suggest a stronger model or a fresh session.
- The diff grows well past the plan, or reaches a path in `.eos/protected.txt`: re-plan.
- A long session gets confused: write the handoff and start a fresh session.

## Context
- Read only what the task needs. For library APIs, check the installed version (lockfile) and the official docs or docs MCP rather than recalling them.
- For multi-step or resumed work, read `memory/handoff.md` if it exists, else `memory/active-context.md`. For decisions, read `docs/adr/INDEX.md`, then only the ADR you need. Read `docs/ai/lessons.md` when stuck or reviewing.

## Memory (only when there is state worth keeping)
- When work stops unfinished, or after a meaningful change, rewrite `memory/active-context.md` (≤40 lines: now / next / blockers / questions) and add one line per finished item to `memory/progress.md` (capped at 200 lines by `eos check`; move older lines to `memory/archive/`).
- For a significant decision, add an ADR plus an INDEX line. Supersede accepted ADRs; don't edit them.
- When a mistake repeats, propose an automated check (preferred) or one line in `docs/ai/lessons.md`.
<!-- eos:core:end -->

<!-- eos:stack:begin -->
## Stacks & checks (run in Dir; "done" = full check green)
| Stack | Dir | Fast check (while iterating) | Full check (before saying done) |
|---|---|---|---|
| nextjs | `apps/web` | (as typescript) | `pnpm run build` |
| python | `apps/api` | `uv run ruff check --fix . && uv run ruff format .` | `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q` |
| python-fastapi | `apps/api` | (as python) | (as python) |
| typescript | `apps/web` | `pnpm run lint` | `pnpm run lint && pnpm run typecheck && pnpm test && pnpm run --if-present build` |
<!-- eos:stack:end -->

<!-- eos:map:begin -->
## Packs (just in time)
In Cursor, Cline and Claude Code, packs attach by file path or load as skills. Other tools: read `.eos/packs/INDEX.md`, then only the one pack the task needs.
<!-- eos:map:end -->

## Project specifics (owned by the team; eos never edits this section)
- **What this is:** <one or two lines>
- **Architecture:** see `docs/architecture/overview.md` and `docs/adr/INDEX.md`
- **Domain words:** <term = meaning; keep it short>
- **Gotchas:** <things a newcomer (or an AI) gets wrong here>
~~~

The *Project specifics* section is where the team writes what the code cannot say: policy, frozen paths, non-default conventions, observed pitfalls and pointers. BMAD's `bmad-project-context` may add its block there. Keep the whole file ≤1,600 tokens (`eos check` enforces this). The per-pack index is generated into `.eos/packs/INDEX.md` instead of living here (see [Section 4.5](#45-the-v020-context-audit-what-was-wasting-tokens-or-reasoning)).

### 19.2 A generated scoped rule: Cursor and Cline

`.cursor/rules/eos-security.mdc` (first lines):

~~~markdown
---
globs: **/*auth*,**/*login*,**/*session*,**/*crypt*,**/*secret*,**/*token*,**/*payment*,**/*wallet*,**/*permission*,**/*rbac*,**/*policy*,**/.env*,**/security/**
alwaysApply: false
---
<!-- eos-managed from .eos/packs/phases/security.md; edit there + `eos sync` -->
# Security

## Standards
…
Entry, deliverables, exit checklist and handoff: read `.eos/packs/phases/security.md` when starting or finishing this phase.
~~~

There is no `description:` line: the security pack is also a skill, and the skill is its only intent trigger, so it is listed once. The rule body is only *Standards* + *Automated checks*; the last line points to the full pack. `.clinerules/eos-security.md` carries the same body with Cline's `paths:` list:

~~~markdown
---
paths:
  - "**/*auth*"
  - "**/*login*"
  - "**/*session*"
  - "**/*crypt*"
~~~

### 19.3 Hook configs (generated)

`.cursor/hooks.json`:

~~~json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "python3 .eos/bin/eos.py guard cursor-shell",
        "timeout": 15
      }
    ],
    "preToolUse": [
      {
        "command": "python3 .eos/bin/eos.py guard cursor-tool",
        "timeout": 15
      }
    ],
    "beforeReadFile": [
      {
        "command": "python3 .eos/bin/eos.py guard cursor-read",
        "timeout": 10
      }
    ],
    "beforeMCPExecution": [
      {
        "command": "python3 .eos/bin/eos.py guard cursor-mcp",
        "timeout": 10
      }
    ],
    "stop": [
      {
        "command": "python3 .eos/bin/eos.py guard cursor-stop",
        "timeout": 240,
        "loop_limit": 3
      }
    ]
  }
}
~~~

`.claude/settings.json`:

~~~json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit|Read",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.eos/bin/eos.py\" guard claude-tool",
            "timeout": 15
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.eos/bin/eos.py\" guard claude-stop",
            "timeout": 240
          }
        ]
      }
    ]
  }
}
~~~

`.clinerules/hooks/PreToolUse` (executable):

~~~sh
#!/usr/bin/env sh
# eos-managed: Cline PreToolUse hook -> shared guard (Cline hooks: macOS/Linux).
exec python3 "$(dirname "$0")/../../.eos/bin/eos.py" guard cline-tool
~~~

### 19.4 Guard settings: `.eos/config.json` and `.eos/protected.txt` (project-owned)

~~~json
{
  "loop_limit": 3,
  "stop_check": "auto",
  "stop_check_timeout": 180,
  "cline_ask": "cancel",
  "mcp_write_ask": true,
  "push_policy": "feature-branches",
  "protected_branches": ["main", "master", "develop", "trunk", "release/*", "production"]
}
~~~

~~~text
# Paths agents must not edit without explicit human instruction (gitignore-style globs).
# Prefix with "tracked:" to protect only files already committed (new files are allowed).
.eos/**
.github/workflows/**
.pre-commit-config.yaml
**/*.lock
**/uv.lock
**/pnpm-lock.yaml
**/package-lock.json
**/yarn.lock
tracked:**/migrations/**
tracked:**/alembic/versions/**
CODEOWNERS
.github/CODEOWNERS
tracked:docs/adr/0*.md
!docs/adr/0000-template.md
~~~

### 19.5 Pre-commit base (`core/pre-commit/base.yaml`)

`eos init` appends the stack fragments to this. Python adds `ruff-check --fix` and `ruff-format` at commit, and mypy and pytest at pre-push. TypeScript adds lint at commit, and typecheck and tests at pre-push.

~~~yaml
# engineering-os: base pre-commit hooks (stack-agnostic). Stack fragments are appended by `eos init`.
# Fast hooks run on commit; slow ones (types, tests) run on pre-push. CI re-runs everything.
default_install_hook_types: [pre-commit, commit-msg, pre-push]
# Generated/vendored files are never reformatted (formatters would break eos drift checks and BMAD updates).
exclude: '^(\.eos/|_bmad/|_bmad-output/|\.cursor/rules/eos-|\.clinerules/eos-|\.clinerules/hooks/|\.claude/rules/eos-|(\.agents|\.cline|\.claude)/skills/(eos|bmad)-)'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: check-merge-conflict
      - id: check-yaml
        args: ["--allow-multiple-documents"]
      - id: check-json
        exclude: '(^|/)(tsconfig[^/]*\.json|\.vscode/.*|\.devcontainer/.*)$'
      - id: check-toml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: detect-private-key
      - id: no-commit-to-branch
        args: ["--branch", "main", "--branch", "master"]
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.4.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
  - repo: local
    hooks:
      - id: eos-check
        name: eos (AI context budget + adapter drift)
        entry: python .eos/bin/eos.py check
        language: python
        pass_filenames: false
        always_run: true
~~~

Conventional Commits are checked by `conventional-pre-commit`, a Python hook that needs no Node. JS-only teams can swap in commitlint. gitleaks' pre-commit hook builds from source with Go, which pre-commit downloads automatically; that needs network access the first time.

### 19.6 Core CI (`.github/workflows/eos-core.yml`)

~~~yaml
# engineering-os core CI: stack-agnostic gates. Pin actions by SHA (Renovate `helpers:pinGitHubActionDigests`).
name: eos-core
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ai-context:
    name: AI context budget, adapter drift, test integrity
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: eos check (budgets + adapters in sync with .eos/packs)
        run: python3 .eos/bin/eos.py check
      - name: Test integrity (new skips, removed asserts, lowered thresholds)
        if: github.event_name == 'pull_request' && !contains(github.event.pull_request.labels.*.name, 'test-change-approved')
        env:
          BASE_REF: ${{ github.base_ref }}
        run: python3 .eos/bin/eos.py test-integrity --base "origin/${BASE_REF}"
  secrets:
    name: Secrets scan (gitleaks)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: gitleaks (CLI image; the gitleaks-action needs a licence for org repos)
        run: docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact --no-banner
~~~

The stack workflows (`ci-python.yml`, `ci-node.yml`) run the stack's full check with workflow-level `paths:` filters. **If you make one a required check, remove its `paths:` filter.** Otherwise PRs that don't touch those paths wait forever on a check that never runs.

### 19.7 Renovate seed (`.github/renovate.json`)

~~~json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", "helpers:pinGitHubActionDigests", ":semanticCommits"],
  "minimumReleaseAge": "3 days",
  "dependencyDashboard": true,
  "pre-commit": { "enabled": true },
  "packageRules": [
    { "matchUpdateTypes": ["minor", "patch"], "groupName": "non-major dependencies", "automerge": false },
    { "matchUpdateTypes": ["major"], "dependencyDashboardApproval": true },
    { "matchFileNames": [".eos/**"], "enabled": false }
  ]
}
~~~

The `minimumReleaseAge` setting delays brand-new releases by 3 days, which limits exposure to compromised or broken releases. Major updates need approval on the dependency dashboard. Add a schedule and timezone (e.g. `"schedule": ["before 6am on monday"]`, `"timezone": "Africa/Douala"`) if you want PRs batched. Check option names against [Renovate's docs](https://docs.renovatebot.com/configuration-options/) for your version.

### 19.8 Rendered MCP config (`~/.cursor/mcp.json`, from `mcp/servers.json`)

~~~json
{
  "mcpServers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/x/repos/readonly",
      "headers": {
        "Authorization": "Bearer ${env:GITHUB_MCP_PAT}"
      }
    },
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:CONTEXT7_API_KEY}"
      }
    },
    "postman": {
      "url": "https://mcp.postman.com/minimal",
      "headers": {
        "Authorization": "Bearer ${env:POSTMAN_API_KEY}"
      }
    },
    "figma": {
      "url": "https://mcp.figma.com/mcp"
    }
  }
}
~~~

There are no values here, only variable names. Figma uses OAuth inside the client. Playwright is defined but disabled.

### 19.9 Review bot configuration

`.cursor/BUGBOT.md`:

```markdown
# Bugbot review checklist (my-product)
Review against the linked story/spec in the PR description. Flag, with file:line:
1. Money: floats, missing currency, rounding, non-idempotent POSTs, missing Idempotency-Key handling.
2. Transactions: side effects outside the unit of work; events not written to the outbox.
3. Security: authz checks on every endpoint, input validation, secrets/PII in logs, SSRF in outbound calls.
4. Async: blocking calls in async code; missing timeouts.
5. Migrations: non-backward-compatible changes (drop/rename without expand/contract), locking hazards.
6. Tests: any modified/removed/skipped test or lowered threshold — is it justified by the spec?
7. Frontend: hand-edited generated client, hard-coded strings (FR/EN), raw colours instead of tokens, a11y.
Ignore pure style issues (formatters handle them).
```

`.coderabbit.yaml` (if CodeRabbit instead):

```yaml
reviews:
  profile: assertive
  path_instructions:
    - path: "apps/api-*/src/**"
      instructions: "Apply docs/standards/money.md and api.md. Focus on idempotency, outbox usage, authz, async blocking calls and timeouts."
    - path: "apps/*/migrations/**"
      instructions: "Check expand/contract safety, locks on large tables, and downgrade correctness."
    - path: "**/tests/**"
      instructions: "Flag weakened, skipped or deleted tests and assertions that cannot fail."
    - path: "apps/web/src/**"
      instructions: "Check accessibility, FR/EN catalogue usage, generated client usage, server/client component boundaries."
```

### 19.10 Makefile (optional thin wrapper over the stack commands)

```makefile
.PHONY: check-fast check test-int openapi migrations-ci
check-fast:            ## ~30s: format+lint+types on changed packages
	uv run ruff format --check . && uv run ruff check . && uv run mypy $(shell scripts/changed-py-pkgs.sh)
	pnpm -r --filter "...[origin/main]" lint
check: check-fast      ## everything except E2E (Docker required)
	uv run lint-imports
	uv run pytest -q
	pnpm -r test
test-int:
	uv run pytest apps/$(SERVICE)/tests/integration -q
openapi:
	scripts/export-openapi.sh && pnpm --filter api-client generate
migrations-ci:
	scripts/migrations-roundtrip.sh $(SERVICE)
```

### 19.11 `.github/CODEOWNERS`

```
*                                   @your-handle
/AGENTS.md                          @your-handle
/.eos/                              @your-handle
/.claude/                           @your-handle
/.cursor/                           @your-handle
/.clinerules/                       @your-handle
/docs/adr/                          @your-handle
/.github/                           @your-handle
/apps/*/migrations/                 @your-handle
/apps/api-payments/src/payments/domain/   @your-handle
**/tests/contract/                  @your-handle
```

(Replace with real GitHub handles; add teammates as they join. CODEOWNERS only enforces when branch protection requires code-owner review.)

### 19.12 Full product CI example (extends the eos workflows)

For the monorepo in 18.3, add a `ci.yml` like this next to the generated `eos-core.yml`. It is an example, not generated, and was **not executed** (it needs the real services). File: `.github/workflows/ci.yml`

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      python: ${{ steps.f.outputs.python }}
      web: ${{ steps.f.outputs.web }}
      contracts: ${{ steps.f.outputs.contracts }}
    steps:
      - uses: actions/checkout@v7          # pin to a commit SHA in real use (Renovate keeps it updated)
      - id: f
        uses: dorny/paths-filter@v4
        with:
          filters: |
            python: ['apps/api-*/**', 'apps/worker-*/**', 'packages/py-shared/**', 'pyproject.toml', 'uv.lock']
            web: ['apps/web/**', 'packages/design-tokens/**', 'packages/api-client/**', 'pnpm-lock.yaml']
            contracts: ['contracts/**', 'apps/api-*/src/**/api/**']

  hygiene:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }
      - uses: astral-sh/setup-uv@v10
      - run: uv tool run pre-commit run --all-files --show-diff-on-failure   # test-integrity runs in eos-core.yml

  python:
    needs: changes
    if: needs.changes.outputs.python == 'true'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [api-payments, api-backoffice, worker-outbox]
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --frozen --all-packages
      - run: uv run ruff check apps/${{ matrix.service }}
      - run: uv run ruff format --check apps/${{ matrix.service }}
      - run: uv run mypy apps/${{ matrix.service }}/src
      - run: uv run lint-imports --config apps/${{ matrix.service }}/pyproject.toml
      - run: uv run pytest apps/${{ matrix.service }}/tests --cov --cov-report=xml   # testcontainers uses Docker on the runner
      - name: Migrations round-trip + lint
        if: matrix.service != 'worker-outbox'
        run: make migrations-ci SERVICE=${{ matrix.service }}   # upgrade → downgrade -1 → upgrade, alembic check, squawk
      - run: uv run pip-audit
      - run: uvx semgrep scan --config p/python --config p/owasp-top-ten --error apps/${{ matrix.service }}

  contracts:
    needs: [changes, python]
    if: needs.changes.outputs.contracts == 'true' || needs.changes.outputs.python == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }
      - uses: astral-sh/setup-uv@v10
      - uses: pnpm/action-setup@v6
      - uses: actions/setup-node@v7
        with: { node-version-file: .nvmrc, cache: pnpm }
      - run: uv sync --frozen --all-packages && pnpm install --frozen-lockfile
      - run: make openapi && git diff --exit-code contracts/ packages/api-client/
      - name: Breaking change check
        run: |
          git show origin/main:contracts/payments.openapi.json > /tmp/base.json || exit 0
          docker run --rm -v /tmp:/base -v "$PWD/contracts":/pr tufin/oasdiff breaking /base/base.json /pr/payments.openapi.json --fail-on ERR
      - run: make schemathesis SERVICE=api-payments   # boots the app + DB, runs schemathesis against /openapi.json

  web:
    needs: changes
    if: needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: pnpm/action-setup@v6
      - uses: actions/setup-node@v7
        with: { node-version-file: .nvmrc, cache: pnpm }
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web lint
      - run: pnpm --filter web typecheck
      - run: pnpm --filter web exec depcruise src --config .dependency-cruiser.cjs
      - run: pnpm --filter web test -- --coverage
      - run: pnpm --filter web build
      - run: pnpm audit --audit-level high

  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}   # required only for organization repos
      - uses: github/codeql-action/init@v4
        with: { languages: "python, javascript-typescript" }
      - uses: github/codeql-action/analyze@v4

  e2e:
    needs: [web]
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: pnpm/action-setup@v6
      - uses: actions/setup-node@v7
        with: { node-version-file: .nvmrc, cache: pnpm }
      - run: pnpm install --frozen-lockfile && pnpm --filter web exec playwright install --with-deps
      - run: pnpm --filter web e2e        # Playwright + @axe-core/playwright against the preview URL (PREVIEW_URL)
        env:
          PREVIEW_URL: ${{ vars.PREVIEW_URL_TEMPLATE }}   # wire to your preview-deploy step/provider
```

Release workflow outline (`release.yml`, on push to `main`): release-please → on release: build images → `anchore/sbom-action` (SBOM) → Trivy scan → `actions/attest-build-provenance@v4` (needs `id-token: write`, `attestations: write`) → deploy to staging → k6 smoke → manual approval (GitHub Environment) → canary → full rollout.

*(Action major versions are the latest releases seen on 9 Oct 2026; check each action's README for input changes when you upgrade.)*

---

## 20. Honest caveats

1. **No setup guarantees billion-user scale.** Scale comes from architecture fitted to real load, measured with real traffic, plus years of operational learning. This blueprint gives you the *habits and safety nets* that large organisations use; it does not make a system scalable by itself. Load-test against your actual SLOs and grow the architecture when data says so.
2. **Humans must review money, security and data code.** AI reviewers (including the best ones) miss things and can be confidently wrong. For payment flows, ledgers, fees, authentication, permissions, cryptography, PII handling and migrations, a human (you, and ideally a second engineer) approves every change. For regulated activity, legal/compliance review is separate from code review.
3. **AI agents can "cheat"** (weaken tests, special-case inputs). The guardrails in 6.6 (including `eos test-integrity`) reduce this but do not eliminate it. Read test diffs.
4. **Tools change monthly.** BMAD renamed its core implementation skills twice in 2026 (v6.11, v6.12); Cursor's model list and prices change; Next.js and TypeScript had major releases this year. Pin versions, let Renovate propose upgrades, and re-verify this document's [Verified] items every quarter.
5. **Vendor prices and included usage are not guaranteed.** I cited only prices published on the vendors' own pages on 9 Oct 2026; Cursor does not publish the exact size of each plan's included pools. Measure your own cost per story.
6. **Hook payload field names** (especially Cursor `preToolUse` tool inputs) can change between tool versions. The eos guard reads defensively and logs to `.eos/state/guard.log`; check it once per tool.
7. **Experimental features** (Turborepo Python workspaces, ty, Cline hooks on Windows) can break; don't make them blocking gates.
8. **Confidential code and data:** every model call sends code to a provider. Use providers and settings (privacy mode, zero-data-retention routing on OpenRouter) compatible with your clients' contracts, and never paste production customer data into a chat.
9. **Heuristics are not standards.** Token budgets, the two-servers-on MCP default, CI time targets and setup-time caps are my rules of thumb; adjust them with evidence.
10. **This document was researched by an AI assistant**: every [Verified] claim links to its source, but read the sources for anything you'll depend on.
11. **Hooks are defence in depth, not a security boundary.** The guard uses pattern matching. A determined or confused agent can phrase a command it doesn't match (for example through a script file). It also **fails open** on crashes, so it never bricks the editor. Real boundaries are least-privilege tokens, branch protection, CODEOWNERS, environment approvals and human review.
12. **Adapter formats belong to the vendors.** Cursor `.mdc` frontmatter, Cline `paths:`, Claude Code `.claude/rules`, hook payloads and skills folders were checked against each vendor's docs on 9 Oct 2026. Any of them can change. The guard reads only documented fields and logs anything unexpected to `.eos/state/guard.log`. After a tool upgrade, glance at that log and run `tests/selftest.sh`.
13. **Tested where, exactly.** The scripts were tested on Linux: unit tests, shellcheck, actionlint, pre-commit validation, `init` into fixtures, a fake-home bootstrap, the global hook dispatcher, and a real BMAD headless install. macOS should behave the same, because the scripts are POSIX sh and stdlib Python. **Windows (`bootstrap.ps1`) was not executed**; the repo's CI matrix runs the unit tests on Windows to catch regressions. The hooks were not exercised inside live Cursor, Cline or Claude Code sessions. Test one deliberate "blocked" command in each tool on day 1.
14. **Token counts are estimates** (chars ÷ 4). Real tokenisers vary by model, so treat the budgets as relative limits, not exact numbers.
15. **Cursor personal rules.** Cursor's *User Rules* live in its settings UI. eos also writes `~/.cursor/rules/eos-profile.mdc`, which may not be read by every Cursor version. If your profile doesn't show up, paste `personal/PROFILE.md` into Settings → Rules.
16. **One directory per stack (v0.2.0).** Monorepos with several Python or Node apps get hooks and CI for the first detected directory only (see [Section 12.4](#124-monorepos)).

---

## 21. Maintenance cadence

| Frequency | Task |
|---|---|
| Every story | Fresh chat; plan file; stack full check green; `memory/active-context.md` rewritten; pitfalls recorded |
| Weekly | Cost log; Renovate PRs; skim `.eos/state/guard.log` for false positives and blocks; tune the PR-bot checklist |
| Per epic | `bmad-retrospective` → **`eos-retro`** (lessons → checks; prune); `bmad-project-context` *Refresh*; archive old plans; review the ADR index |
| Monthly | `eos budget` across projects; model-routing review (re-run the mini eval on one new cheap model); MCP audit (remove unused servers, rotate tokens); DORA metrics |
| Quarterly | Re-verify the [Verified] items here and in `docs/SOURCES.md`; bump `versions.toml` and tag an eos release; `eos update` in each project; upgrade BMAD on a branch; chaos game day; backup-restore drill; threat-model refresh |

---
## 22. Open decisions

| # | Decision | Options | My default suggestion | What would change it |
|---|----------|---------|-----------------------|----------------------|
| 1 | Python type checker in the `python` pack | mypy strict / pyright strict (ty later) | mypy strict (pydantic plugin, mature); the pack's `full_check` uses mypy | You live in Pyright/Pylance tooling or need its stricter inference. Swap the command in `STACK.md` |
| 2 | JS lint/format in the `typescript` pack | ESLint + Prettier / Biome | ESLint + Prettier (a11y, boundaries, React plugins); the pack only requires a `lint` script, so either works | Speed and one tool → Biome |
| 3 | Global git hooks (`bootstrap --global-hooks`) | on / off | **On for your own machine**: every repo gets gitleaks on commit. Off on shared or CI machines | Repos with their own hook managers (Husky) keep working, but check that once |
| 4 | Guard strictness | default lists / stricter (also ask on package installs, `docker run`, network tools) / looser (allow `git push` to feature branches) | Default. Review `guard.log` after 2 weeks; adjust `SHELL_ASK`/`SHELL_DENY` in the eos repo (a minor release) or `.eos/protected.txt` per project | Too many prompts → loosen; an incident → tighten |
| 5 | Cline MCP secrets on disk | literal values in Cline's private settings (default) / don't render MCP for Cline (`--tools cursor`) / short-lived tokens | Default, with read-only tokens and short expiry | Shared machine or strict policy → no MCP in Cline |
| 6 | Required checks vs `paths:` filters | keep path filters (fast) / make stack jobs required (remove filters) | eos-core required; stack jobs required **without** path filters once CI time allows | CI time and cost |
| 7 | Windows | native PowerShell (no Cline hooks) / WSL2 | WSL2 for development | Corporate machine policy |
| 8 | Monorepo orchestration | plain workspaces / Turborepo / Nx | Plain workspaces + stack CI; revisit when CI > ~15 min | Many packages, slow CI |
| 9 | Premium planning/review model (T1) | any current top reasoning model, via Cursor "Other Models" or OpenRouter | Two from *different* families: one plans, one reviews. Record in `docs/ai/model-routing.md` | Mini-eval results, monthly cost |
| 10 | Primary PR review bot | Cursor Bugbot / CodeRabbit | Bugbot first (already in your plan per Cursor's pricing page) | The seeded-bug eval favours CodeRabbit |
| 11 | BMAD version | stable v6.12.1 (pinned) / Skills-CLI layout on `main` once released | Stay pinned; migrate on a branch after release notes confirm | A release that fixes something you need |
| 12 | Hosting / deploy target | PaaS, containers on VMs, Kubernetes, serverless | A managed container platform with preview envs | Data residency (CEMAC/client contracts), latency, budget |
| 13 | Release tooling | release-please / semantic-release | release-please | Libraries with fully automatic releases |
| 14 | Unattended agents | Cursor Cloud Agents / `bmad-build-auto` / BMad Loop / none | None until rollout phase 6 | Cost, data-exposure policy, pattern stability |
| 15 | Action pinning | major tags (as generated) / commit SHAs | SHAs via Renovate `helpers:pinGitHubActionDigests` (seeded) | n/a; let Renovate do it |
| 16 | Next stack packs to write | Go, PHP/Laravel, Kotlin/Android, Flutter, Terraform | Whatever your next real project uses; Laravel is likely given your background | Client work |

---
## 23. Glossary

- **Adapter**: a tool-specific file (e.g. a Cursor `.mdc` rule) generated from a canonical pack, never edited by hand.
- **ADR** — Architecture Decision Record: a short file documenting one decision and its reasons.
- **Agent** — an AI model that can take actions (edit files, run commands, call tools) in a loop.
- **Blue/green deploy** — two identical environments; switch traffic from old (blue) to new (green) and back if needed.
- **BMAD** — "Breakthrough Method for Agile AI-Driven Development", an open-source framework of AI agent personas and workflows.
- **Canary deploy** — releasing a new version to a small share of traffic first, then expanding if healthy.
- **Pack index**: `.eos/packs/INDEX.md`, generated, with one line per pack giving its trigger and path, so tools without path rules (e.g. Codex) can load packs just in time. `AGENTS.md` only points to it.
- **Context window** — the maximum amount of text (tokens) a model can consider at once.
- **Contract-first** — define the API specification before (or as) you implement it, and generate code/tests from it.
- **DORA metrics** — five delivery metrics from Google's DORA research programme (lead time, deploy frequency, recovery time, change fail rate, rework rate).
- **Drift**: when a generated file no longer matches its source. `eos check` fails on drift.
- **EARS** — "Easy Approach to Requirements Syntax": templates like "WHEN … THE SYSTEM SHALL …".
- **Error budget** — the amount of unreliability an SLO allows (e.g. 99.9% → 0.1% may fail).
- **Eval** — a repeatable test of an AI system's output quality.
- **Fail open / fail closed**: when a hook crashes, it either allows the action (open) or blocks it (closed). The eos guard fails open and logs.
- **Guard**: the shared hook program (`eos guard`) that all agent tools call before shell commands, file edits, reads and MCP calls.
- **Handoff**: a short file (`memory/handoff.md`) that an agent writes when it stops without finishing, so a fresh session or a human can continue.
- **Hook** — a script a tool runs automatically at a fixed point (before commit, after an agent edit…).
- **Idempotency** — doing the same request twice has the same effect as doing it once.
- **Loop guard**: detects the same command run repeatedly on unchanged code and asks a human.
- **Marker file**: a file whose presence identifies a stack (e.g. `pyproject.toml` → Python).
- **MCP** — Model Context Protocol: standard for connecting agents to external tools and data.
- **Mutation testing** — automatically introducing small bugs to check that tests catch them.
- **Outbox pattern** — saving outgoing events in the same DB transaction as the business change, then publishing them reliably.
- **Phase pack**: language-free standards for one lifecycle phase (entry, standards, deliverables, checks, exit, handoff, stop).
- **Prompt caching** — the provider reuses an already-processed prompt prefix, at a lower price.
- **Reward hacking** — an agent satisfying the metric (tests pass) without achieving the goal (feature works).
- **SBOM** — Software Bill of Materials: list of all components in a build.
- **Skill**: a folder with a `SKILL.md` that an agent loads only when the task matches its description.
- **SLO / SLI** — Service Level Objective / Indicator: a reliability target and the measurement behind it.
- **SLSA** — framework of supply-chain integrity levels for builds.
- **Spec-driven development (SDD)** — the written spec is the main artifact; code is produced and checked against it.
- **Stack pack**: commands and idioms for one ecosystem, plus its pre-commit and CI fragments.
- **Token** — the unit models read and bill by (roughly ¾ of an English word).
- **Vendoring**: copying a tool into the project (here `.eos/bin/eos.py`) so it works without a separate install.

---

## 24. Definition of Done (per story) — print this

- [ ] Story has EARS acceptance criteria and a plan file
- [ ] Failing tests were written first (one per AC) and now pass
- [ ] Stack full check (AGENTS.md table) green locally; the stop hook passed; CI green
- [ ] No protected files changed (or explicitly approved); `eos test-integrity` clean or labelled `test-change-approved` by a human
- [ ] OpenAPI + generated client updated if the API changed; no breaking change without version bump/ADR
- [ ] Migration is expand/contract-safe and round-trips
- [ ] Logs/metrics/traces added for new flows; no PII in logs
- [ ] Review: in-loop review done; `bmad-code-review` thorough if risky; PR bot findings resolved
- [ ] Human approval recorded for money/auth/crypto/migration/infra changes
- [ ] Feature flag in place for risky user-facing changes
- [ ] Phase exit checklists for the touched phases satisfied (packs)
- [ ] `memory/active-context.md` rewritten, `progress.md` line appended; repeat mistakes → `eos-retro`

---

## 25. Sources

All accessed 9 October 2026.

**BMAD Method**
- BMAD-METHOD repository and README — https://github.com/bmad-code-org/BMAD-METHOD
- Releases (v6.11.0, v6.12.0, v6.12.1) — https://github.com/bmad-code-org/BMAD-METHOD/releases
- npm package `bmad-method` (latest 6.12.1) — https://www.npmjs.com/package/bmad-method
- Install BMad (website; documents the newer Skills-CLI layout on `main`) — https://docs.bmad-method.org/start/install-bmad/
- Choose a Planning Path — https://docs.bmad-method.org/plan/choose-a-planning-path/
- Skills and Agents reference — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/skills-and-agents.md
- Build a Change — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/build-a-change.md
- Review a Change — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/review-a-change.md
- Autonomous Development Loops — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/autonomous-development-loops.md
- Set and Maintain Project Context — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/existing-codebases/set-and-maintain-project-context.md
- Adopt BMad Across a Team — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/customize/adopt-bmad-across-a-team.md
- v6 getting-started (tracks: Quick Flow / BMad Method / Enterprise) — https://github.com/bmad-code-org/BMAD-METHOD/blob/e36f219c/docs/tutorials/getting-started.md
- v6.12.1 (stable) install guide — https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.1/docs/start/install-bmad.md
- v6.12.1 (stable) skills and agents reference — https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.1/docs/reference/skills-and-agents.md
- Break Work into Stories and Track It (main) — https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/plan/break-work-into-stories-and-track-it.md

**Spec-driven development**
- GitHub Spec Kit README — https://github.com/github/spec-kit/blob/main/README.md
- Spec Kit quickstart — https://github.github.com/spec-kit/quickstart.html
- Spec Kit releases (v1.1.2) — https://github.com/github/spec-kit/releases
- Kiro feature specs — https://kiro.dev/docs/specs/feature-specs/
- Kiro steering — https://kiro.dev/docs/steering.md

**Cursor**
- Models & Pricing — https://cursor.com/docs/models-and-pricing
- Rules — https://cursor.com/docs/rules
- Hooks — https://cursor.com/docs/hooks
- Agent Skills — https://cursor.com/docs/skills
- Bugbot — https://cursor.com/docs/bugbot
- Cloud Agents — https://cursor.com/docs/cloud-agents ; setup — https://cursor.com/docs/cloud-agent/setup
- MCP configuration — https://cursor.com/docs/mcp
- Hooks cookbook — https://github.com/cursor/cookbook/blob/main/hooks/README.md

**Cline**
- Rules (incl. conditional `paths`) — https://docs.cline.bot/customization/cline-rules
- Memory Bank — https://docs.cline.bot/best-practices/memory-bank
- Skills — https://docs.cline.bot/customization/skills
- Plan & Act — https://docs.cline.bot/core-workflows/plan-and-act
- Commands (`/deep-planning`, `/smol`, `/newtask`) — https://docs.cline.bot/core-workflows/using-commands
- Auto Compact — https://docs.cline.bot/features/auto-compact
- Installing Cline — https://docs.cline.bot/getting-started/installing-cline
- Hooks README — https://github.com/cline/cline/blob/8a6441fd/.clinerules/hooks/README.md
- Cline v3.36 Hooks announcement — https://cline.bot/blog/cline-v3-36-hooks

**OpenRouter**
- Limits (credit limits, free-model rate limits) — https://openrouter.ai/docs/api_reference/limits
- Spend controls / guardrails — https://openrouter.ai/docs/guides/best-practices/spend-controls
- Prompt caching — https://openrouter.ai/docs/guides/best-practices/prompt-caching

**MCP**
- MCP Authorization spec (2025-11-25) — https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- MCP Security Best Practices — https://modelcontextprotocol.io/docs/2025-03-26/tutorials/security/security_best_practices
- OWASP: MCP Tool Poisoning — https://github.com/OWASP/www-community/blob/master/pages/attacks/MCP_Tool_Poisoning.md
- Reference Memory server — https://github.com/modelcontextprotocol/servers/tree/main/src/memory
- GitHub MCP remote server (toolsets, read-only) — https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md
- AGENTS.md format — https://agents.md/

**Review bots and agent testing**
- CodeRabbit configuration — https://docs.coderabbit.ai/reference/configuration
- "Protecting the oracle" — https://developertoolkit.ai/en/workflows/test/protect-the-oracle/
- "The Verification Horizon: No Silver Bullet for Coding Agent Rewards" (arXiv) — https://arxiv.org/html/2606.26300

**Python, JS and build tooling (versions from registries)**
- PyPI (uv, ruff, mypy, pyright, fastapi, flask, pydantic, sqlalchemy, alembic, pytest, hypothesis, mutmut, import-linter, bandit, semgrep, pre-commit, opentelemetry-sdk, structlog, schemathesis, ty, apiflask, flask-smorest, pip-audit, testcontainers, squawk-cli) — https://pypi.org/
- npm registry (next, typescript, @biomejs/biome, eslint, prettier, dependency-cruiser, vitest, @playwright/test, storybook, @axe-core/playwright, @lhci/cli, turbo, nx, husky, lint-staged, @commitlint/cli, semantic-release, release-please, orval, @hey-api/openapi-ts, openapi-typescript, style-dictionary, eslint-plugin-boundaries, knip, pnpm) — https://www.npmjs.com/
- Python release cycle — https://endoflife.date/python ; Node.js — https://endoflife.date/nodejs
- ty (beta) — https://pypi.org/project/ty/
- Turborepo Python (experimental) — https://turborepo.dev/docs/guides/tools/python
- Next.js 16 — https://nextjs.org/blog/next-16 ; Next.js 16.4 — https://nextjs.org/blog/next-16-4 ; October 2026 security notice — https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026
- TypeScript 7.0 — https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/
- oasdiff — https://github.com/oasdiff/oasdiff
- gitleaks-action (licence note) — https://github.com/gitleaks/gitleaks-action
- ruff pre-commit hooks — https://github.com/astral-sh/ruff-pre-commit
- GitHub releases checked for: grafana/k6 (v2.3.0), sigstore/cosign, anchore/syft, renovatebot/renovate, aquasecurity/trivy, chaos-mesh, Unleash, dorny/paths-filter, actions/*, astral-sh/setup-uv, pnpm/action-setup

**Supply chain**
- SLSA v1.1 specification — https://slsa.dev/spec/v1.1/
- GitHub artifact attestations — https://docs.github.com/en/actions/concepts/security/artifact-attestations
- Reaching SLSA Build Level 3 with reusable workflows — https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/increase-security-rating

**Reliability and delivery practice**
- DORA metrics guide — https://dora.dev/guides/dora-metrics
- DORA 2025 State of AI-assisted Software Development — https://dora.dev/research/2025/dora-report
- RedMonk on DORA 2025 — https://redmonk.com/rstephens/2025/12/18/dora2025/
- Google SRE book, Embracing Risk — https://sre.google/sre-book/embracing-risk/
- Google SRE workbook, Implementing SLOs — https://sre.google/workbook/implementing-slos/
- Netflix Chaos Monkey — https://netflix.github.io/chaosmonkey/
- Stripe idempotent requests — https://docs.stripe.com/api/idempotent_requests
- IETF draft: Idempotency-Key header — https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- Transactional outbox pattern — https://microservices.io/patterns/data/transactional-outbox.html

**Engineering OS additions (version 2)**
- Anthropic, "Effective context engineering for AI agents" — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Claude Code memory, `CLAUDE.md` imports and `.claude/rules` — https://code.claude.com/docs/en/memory
- Claude Code hooks — https://code.claude.com/docs/en/hooks
- Claude Code MCP — https://code.claude.com/docs/en/mcp
- Claude Code skills — https://code.claude.com/docs/en/skills
- Codex `AGENTS.md` — https://developers.openai.com/codex/guides/agents-md
- Codex MCP configuration — https://developers.openai.com/codex/mcp
- Cline hooks — https://docs.cline.bot/features/hooks
- Cline MCP configuration (`cline_mcp_settings.json`, `streamableHttp`) — https://docs.cline.bot/mcp/configuring-mcp-servers
- Agent Skills specification — https://agentskills.io
- Postman remote MCP server — https://learning.postman.com/docs/developer/postman-api/postman-mcp-server/postman-mcp-remote-server/
- Figma MCP server (remote) — https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/
- Context7 — https://github.com/upstash/context7
- Playwright MCP — https://github.com/microsoft/playwright-mcp
- uv installation — https://docs.astral.sh/uv/
- pre-commit — https://pre-commit.com
- conventional-pre-commit — https://github.com/compilerla/conventional-pre-commit
- gitleaks (and its Docker image) — https://github.com/gitleaks/gitleaks
- Renovate configuration options — https://docs.renovatebot.com/configuration-options/
- Renovate helper presets — https://docs.renovatebot.com/presets-helpers/
- actionlint — https://github.com/rhysd/actionlint
- ShellCheck — https://www.shellcheck.net
- Diátaxis documentation framework — https://diataxis.fr
- OWASP Top 10 — https://owasp.org/Top10/
- OWASP ASVS — https://owasp.org/www-project-application-security-verification-standard/
- OWASP GenAI Security Project — https://genai.owasp.org
- RFC 9457 (Problem Details for HTTP APIs) — https://www.rfc-editor.org/rfc/rfc9457
- WCAG 2.2 — https://www.w3.org/TR/WCAG22/
**Context and token audit (v0.2.0)**
- Anthropic, Effective context engineering for AI agents — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic, Claude prompting best practices — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- OpenAI, GPT-5 prompting guide — https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/gpt-5/gpt-5_prompting_guide.ipynb
- Cursor, Rules — https://cursor.com/docs/context/rules
- Cursor, Dynamic context discovery (MCP tools loaded on demand) — https://cursor.com/blog/dynamic-context-discovery
- Claude Code, Memory (CLAUDE.md, AGENTS.md import, size guidance) — https://code.claude.com/docs/en/memory
- Claude Code, MCP (tool search on by default) — https://code.claude.com/docs/en/mcp
- Cline, Rules — https://docs.cline.bot/customization/cline-rules
- Cline issue: high token usage with MCP servers enabled — https://github.com/cline/cline/issues/9398
- Codex, AGENTS.md (`project_doc_max_bytes`) — https://developers.openai.com/codex/guides/agents-md
- Codex PR: use tool search for MCP tools by default — https://github.com/openai/codex/pull/29486
- github-mcp-server releases (v2.0.2 used for the schema measurement) — https://github.com/github/github-mcp-server/releases
**Senior review (v0.3.0)**
- OpenRouter models API (model ids and prices on 9 Oct 2026) — https://openrouter.ai/api/v1/models
- OpenRouter per-key credit limits and resets — https://openrouter.ai/docs/api_reference/limits
- Cline, Plan & Act (different models per mode) — https://docs.cline.bot/core-workflows/plan-and-act
- Cline, MCP overview (`disabled` flag, CLI settings path) — https://docs.cline.bot/mcp/mcp-overview
- release-please-action (v5.0.0, node24) — https://github.com/googleapis/release-please-action
- dependency-review-action (v5.0.0; availability on private repos) — https://github.com/actions/dependency-review-action and https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review
- anchore/sbom-action — https://github.com/anchore/sbom-action
- CodeQL action (v4) — https://github.com/github/codeql-action
- oasdiff-action (`breaking`, `review: false`) — https://github.com/oasdiff/oasdiff-action
- squawk (Postgres migration linter, npm `squawk-cli` 2.68.0) — https://github.com/sbdchd/squawk
- uv in Docker — https://docs.astral.sh/uv/guides/integration/docker/
- Next.js deploying (standalone output) — https://nextjs.org/docs/app/getting-started/deploying
- testcontainers-python (4.15.0) — https://pypi.org/project/testcontainers/
- @axe-core/playwright (4.13.0) — https://www.npmjs.com/package/@axe-core/playwright
- Docker Official Images: postgres (18), redis (8), python, node tags — https://hub.docker.com/_/postgres
- The `engineering-os` repo carries its own `docs/SOURCES.md` with the links behind each pack.

---

## 26. Senior review v0.3.0

I reviewed the whole system (repo and this blueprint) as the person who would use it every day, by doing what a new user does: bootstrap a fake home, init a FastAPI project, run `eos doctor`, write a story, follow it to a PR, and read every generated file. The question each time was: what is weak, missing or over-built, and what would annoy you in week 1 versus month 3?

### 26.1 Findings, by priority

**Critical** (fixed in v0.3.0)
1. **MCP was all-or-nothing, and Cline was starved.** GitHub was hard-excluded from Cline, and changing servers meant editing JSON and re-running bootstrap. Now there are per-task profiles: `eos mcp use build|review|api|design|debug-ui|minimal|off`, with a phase id as an alias. The choice is per tool, and Cline gets a `disabled` toggle per server.
2. **A force push could slip through the guard.** `git -C dir push --force` and `git push origin +branch` escaped the deny regex. Push handling now parses the command itself: force is always denied, wherever it appears.
3. **Every `git push` needed an approval.** In week 1 people switch hooks off over prompts like this. A new `push_policy: feature-branches` (the default for new projects) lets pushes to feature branches through. It still asks for protected branches (main, master, develop, trunk, release/*, production), tags, deletes, `--all`/`--mirror`, force-with-lease, a detached HEAD, and pushes hidden inside `sh -c`.
4. **CI claimed gates it did not run.** The packs talk about coverage, migration safety, e2e, a11y, bundle budgets, contract checks and SBOMs, but CI ran only lint, types, tests and an audit. Now:
   - the coverage gate (`COVERAGE_MIN`, default 80) runs whenever pytest-cov is installed;
   - squawk lints any SQL migration a PR changes;
   - Playwright e2e + axe a11y run whenever a Playwright config exists;
   - the bundle-size step runs whenever a `size` script exists;
   - oasdiff (API contract) and dependency review + SBOM + CodeQL are one `eos scaffold` away.
5. **"Money and auth need human review" had nothing enforcing it.** There was no PR template and no CODEOWNERS. `eos init` now seeds a PR template (AC → test map, risk boxes, an AI-assistance note) plus story and bug issue forms. `eos scaffold codeowners --owner @you` writes owners for the risky paths.

**High** (fixed)
6. **`eos doctor` described problems but never said how to fix them.** It did not check the project or explain PATH, and `pre-commit install` was a manual step that was easy to forget. Every problem line now ends with the command that fixes it, using brew, winget or Linux hints. It also checks:
   - whether the project's eos version is behind the repo;
   - hooks that aren't installed;
   - `.eos-new` files that haven't been merged;
   - placeholder text left in AGENTS.md;
   - stale memory;
   - a repo on `/mnt/c` under WSL;
   - empty secrets for the active MCP profiles.

   `eos init` now installs the hooks itself.
7. **Model routing was prose, built around a $5 budget.** It now lives in `personal/models.toml`: premium, strong and cheap tiers, a task → tier map, and an escalation rule. Budget caps are settings, with 0 meaning no cap, and you can override any of it in a git-ignored `models.user.toml`. `eos models --check` checks the ids against the live catalogue, and `--usage` compares your OpenRouter key's spend with the caps. The core rules gained one line: after two failed attempts at a hard problem, suggest a stronger model or a fresh session.
8. **ADRs and stories were numbered by hand.** Nothing linked a story's AC ids to tests or the PR. Now:
   - `eos new adr "<title>"` writes the file and its INDEX line;
   - `eos new story "<title>"` writes a story with AC ids;
   - the BMAD dev persona names tests after AC ids and fills the PR template.
9. **Projects had no release automation or changelog.** `eos scaffold release` adds release-please v5 with a config and manifest. It notes a GitHub limitation: PRs opened with `GITHUB_TOKEN` do not trigger CI.
10. **There was no way out.** `eos uninstall` removes generated files you did not edit, strips the hook entries and the AGENTS.md blocks, and keeps your memory, ADRs, docs and scaffolds.
11. **There was no production or local-dev scaffolding.** New opt-in scaffolds, all written once and yours afterwards:
    - `compose`: Postgres 18 and Redis 8 with health checks, bound to 127.0.0.1, plus `.env.example` with OTel and feature-flag variables;
    - `docker-python`: uv multi-stage, non-root, a HEALTHCHECK, and FastAPI `/healthz` + `/readyz`;
    - `docker-node`: Next.js standalone, non-root.
12. **There were no testing templates.** `tests-python` adds a testcontainers Postgres fixture that skips cleanly without Docker, factories that use integer minor units for money, and a one-page test pyramid. `e2e-node` adds a Playwright smoke test with an axe check.

**Medium** (fixed unless marked)
13. **Nothing flagged stale memory.** `eos check` and `eos doctor` now warn when `memory/active-context.md` is more than 25 commits behind, or `handoff.md` is more than 14 days old. These are warnings, not failures.
14. **There was no threat-model template or dependency policy.** Both now come with `eos scaffold security`.
15. **Windows/WSL guidance was thin.** It now covers WSL 2 with repos in the Linux filesystem, and doctor flags `/mnt/c`. Native Windows is documented but still **untested**: the selftest runs on Linux.
16. **Two MCP rendering gaps.** The Cline CLI settings file was ignored, and the Claude Code MCP script never removed servers that had been switched off. Both are fixed.
17. **Workflow knowledge was scattered.** It included when to plan vs act, recovery, escalation, worktrees and cloud agents, evals of the system, and memory hygiene. It is now in `docs/WORKFLOW.md`, a step-by-step table from idea to release with the check at each handoff. It is read on demand and costs no tokens.
18. **Existing projects do not receive new config defaults.** `.eos/config.json` and the BMAD overrides are seeded once. *Deferred and documented*, because silently changing security settings in existing repos is worse than a one-line manual opt-in (section 11.4).
19. **Alembic migrations are Python, so squawk never sees them.** *Deferred*: rendering them to SQL offline depends on each project's `env.py`. The backend pack's expand/contract rules and the guard's approval prompt for migrations still apply.
20. **Node coverage thresholds are not enforced by CI.** *Deferred*: they belong in `vitest.config` (`coverage.thresholds`), which eos does not own. The test-strategy doc says so.

**Nice-to-have** (deferred)
21. **OpenTelemetry wiring code.** Deferred because it is framework- and vendor-specific. The scaffolds set the standard `OTEL_*` variables. Start with the zero-code `opentelemetry-instrument` wrapper and the observability standards in the operations pack.
22. **Preview environments.** Deferred because they depend on the platform (Vercel, Fly, Render, Kubernetes namespaces). Pick the platform first, then add one workflow.
23. **Feature-flag SDK.** Deferred: an env-var-per-flag convention is enough until you need targeting. Then adopt an OpenFeature-compatible provider.
24. **An automated eval runner for the system itself.** Deferred. `docs/WORKFLOW.md` defines a 30-minute monthly golden-task routine, which is enough until it is done often enough to be worth automating.
25. **Splitting `bin/eos.py` (now ~2,900 lines) into modules.** Deferred: one stdlib-only file is what makes the vendored copy in every project work without installing anything. Split it when a second maintainer appears.
26. **Auto-switching MCP profiles when a phase starts.** Deferred. No tool exposes a "phase started" event, and Cline reads one global settings file. `eos mcp use <phase>` is the honest version.

**What is not over-engineered, and what might be.** The four-tool adapter matrix costs nothing when you use two tools, because only the chosen tools get files. The 18 phase packs cost about 320 tokens of skill descriptions in total and nothing else until used. Candidates to delete after month 3 if they never fire: the `mobile` and `ideation` packs, and the `test-change-approved` label flow if you are the only reviewer.

**Week 1 vs month 3.**
- *Week 1 annoyances*, now fixed: approval prompts on push, a doctor that does not say what to do, and forgetting `pre-commit install`.
- *Week 1 annoyances that remain*: the first commit is slow while pre-commit builds its hook environments (one time only), and editors launched from a GUI do not see shell environment variables (section 10.4).
- *Month 3 risks*:
  - memory going stale (now warned about);
  - `.eos-new` files piling up (doctor lists them);
  - model ids being renamed (`eos models --check`);
  - pins ageing (Renovate);
  - lessons growing (capped by `eos check`).

**Template vs rule.** Use a template or scaffold for anything mechanical that has one correct default: CI, Dockerfiles, PR templates, compose. Use a rule only for judgement. Use a check whenever a rule can be verified automatically. v0.3.0 moved work from prose to templates and checks. The always-on rules grew by exactly one line.

### 26.2 Token numbers, before and after

Measured with the same script and fixture as section 4.2 (FastAPI `api/` + Next.js `web/`, all four tools, chars/4) on the v0.2.0 tag and on v0.3.0 [Tested]:

| Tool | Session start v0.2.0 → v0.3.0 | Path rules editing a route | MCP schemas per request |
|---|---|---|---|
| Cursor | 1,715 → 1,740 | 2,864 → 2,864 | names only (lazy) |
| Cline | 1,691 → 1,716 | 2,899 → 2,899 | 1,250 → ≈4,450 in the default `build` profile (deliberate: GitHub is now on); `minimal` = 1,250 |
| Claude Code | 1,738 → 1,763 | 2,899 → 2,899 | names only (tool search) |
| Codex | 1,691 → 1,716 | none (INDEX on demand) | deferred (tool search) |

Everything else added in v0.3.0 is on demand: CLI commands, scaffolds, templates and `docs/WORKFLOW.md`.

### 26.3 How it was tested

- 39 unit/integration tests pass (`python3 -m unittest discover tests`), 10 more than v0.2.0. The new tests cover:
  - MCP profiles and phase aliases;
  - a Cline toggle round-trip in a fake home;
  - model routing and escalation, and user overrides;
  - doctor project checks and memory staleness;
  - the push policy (feature branch, HEAD:main, release/*, tags, `--delete`, `-C` force, sub-shell);
  - seeded GitHub templates;
  - `eos new` numbering and the INDEX line;
  - every scaffold rendering with no placeholders left, plus actionlint on the generated workflows;
  - uninstall keeping edited files and memory.
- `tests/selftest.sh --full`, ruff, shellcheck and actionlint all pass, and so does a full `pre-commit run` on a freshly initialised fixture.
- Not tested: native Windows, the hooks running live inside each editor, the scaffolded Dockerfiles (`docker build`; no Docker on the build box), the security/release workflows on GitHub itself, and `eos models --usage` against a real key.

## 27. Research-driven upgrades (v0.4.0)

*10 October 2026. The request: research broadly and independently, beyond the original prompts, and fold the best ideas in, so the system works for any project type and environment. The full cited report is `RESEARCH.md` (PDF alongside; also `engineering-os/docs/research/RESEARCH.md`, with raw notes in `notes.md`). This section summarises what changed in the repo.*

### 27.1 What the research said, in plain words

1. **Fix the environment, not the prompt.** OpenAI's Codex team and Stripe's Minions both found that agent output quality comes from:
   - a small always-on map;
   - scoped rules;
   - a curated tool set;
   - isolated environments;
   - fast deterministic checks;
   - a cap on retries.

   ([OpenAI](https://openai.com/index/harness-engineering/), [Stripe](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)) engineering-os already had most of this. v0.4 adds what was missing: execution plans, decisions and fitness functions.
2. **AI helps only on good foundations, so measure.** METR's randomised trial found experienced developers 19% slower with AI on their own repositories. DORA 2025 calls AI an amplifier of existing strengths and weaknesses. ([METR](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), [DORA](https://dora.dev/research/2025/dora-report))
3. **Agents copy bad patterns and cheat on tests.** So the system needs:
   - protected tests;
   - lint rules whose error says the fix;
   - weekly clean-up.

   ([ImpossibleBench](https://arxiv.org/abs/2510.20270), [GitClear](https://www.gitclear.com/ai_assistant_code_quality_2025_research))
4. **Humans keep one-way-door decisions.** Agents make two-way ones fast. ([Amazon 2015 letter](https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF))
5. **Generic AI design has known tells.** Fix it with a written design direction before code, plus a screenshot critique loop. ([Anthropic frontend-design skill](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md))
6. **Agent security is structural.** Break the "lethal trifecta" (private data + untrusted content + a way to send data out). Pin MCP tool definitions. Follow the OWASP Agentic Top 10. ([Willison](https://simonwillison.net/2025/jun/16/the-lethal-trifecta/), [OWASP](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/))
7. **Scale in steps, after SLOs.** ([Google SRE](https://sre.google/workbook/implementing-slos/), [Figma](https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/))

### 27.2 What changed in engineering-os v0.4.0

| Area | Change | Where |
|---|---|---|
| Fit to the product | **Project profiles** (web-app, api, mobile, data-ml, internal-tool, cli-library, full). `eos init` asks project type plus 5 risk questions (money, personal data, LLM features, scale, low-end devices), or takes `--profile/--answers/--yes`. Unknown money or personal data → treated as yes (ASVS L2). Answers become a short *Product profile* block in `AGENTS.md`. Profiles choose skill packs; switching profile prunes unselected generated files and keeps edited ones | `core/profiles.json`, `docs/PROFILES.md`, `bin/eos.py` |
| Decisions | `decisions` pack plus `ref/decision-matrices.md`: questionnaire, then matrices for stack, database, hosting, auth, monolith vs services, mobile approach (Expo / Flutter / native / PWA / USSD), build vs buy, internal tools. Each matrix has a boring default and "switch when" conditions. Ends in an ADR and a fitness function | `packs/phases/decisions.md`, `packs/ref/` |
| Design | `design-direction` pack and `eos new design`: direction and tokens before UI code, a list of AI-generic defaults to reject, WCAG 2.2 floor, two screenshot critique rounds | `packs/phases/design-direction.md`, `core/templates/design/` |
| Mobile | `react-native-expo` and `flutter` stack packs (`ci-flutter.yml`, pre-commit). Mobile pack adds MASVS, deep links, low-data rules (small downloads, SMS/USSD fallback, cheap-Android testing), OTA rules, Maestro/Detox | `packs/stacks/`, `packs/phases/mobile.md` |
| Security | `agent-security` pack (OWASP Agentic Top 10, trifecta, MCP poisoning/rug pulls, sandboxing, injection evals). Security pack moves to OWASP Top 10:2025, ASVS 5.0 levels, LINDDUN, SLSA Build L2+, slopsquatting. `ref/security-baseline.md` covers level choice, cadence, and GDPR / Cameroon Law 2024/017 / PCI notes | `packs/phases/`, `packs/ref/` |
| Scale | `performance-scale` pack: SLOs and burn-rate alerts, an 8-step scaling ladder, capacity model, load tests, protection, cost per request, when *not* to scale | `packs/phases/performance-scale.md` |
| Data/ML | `data-ml` pack: reproducible runs, data contracts, leakage, slice evals, model cards, drift | `packs/phases/data-ml.md` |
| Harness | `eos new plan` (execution plans with progress and decision logs), seeded `docs/plans/tech-debt.md`. Architecture: fitness functions whose errors say how to fix. Code review: duplication and cross-model review. Maintenance: weekly garbage collection. WORKFLOW updated | `core/templates/plans/`, packs, `docs/WORKFLOW.md` |
| Reproducibility | `eos scaffold reproducible`: `mise.toml` (lockfile on, pins from `versions.toml`), `.devcontainer/devcontainer.json`, dev-environment doc (worktree per agent, offline tips) | `core/scaffold/reproducible/` |

### 27.3 Token numbers (same fixture and script as v0.3.0)

| Tool | Session start v0.3.0 | v0.4.0 `web-app` (default for this fixture) | v0.4.0 `api` | v0.4.0 `full` | Path rules: route / .tsx |
|---|---|---|---|---|---|
| Cursor | 1,740 | 1,889 | 1,834 | 1,941 | 2,864 / 2,241 → 2,256 |
| Cline | 1,716 | 1,865 | 1,810 | 1,917 | 2,899 / 2,262 → 2,277 |
| Claude Code | 1,763 | 1,912 | 1,857 | 1,964 | 2,899 / 2,262 → 2,277 |
| Codex | 1,716 | 1,865 | 1,810 | 1,917 | none |

The increase (+94 to +201 tokens, by profile) has two parts:

- the Product-profile block (about 50–140 tokens, by answers);
- two always-relevant skill descriptions (decisions, agent-security).

All other new content (5 packs, 2 stack packs, 2 reference files, templates) loads only on demand. Profiles keep irrelevant skills out: an API project lists 12 of the 16 skills. Cline MCP is unchanged (≈4,450 in `build`, 1,250 in `minimal`). The core-block budget moved from 1,000 to 1,100 to make room for the product block. The skill-description cap (500) holds for every profile (≤ about 410).

### 27.4 Deferred, and why

| Item | Why deferred |
|---|---|
| Per-worktree app boot plus agent-readable logs/metrics (OpenAI's pattern) | Very high leverage, but specific to each app's runtime; documented in `docs/dev-environment.md` and the research report instead of being guessed generically |
| Blueprint-style unattended runner (fixed and agent steps, isolated devbox, 2-CI-round cap) | Needs a hosted sandbox and CI integration; the retry cap and isolation rules are in the core and agent-security packs |
| Automated cross-model reviewer | Depends on which models and keys the user has; documented as a code-review rule; `eos models review` already routes the tier |
| Automatic DORA metric collection | Needs repo and CI API access per project; metrics defined in the research report |
| Native iOS/Android (Swift/Kotlin) stack packs | Expo and Flutter cover the user's likely projects first; `eos new-stack` covers the rest |
| Legal certainty on Cameroon Law 2024/017 | Summary is from the official text; commentators note an 18-month compliance window and a supervisory authority still being set up. Confirm with counsel |

### 27.5 Tests and how to adopt

- **Results:**
  - 50 unit tests, all passing (40 → 50);
  - `tests/selftest.sh --full` green, including new Expo and Flutter fixtures (init, check, pre-commit config, actionlint);
  - ruff, shellcheck, and the repo's `pre-commit run --all-files` green.
- **Not tested:**
  - building the devcontainer (no Docker on the build box);
  - running Flutter/Expo toolchains (only generated configs were validated);
  - workflows on GitHub;
  - the interactive questionnaire on a real terminal (covered by a unit test with scripted answers).
- **Existing projects:**
  - `eos update` keeps everything; pre-v0.4 projects are treated as `full`.
  - To pick a profile, run `eos init --profile <p> --answers …` once. It removes the skill packs that profile doesn't need.

## 28. Any project state, self-guiding, any repo shape (v0.5.0)

*10 October 2026. The request: make engineering-os work for projects in any state (new, existing, being rewritten, in maintenance), let it tell the user what to do next, and support every common repo shape. Sources and raw notes: `engineering-os/docs/research/v0.5-notes.md`; plain-language user guide: `engineering-os/docs/GUIDE.md`.*

### 28.1 What the research said, in plain words

1. **On an existing codebase, block new problems, not old ones.** Turning on strict lint on a messy repo fails every commit, so teams switch it off. Mature tools record today's violations as a baseline and fail only on new ones: ESLint bulk suppressions, the PHPStan baseline, Betterer, and dependency-cruiser's known-violations baseline. ([ESLint](https://eslint.org/docs/latest/use/suppressions), [PHPStan](https://phpstan.org/user-guide/baseline), [Betterer](https://phenomnomnominal.github.io/betterer/), [dependency-cruiser](https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md)) **[Verified]**
2. **Pin behaviour before you change it.** Characterization tests record what legacy code does today, so refactors don't change it by accident (Michael Feathers, *Working Effectively with Legacy Code*). **[Recommendation]**
3. **Rewrite by slices, not big bang.** The strangler fig pattern replaces a system piece by piece behind a routing layer, with parity checks, feature flags or dual-run, and a rollback path for each cutover. ([Fowler](https://martinfowler.com/bliki/StranglerFigApplication.html), [Microsoft](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)) Data changes use expand/contract. ([Fowler, parallel change](https://martinfowler.com/bliki/ParallelChange.html)) **[Verified]**
4. **Prefer a modular monolith with enforced boundaries; go to services only for a reason.** ([Fowler, MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html)) Enforce boundaries with a tool, not a wiki: [import-linter](https://import-linter.readthedocs.io/en/stable/contract_types/) (Python) and dependency-cruiser (TypeScript). **[Verified]**
5. **Services need a contract, an owner and a catalog entry.** Backstage's `catalog-info.yaml` is a widely used, tool-independent format for owner, lifecycle and APIs. ([Backstage](https://backstage.io/docs/features/software-catalog/descriptor-format)) **[Verified]**
6. **Each agent tool handles several repos differently.** Cline loads rules only from the first folder of a multi-root workspace ([Cline](https://docs.cline.bot/features/multiroot-workspace)); Claude Code loads `CLAUDE.md` files in subfolders on demand ([Claude Code memory](https://code.claude.com/docs/en/memory)); a Cursor forum report says a repo's root `AGENTS.md` can apply across a multi-root workspace ([forum](https://forum.cursor.com/t/agents-md-leaks-into-other-repositories-in-multi-repo-workspace/155477)). So eos opens the parent workspace folder first and writes path-scoped pointers. **[Verified]**
7. **BMAD has a brownfield path.** The pinned v6.12.1 uses `bmad-project-context` to document an existing project and `bmad-help` as the guide. The website documents unreleased `main`, where the hub is called `bmad`. **[Verified]** against the v6.12.1 tag.

### 28.2 What changed in engineering-os v0.5.0

| Area | Change | Where |
|---|---|---|
| Project state | Four **lifecycle modes** (greenfield, brownfield, rewrite, maintain), detected with the reason shown; `eos mode set` confirms or overrides | `bin/eos.py`, `core/lifecycle.json` |
| Existing repos | **`eos adopt`**: scans the repo, writes a project map, a baseline report and a P0/P1/P2 improvement plan. Never overwrites a file it didn't create: its version goes to `.eos/suggested/`. Existing CI stays. `adopted: true` keeps this behaviour on later updates | `docs/eos/`, `docs/plans/improvement-plan.md` |
| Gates | **Ratchet gates**: existing violations recorded in `.eos/baseline/`, only new ones fail, `--tighten` lowers the baseline as debt is paid. `eos gates strict\|ratchet` | `eos ratchet`, pre-push hook |
| Rewrites | `migration` pack plus `ref/migration-playbook.md` (strangler fig, characterization tests, parity, flags/dual-run, expand/contract data migrations, cutover and rollback runbooks); `eos new migration` | `packs/` |
| Self-guiding | **Navigator**: a phase state machine with entry and exit checks for each mode. `eos status`, `eos next` (one step, why, exact command or prompt), `eos explain <topic>`, `eos start` wizard. The core rule makes agents suggest the next step once, after a verified task only | `core/lifecycle.json`, `core/concepts.md`, `packs/phases/navigator.md` |
| Teaching | `eos teach on\|off`: agents explain decisions in one or two plain sentences and define jargon once. On by default for new projects | AGENTS.md core block |
| Topologies | Detects single app, monorepo, modular monolith, microservices and multi-repo workspace. `topology` pack and reference; `eos new service` (contract, catalog entry, AGENTS.md); `eos new module`; `eos scaffold boundaries`. Monorepos are wired per app directory | `packs/phases/topology.md`, `packs/ref/topologies.md` |
| Multi-repo | `eos workspace init\|add\|status\|sync\|change`: workspace AGENTS.md, Cursor multi-root file, Cline pointers, CLAUDE.md import, cross-repo change records with linked PRs and contract versions | `eos-workspace.json`, `docs/changes/` |

### 28.3 Token numbers (same fixture and script as v0.4.0)

| Tool | v0.4.0 → v0.5.0 `web-app` (default) | `web-app`, teaching off | `api` | `full` | Path rules: route / .tsx |
|---|---|---|---|---|---|
| Cursor | 1,889 → 2,039 | 2,009 | 1,824 → 1,974 | 1,941 → 2,155 | 2,864 / 2,256 (unchanged) |
| Cline | 1,865 → 2,015 | 1,985 | 1,800 → 1,950 | 1,917 → 2,131 | 2,899 / 2,277 (unchanged) |
| Claude Code | 1,912 → 2,062 | 2,032 | 1,847 → 1,997 | 1,964 → 2,178 | 2,899 / 2,277 (unchanged) |
| Codex | 1,865 → 2,015 | 1,985 | 1,800 → 1,950 | 1,917 → 2,131 | none |

The `api` row for v0.4.0 was re-measured from the v0.4.0 tag on this run (1,824; section 27 printed 1,834). The +150 tokens (default profile) are:

- the one-line next-step rule (~33);
- the navigator skill description (~27);
- the teaching line (~30; `eos teach off` removes it);
- on this two-app fixture, the monorepo topology block (~45).

Everything else loads only when needed: 3 new packs, 2 reference files, concepts, lifecycle and templates. Budgets: core blocks 888/1,100, skill descriptions 491/500 with every pack selected. On the adopted messy-repo fixture the AGENTS.md eos blocks are core 765, product 143, stack 156, project map 81. **[Tested]**

### 28.4 Example

After `eos adopt` on the messy-repo fixture, `eos next` prints:

```
You are here: brownfield · phase Safety net (1/4 phases done)
Next: Pin current behaviour of the most-changed files
Why: You can't change code safely without knowing what it does today; these tests catch accidental changes.
How: ask your agent: "Read docs/eos/project-map.md (hot spots). Write characterization tests that pin what the top hot spot does today (migration pack). No behaviour changes."
Guide: the agent uses the 'migration' pack for this step.
Learn the idea: `eos explain characterization-tests`
```

### 28.5 Deferred, and why

| Item | Why deferred |
|---|---|
| CODEOWNERS lines per module or service | Needs real team names; `eos scaffold codeowners --owner` covers the repo level |
| Several OpenAPI specs in `api-contract` | One spec covers most repos; services each carry their own `openapi.yaml` |
| Reliable contract-consumer detection across repos | Only a heuristic today; the user confirms it in `eos-workspace.json` |
| Claude Code nested `.claude/rules` across a workspace | Not verified, so the workspace uses the documented `CLAUDE.md` import |
| `eos workspace status --prs` | Needs the GitHub CLI and network; untested on the build box |
| Coverage ratchet, and `eos ratchet` in the user's own CI | Coverage tools differ per stack; adopt never edits existing CI, so this is an improvement-plan item |
| Skill-description headroom | 491/500 with every pack selected; the next skill must replace or shorten one |

### 28.6 Tests and how to adopt

- **Results [Tested]:**
  - 67 unit tests, all passing (50 → 67). Fixtures cover a messy repo (adopt must not clobber: `.cursorrules`, `.clinerules`, pre-commit, CI, ruff and ESLint configs, Makefile, pyproject and app code are byte-identical after adopt and after a later update; the user's AGENTS.md and CLAUDE.md text survives verbatim with eos blocks added; the `.env` secret value appears in no generated doc or output), a modular monolith, a 3-service microservices monorepo, a rewrite project and a 4-repo workspace;
  - `tests/selftest.sh --full` green;
  - ruff, shellcheck, actionlint and the repo's `pre-commit run --all-files` green.
- **Not tested:** GitHub PR linking (`--prs`), opening the workspace in each editor, and a real BMAD install run.
- **Existing eos projects:** `eos update` adds the navigator; run `eos next`. **Existing repos without eos:** run `eos adopt` (or `eos start`), then follow `eos next`.

---

## 29. Velocity audit (v0.6.0)

*10 October 2026. The request: find where this system slows a solo engineer down instead of speeding them up, and cut whatever doesn't pay for itself, while keeping every safeguard for money, auth, secrets and force pushes. Full walk-through of ten workflows, with every count: `docs/research/v0.6-velocity-audit.md` in the repo.*

### 29.1 The diagnosis in plain words
A process-heavy system rarely fails because one gate is bad. It fails because **every change pays for the worst case**. v0.5.0 asked a typo fix to do what a payment change does: run the full check before "done", update two memory files, ask the navigator for a next step, and pass a commit-message format check. Each item was cheap; together they turned a two-minute change into a ten-minute one, dozens of times a day. People respond to that by skipping the system (`--no-verify`, override labels), which removes the safety exactly where it was needed. [Recommendation]

Approval fatigue is documented: Anthropic reports that sandboxing reduced Claude Code permission prompts by 84% internally, because prompts that are almost always "yes" stop being read ([Anthropic](https://www.anthropic.com/engineering/claude-code-sandboxing)) [Verified]. DORA recommends that automated tests give feedback within minutes, with about ten minutes as an upper bound ([DORA](https://dora.dev/capabilities/continuous-integration/)) [Verified].

### 29.2 Slow-down risks, ranked
1. The same ceremony for every change, whatever its risk.
2. Cline's default MCP profile: ~4,450 tokens of tool schemas on every request.
3. Per-task agent overhead: a navigator call, two memory edits, teaching text.
4. No sanctioned escape hatch for spikes and hotfixes.
5. The full check as the definition of "done", duplicating pre-push and CI.
6. The 12-step greenfield BMAD flow presented as the default workflow.
7. The first commit failing offline (hook downloads, a remote commit-msg hook).
8. Every suppression comment blocking, which trains reflexive override labels.
9. Hook latency: ~90 ms per agent tool call, ~1 s per commit.
10. eos's generated files tripping the project's own linters.
11. The navigator blocking on `.eos-new` files, with generic steps you couldn't dismiss.
12. Too many commands (34) with no obvious daily set.

### 29.3 Risk lanes
| Lane | Detected from | Plan | Checks (`eos verify`) | Review |
|---|---|---|---|---|
| trivial | only docs, copy, translations, images | none | hooks on changed files | CI |
| standard | the default | only for multi-session work, never blocking | hooks + related tests (`vitest related`, `jest --findRelatedTests`, pytest by module name) | CI |
| risky | money/auth/crypto/PII words in paths, migrations, infra, CI, gate configs, > 20 files or > 400 lines | 5 lines; **blocking** when money, auth or security behaviour changes | full check + strict test-integrity | human, line by line, on the flagged files |
| one-way-door | a migration that drops/renames data; removed lines in an API contract | written, approved before merge, with rollback | as risky | as risky + ADR |
| spike | `spike/*` (`eos spike`) | none | none; secret/force-push/protected-path guards and gitleaks stay on | never merged (CI fails it) |
| hotfix | `hotfix/*` (`eos hotfix`) | none | as standard; full tests at pre-push | merge on green; review note next working day (`eos hotfix done`) |

[Tested] in `tests/test_eos.py` (VelocityTests) and `tests/selftest.sh`. The thresholds are [Heuristic]: tune them in `.eos/config.json`, and override a single change with a `lane:<name>` PR label (logged).

### 29.4 Before and after (measured on the same fixture, median of 15, v0.5.0 and v0.6.0 run back to back) [Tested]
| | v0.5.0 | v0.6.0 |
|---|---|---|
| Guard hook per agent tool call | 92–99 ms | 44–48 ms |
| Commit of a docs typo / a `.py` change | 966 / 979 ms | 394 / 398 ms |
| Stop check at "done" | 522 ms | 420 ms |
| "Done" check on a 60-test fixture | full check 3.8 s | standard lane 0.6–1.0 s |
| Session-start context, default profile (Cursor / Cline / Claude Code / Codex) | 2,039 / 2,015 / 2,062 / 2,015 | 1,884 / 1,860 / 1,907 / 1,860 |
| Cline per request incl. default MCP schemas | ~6,465 | ~3,110 |
| Guard corpus: benign prompted / risky asked / deny denied | 0/58, 16/17, 9/9 | 0/58, 17/17, 9/9 |

Workflow counts (counted from the rules and hooks each version installs; agent time is an estimate): a 10-minute bug fix went from 4 extra agent actions (full check, 2 memory edits, navigator) to 1 (`eos verify`); a typo from the same 4 to hooks on one file; a 1–2 day feature from a blocking plan plus ~30–45 extra actions to a non-blocking plan plus 10–15 verify runs. A risky money change keeps the same plan, checks and human review. CI wall time was not measured.

### 29.5 What was cut, and what was kept on purpose
- **Cut:** the per-task `eos next --brief` rule and the navigator skill; seeded `memory/active-context.md` and `progress.md` (git history is the progress log; `memory/handoff.md` remains for unfinished work); the remote commit-msg hook; teaching on by default; the GitHub and Context7 MCP servers on by default; suppression comments blocking outside risky lanes; `eos check` on every commit.
- **Added:** `eos lane`, `eos verify`, `eos spike`, `eos hotfix`, `eos stats` (a local event log: prompts per 100 tool calls, hook p90s, stop-check blocks, overrides, lead time), `eos next --skip`, a CI lane summary, background hook warm-up at init, `.eos/ruff.toml`.
- **Kept despite friction:** branch + PR + CI for every change; gitleaks on every commit; the force-push and secret-read denials; test-integrity blocking skips, removed asserts and lowered thresholds; pre-push type checks and tests (faster than a CI round trip on a flaky link); the stop check; the one-time init questions; money/auth plan approval and human review; one-way-door approval; cross-repo ceremony.
- **Deferred:** merging overlapping packs, an automatic coverage ratchet, CI parallelisation (needs live CI timings first), flaky-test quarantine (Google reported about 1.5% of test runs flaky: [Google Testing Blog](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)).

### 29.6 How to keep it fast
Run `eos stats` every couple of weeks. If more than 5% of tool calls ask for approval, a stop check's p90 is over 60 s, or a git hook's p90 is over 2 minutes, it prints which knob to turn. A gate that never catches anything and always costs time is a candidate for CI-only or removal; a gate that catches real problems stays, however annoying it is. [Recommendation]

## 30. The deep knowledge library (v0.7.0)

*10–11 October 2026, eleven stages. The request: give agents the depth of a senior specialist in each area (architecture, security, data, APIs, testing, operations, frontend, design, mobile, LLM apps, analytics and ML) without making every session pay for it, and turn the practices into checks wherever a machine can check them. Design: `docs/LIBRARY.md`. Status, sizes and the human review checklist: `docs/LIBRARY-STATUS.md`. Sources per area: `docs/research/v0.7-*-sources.md`.*

### 30.1 The idea: short rules always, deep knowledge on demand
Section 4 kept the always-on rules small. That leaves a gap: a pack can say "cache with a clear invalidation rule", but it cannot also teach cache stampedes, TTL jitter and when Redis is the wrong answer without blowing the budget. v0.7 organises knowledge in four layers:

| Layer | What | When it costs tokens |
|---|---|---|
| 1. Rules | phase and stack packs (≤ 1,200 tokens each) | as before (skills, path rules) |
| 2. Deep references | `packs/ref/<area>/<topic>.md`: decision guide, examples, anti-patterns, checks, sources (target ≤ 2,500 tokens) | only when a pack points to one and the agent is doing that work |
| 3. Vendored material | the best external text, pinned to a commit with licence and hashes, quarantined until a human signs off | same as layer 2, and only after sign-off |
| 4. Enforcement | `eos` gates, scaffolds, Semgrep rules, CI jobs | zero tokens: runs in hooks, `eos verify` and CI |

A pack lists its refs in one `## Deep references` section placed after "Automated checks", so the pointer is not in the edit-time path-rule slice. `eos init` installs only the refs that the selected packs point to, plus an `INDEX.md` with one "read when" line each. This works the same in Cursor, Cline, Claude Code and Codex because it is just a project-relative path. [Tested]

**Always-on context did not grow.** Session start (default `web-app` profile): Cursor 1,884, Cline 1,860, Claude Code 1,907, Codex 1,397 tokens, identical to the measurement taken just before stage 1. The Python path rule grew by 8 tokens (the words "deep references"). Measured after every stage with `tests/bench/measure_context.py`. [Tested]

### 30.2 What the library contains
134 refs, about 246,600 tokens, none of them always on:

| Area (stage) | Refs | Examples of what it teaches |
|---|---|---|
| architecture (1) | 11 + 4 | scaling stages, modular monolith, caching, consistency and outbox, event-driven, resilience, cost |
| security (2) | 13 | threat modelling, authN/authZ, OAuth/OIDC/JWT, payments, secrets, supply chain, privacy (incl. Cameroon Law 2024/017), LLM and agent security |
| data (3) | 12 | relational modelling, keys/money/time, Postgres queries, indexing, concurrency, operations, migrations, multi-tenancy |
| api (4) | 11 | contract-first, resource design, errors (RFC 9457), evolution, rate limits, webhooks, gRPC/async, GraphQL, testing |
| testing (5) | 12 | strategy, unit design, coverage of AI-written code, mutation, property and fuzz, E2E, flaky tests, load |
| ops (6) | 12 | SLOs and burn-rate alerts, dashboards, incidents and runbooks, deploy strategies, feature flags, DR, connectivity in Africa |
| frontend (7) | 12 | Next.js actions and routes, state and forms, performance, accessibility, i18n, errors and observability |
| design (8) | 12 | design tokens, colour and contrast, typography, layout, forms and copy, data visualisation, critique rubric, Cameroon context |
| mobile (9) | 12 | choosing an approach, Expo/React Native, Flutter, offline sync, unreliable networks, low-end performance, MASVS, auth and payments |
| llm (10) | 11 | choosing models, prompts and structured output, tools and MCP, RAG, agents, evals, observability, cost, privacy, multilingual |
| analytics (11) | 7 | OLTP vs OLAP, CDC vs batch ELT, DuckDB/Postgres-first, dbt, pipelines and backfills, data contracts, product events and consent, metrics, anonymisation |
| ml (11) | 5 | framing and leakage, experiments and reproducibility, serving and drift, fintech risk (fraud, credit fairness, regulation), notebooks to production |

Each ref has `verified` and `revisit_days` dates, at least two sources listed under `## Sources`, and the four required sections. `eos library lint` checks the format, the size limits, broken pointers, stale dates and injected instructions. Links were checked live when each stage was written; each research file records the results. [Tested]

**Imported text is the exception.** Most refs are original text that cites official docs, standards, peer-reviewed work and law. Eight external sources were vendored (OWASP cheat sheets, two design skill repos and others). They sit unmodified under `packs/vendor/` with licence, commit and per-file SHA-256, and `eos` never installs them until a person runs `eos vendor review`. None has been signed off; that is deliberate (section 30.5). [Verified]

### 30.3 Practices turned into checks
Where a rule can be checked mechanically, it became an `eos` gate (in-process, milliseconds, no network), a scaffold (opt-in starter files with a pinned CI job) or a Semgrep rule. Examples:
- **Testing:** `eos diff-coverage` (80% of changed lines, 90% on money/auth paths), `eos quarantine` for flaky tests with expiry (the deferred item from section 29.5), `eos test-integrity`, mutation planning and scoring.
- **Operations:** `eos ops check` (SLO file, alerts need a runbook, feature flags expire).
- **Frontend and design:** `eos i18n check`, the bundle-size ratchet, `eos design check` (token schema, WCAG contrast, generic-look lint).
- **Mobile:** `eos mobile check` (Android backup and cleartext, debuggable builds, exported components, iOS ATS, public env names) and an app-size ratchet.
- **LLM apps:** `eos llm check` (versioned prompt files, delimited untrusted input, no secrets) and `eos llm gate` (eval regressions against a baseline).
- **Data and ML:** `eos data check` (ODCS data contracts with breaking-change detection against the base branch; notebooks committed without outputs or secrets) and `eos data split` (shared customers, duplicate rows or time overlap across train and test files).

The scaffolds generate real, tested starter projects. The analytics scaffold, for example, is a dbt + DuckDB project whose 24 checks pass under dbt-core 1.12.5, and whose enforced contract fails the build when a column type changes. [Tested]

All of this respects the lanes from section 29. Trivial and spike lanes get nothing new. Standard runs the relevant gate on changed files. Risky, one-way-door and `--full` check everything. Heavy tools (dbt builds, Lighthouse, Maestro, real model evals, mutation runs) stay in CI.

### 30.4 How we know it helps, and the limit of that evidence
189 eval tasks across the 12 areas ask an agent a realistic question ("our fraud model has 0.99 AUC offline and fails in production; why?") and list the points a senior answer must cover. With the pack alone, the agent's context covers 41% of those points on average. With the pack and the refs it points to, it covers 100%. [Tested] This is an availability measure, not proof of better answers: the rubric and the refs have the same author. No agent ran live on the build box. `eos library eval tests/evals --responses DIR` scores real answers when you run the tasks with your own agents. [Recommendation]

### 30.5 What still needs a human
`docs/LIBRARY-STATUS.md` §4 is the single checklist, in priority order:
1. Security and money code to read line by line (webhook verification, CSP, every Semgrep rule set, eos's guards, money refs and the analytics reconciliation test).
2. Legal items: the repository is MIT-licensed since v0.7.1 (vendored and CC BY 4.0-adapted material keep their own licences; see `THIRD_PARTY_NOTICES.md`). The Cameroon Law 2024/017 quotes come from OCR. The credit-scoring rules (EU AI Act and Digital Omnibus dates, SCHUFA, Regulation B) and the analytics consent rules need a lawyer's eye.
3. Eight vendor sign-offs, with the exact `eos vendor review` commands. Two sources have scan findings that need `--accept-findings` with a reason. Signing off is your decision; declining and deleting the source is also fine.
4. Thresholds to confirm (coverage, SLOs, performance budgets, eval gates, split checks).
5. The design A/B test that decides whether the opt-in design studio stays (default: drop).

### 30.6 Caveats
- The refs are dated. Each one carries the day its facts were checked, and `eos library lint` warns when it is due for re-verification (60–90 days for LLM refs, 180–365 for the rest).
- No prices are recorded anywhere. Where cost matters, the refs explain the cost drivers and link the vendor's page.
- Legal content is quoted and dated, never a conclusion about your product.
- Several vendor docs pages contained instructions aimed at AI agents (for example asking agents to send telemetry or fetch extra files). All of it was treated as page data and none of it was followed. The research files list each case.
