# Daily workflow

Read on demand; nothing here is loaded into agent context.

## The golden path (most work, every day)
1. Branch: `git switch -c fix/<name>` (or `eos spike` / `eos hotfix`, below).
2. Ask the agent for the change. It sizes the process with `eos lane` and checks with `eos verify`.
3. Commit (hooks check only the changed files, well under a second on the bench fixture), push (type checks and tests run at pre-push only if that stack's files changed), open a PR, merge on green CI (`gh pr merge --auto --squash` lets you walk away).

What changes with the lane (`eos lane` prints it; CI writes it in the job summary):

| Lane | Detected from | Plan | Checks (`eos verify`) | Review | Typical extra time |
|---|---|---|---|---|---|
| trivial | only docs, copy, translations, images (not agent rules) | none | hooks on the changed files | CI; self-merge | none |
| standard | everything else | only for multi-session work (`eos new plan`) | hooks on changed files + related tests + flaky-quarantine expiry + ops config (SLOs, alerts, flags) when present + translation completeness when catalogs exist + design tokens/contrast/generic-look lint on changed UI or token files | CI; optional self-review | seconds |
| risky | money/auth/crypto/PII words in paths, migrations, infra, CI, gate configs, or > 20 files / > 400 lines | 5 lines in the PR; approved first if money, auth or security behaviour changes | + the stack's full check + test-integrity + changed-line coverage (from a fresh report) + hadolint on changed Dockerfiles (when installed) + client bundle ratchet (from a fresh build) + design lint over the whole repo; CI mutation-tests changed money/auth code | a human reads the flagged files line by line; fresh-session AI review recommended | the review |
| one-way-door | a migration that drops/renames data, removed lines in an OpenAPI/proto/GraphQL contract | written, approved before merge, with rollback or forward-fix | as risky | as risky, plus an ADR | the approval |
| spike | branch `spike/*` (`eos spike <name>`) | none | none (stop check off; secret, protected-path and force-push guards on) | never merged: CI fails spike PRs | none |
| hotfix | branch `hotfix/*` (`eos hotfix <name>`) | none | as standard; full tests at pre-push | merge on green CI; post-hoc review note (`eos hotfix done`) within a working day | the next-day review |

Tune it in `.eos/config.json`: `"lanes": {"risky": ["src/pricing/**"], "trivial": ["content/**"], "risk_words": ["tariff"], "large": {"files": 30, "lines": 600}}`. A PR label `lane:<name>` overrides one change (logged). Measure before and after any tuning with `eos stats`.

## Building a new product (greenfield): the full flow
Use this only when you are creating a product or a large epic; a bug fix or a feature in an existing product follows the golden path above. Each step names what goes in, what comes out, and the command that checks the handoff. Skip any step you don't need with `eos next --skip`.

| # | Step | Who / tool | Model tier (`eos models`) | MCP profile (`eos mcp use`) | Output | Handoff check |
|---|---|---|---|---|---|---|
| 1 | Idea / brief | BMAD analyst (`bmad-product-brief`) or chat | premium | minimal | `_bmad-output/planning-artifacts/brief.md` | claims tagged fact/assumption |
| 2 | PRD | BMAD PM (`bmad-prd`) | premium | minimal | PRD with AC-n ids and numeric NFRs | a human confirms every money/state rule |
| 3 | Decisions + architecture | eos-decisions skill (questionnaire + matrices in `.eos/packs/ref/decision-matrices.md`), then BMAD architect | premium | build | ADRs for stack, DB, hosting, auth, services, mobile approach; architecture doc | a human approves each one-way-door ADR; fitness function recorded |
| 4 | Design direction + UX (if UI) | `eos new design` + eos-design-direction skill, then BMAD UX + Figma | premium | design | `docs/design/direction.md`, tokens, one critiqued reference screen, flows and states | no rejected AI default without a reason; 2 screenshot critique rounds; every screen has empty/loading/error states |
| 5 | Stories | BMAD (`bmad-create-epics-and-stories`) or `eos new story "<title>"` | strong | minimal | story files with AC-n | each story ≤ ~500 changed lines, risk area named |
| 6 | Plan | agent in plan mode (Cline Plan, Cursor/Claude plan); `eos new plan "<title>"` for multi-session work | premium | minimal | goal, files, risks, checks (+ progress and decision log in `docs/plans/active/`) | risky and one-way-door lanes (core rule 1); a bad result → revert and re-plan, don't patch |
| 7 | Implement | agent in act mode (`bmad-build`) | strong | build (api / design / debug-ui as needed) | code + tests named after AC ids | stop hook: fast check green before the agent may stop |
| 8 | Self-check | same session | strong | build | full check output, one line per check | `eos test-integrity` clean; nothing weakened |
| 9 | Review | risky lanes: **fresh session**, different model if you can (`bmad-code-review`, eos-code-review skill) | premium | minimal | review notes, fixes | human reviews the files `eos lane` flags, line by line |
| 10 | PR | `gh pr create` (template fills itself) | cheap | review | PR with AC → test map and risk boxes | CI: eos-core, ci-<stack>, security, api-contract |
| 11 | Merge + release | release-please (`eos scaffold release`) | n/a | n/a | release PR → tag → GitHub release + CHANGELOG | conventional commits enforced by the commit-msg hook |
| 12 | Retro | `bmad-retrospective`, then the eos-retro skill | strong | minimal | a check (preferred) or one lesson line | `eos check` stays within budgets |

Not sure where you are in this table? Run `eos next`. It reads the project (mode, phase, files present, gate results, stories, git) and prints the one next step, why, and the exact command or agent prompt. `eos status` shows the whole picture. Agents don't call it on their own (that cost a tool call per task); ask them "what next?" and they will. MCP stays on the `minimal` profile; agents use the `gh` CLI for issues and PRs. Switch profiles only for work that needs a specific server: `eos mcp use design` for Figma plus a localhost browser (screenshots, axe), `debug` for a read-only look at your **local** database (schema, EXPLAIN, health), `debug-ui` for the browser alone. In Cline the bigger profiles cost tokens on every request, so switch back to `minimal` afterwards. For design work you can also turn on the opt-in design studio (`eos studio on`, after a human signs off its sources): extra catalogs and a sandboxed anti-pattern scanner read only on demand. It adds nothing at session start and nothing to the lanes or hooks above; `eos design check` stays the gate. Whether it is worth keeping is decided by `eos design ab` (`docs/research/v0.7-design-studio.md`).

## The flow depends on the project's state (lifecycle mode)
The table above is the **greenfield** flow. `eos mode` shows the mode; `eos mode set <mode>` changes it. The phases and their exit criteria live in `.eos/lifecycle.json`.

| Mode | Phases (exit criteria in `.eos/lifecycle.json`) | Gates | Key commands |
|---|---|---|---|
| **greenfield**: new idea | ideate → discover → define → design (if UI) → architect → build → ship → operate | strict | `eos start`, `eos new story`, `eos new adr` |
| **brownfield**: existing code | adopt (map + plan) → safety net (ratchet baseline, characterization tests on hot spots) → stabilise (P0/P1 items) → evolve | ratchet | `eos adopt`, `eos ratchet check`, `eos ratchet update`, then `eos gates strict` when counts reach zero |
| **rewrite** (refonte, re-platform) | decide (plan, seam, ADR) → safety net (golden-master tests) → slice by slice (flag, shadow, canary, live; parity evidence) → cutover (rehearsed rollback) → decommission | ratchet or strict | `eos new migration "<name>"`, `eos explain strangler-fig` |
| **maintain**: live, mature product | operational baseline (SLOs, runbooks) → steady state (small flagged releases, debt paid down) | strict | `eos explain slo`, `eos explain feature-flags` |

### Adopting existing code, step by step
1. `eos adopt --scan-only`: see what eos found (stacks, mode, shape, your agent rules and lint configs) before anything is written.
2. `eos adopt`: installs eos. Your files are never overwritten: where eos would have written a file you already have, its version goes to `.eos/suggested/`. Your `AGENTS.md` keeps its text; eos adds marked blocks. Your `CLAUDE.md` gets a one-line `@AGENTS.md` import. Your CI stays yours (eos adds only `eos-core.yml`).
3. Read `docs/eos/baseline-report.md` and `docs/plans/improvement-plan.md`. Commit on a branch.
4. Add `python3 .eos/bin/eos.py ratchet check` to your CI (the plan says where). From now on new code must be clean; old violations are tracked, not blocking.
5. Work the plan top-down, one item per PR. `eos next` always points at the first open item. After a clean-up PR, `eos ratchet update` locks in the lower count.

### Cross-repo changes (multi-repo workspace)
1. `eos workspace change "<title>" --repos contracts,api,web` writes `docs/changes/NNNN-<slug>.md`: the same branch name for every repo and the merge order (contracts and providers first).
2. Change the contract additively; check it with `oasdiff breaking` / `buf breaking` / consumer contract tests.
3. One PR per repo, each linking the plan and the others ("Part of change NNNN; depends on org/api#12"). `eos workspace status --prs` shows them side by side.
4. Merge in order; roll back in reverse order.

## When to plan, act, escalate
- **Act directly**: trivial and standard lanes (rename, small fix, copy change, most features).
- **Plan first**: risky and one-way-door lanes (core rule 1). The agent waits for your approval when money, auth or security behaviour changes, or the change is a one-way door. Plan in a premium model; implement in a strong one (Cline: Settings → "Use different models for Plan and Act", [docs](https://docs.cline.bot/core-workflows/plan-and-act)).
- **Escalate** after two failed attempts at the same problem: switch up a tier (`eos models debug --failures 2` prints which), or start a fresh session with `memory/handoff.md`. After three failed fixes the stop hook makes the agent write the handoff and ask you.
- **Recover**: `git stash` or a new branch from the last green commit beats asking an agent to undo its own work. Small commits make this cheap.

## Garbage collection (weekly, 20 minutes)
AI copies existing patterns, including bad ones. Once a week, ask an agent for small clean-up PRs: duplicated code, dead code, stale docs, violations of your golden principles. When the same issue keeps coming back, turn it into a lint rule or structural test whose error message says how to fix it. Track the rest in `docs/plans/tech-debt.md`.

## Parallel agents and worktrees
- One agent per git worktree: `git worktree add ../proj-refunds -b feat/refunds`. Each worktree has its own working files and `.eos/state/`, so hooks and the loop guard do not collide.
- Give parallel agents disjoint files (one story each). Merge through PRs, never by copying between worktrees.
- Cloud/background agents: same rules. They open a PR; the PR gates and a human review apply unchanged. Never give them deploy or production credentials.
- `eos init` is per repository, not per worktree: worktrees share the committed `.eos/` files.

## Evaluating the system itself (monthly, 30 minutes)
1. Keep 3–5 **golden tasks** in `docs/ai/evals.md`: a real small story, a bug with a known fix, a review of a known-bad diff. Note the expected outcome.
2. Run them after changing packs, models or MCP profiles. Record: passed checks first time? how many turns? did the review catch the planted bug? tokens/cost from OpenRouter (`eos models --usage`).
3. A regression means revert the pack/model change or add a check. Record the result in `docs/ai/evals.md`.
4. Run `eos stats` too: approval prompts per 100 tool calls, stop-check p90, git-hook p90 and override counts tell you which gate costs more than it catches.

## Memory hygiene
- Git history (small commits, clear messages) is the progress log. Agents don't keep a separate one.
- `memory/handoff.md` is the only file an agent reads at the start of resumed work, and it exists only while work is unfinished: delete it when that work is done.
- Projects from before v0.6 may still have `memory/active-context.md`; `eos doctor` warns when it is stale. Delete it if nobody updates it.
- Lessons that repeat become checks (eos-retro), then the lesson line is deleted.
