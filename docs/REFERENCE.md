# Reference: files, commands, repo layout

The README covers the why and the quick start. This page lists everything else.

## What `eos init` puts in a project
| Path | What it is | Owner |
|---|---|---|
| `AGENTS.md` | Core rules plus the stack/commands table and a two-line pointer to `.eos/packs/INDEX.md` (eos-managed blocks), and your *Project specifics* section | eos blocks are managed; the rest is yours |
| `.eos/packs/{phases,stacks}/*.md`, `.eos/packs/core.md` | Canonical pack copies (the single source of truth in the project) | managed; edits are allowed and are kept on update |
| `.eos/bin/eos.py`, `.eos/bin/hook.py` | Vendored CLI used by hooks, pre-commit and CI (stdlib only); `hook.py` is the fast entry point for agent hooks | managed |
| `.eos/ruff.toml` | Makes your own `ruff check .` skip eos's generated files | managed |
| `.eos/protected.txt`, `.eos/config.json` | Paths agents may not edit; hook settings (loop limit, stop check) | yours |
| `.cursor/rules/eos-*.mdc`, `.agents/skills/eos-*` | Cursor adapters: glob-attached rules plus on-demand skills (Codex also reads `.agents/skills`) | generated |
| `.clinerules/eos-*.md`, `.cline/skills/eos-*` | Cline adapters (`paths:` rules plus skills) | generated |
| `.claude/rules/eos-*.md`, `.claude/skills/eos-*`, `CLAUDE.md` | Claude Code adapters (`CLAUDE.md` imports `@AGENTS.md`) | generated |
| `.cursor/hooks.json`, `.clinerules/hooks/PreToolUse`, `.claude/settings.json` | Guard hooks: shell policy, secret files, protected paths, loop guard, stop check | merged (your entries are kept) |
| `memory/handoff.md`, `docs/adr/`, `docs/ai/lessons.md`, `docs/plans/tech-debt.md` | Project memory: handoff (only when work stops unfinished), ADRs, lessons, tech-debt tracker. Git history is the progress log. | yours (seeded once) |
| `docs/spikes/`, `docs/incidents/` | Notes written by `eos spike done` / `eos hotfix done` from the branch's git history | yours |
| `.eos/state/events.jsonl` | Local, git-ignored log read by `eos stats` | local |
| `.eos/packs/ref/*.md` | Reference files read on demand by packs: decision matrices, security baseline (levels, cadence, compliance) | managed |
| `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/{story,bug}.yml` | PR template (AC → test map, risk boxes, AI-assistance note) and story/bug forms | yours (seeded once) |
| `.pre-commit-config.yaml`, `.github/workflows/eos-core.yml`, `ci-<stack>[-<dir>].yml`, `.github/renovate.json` | Quality gates (one CI workflow per app dir in a monorepo) | managed until you edit; then you get `.eos-new` |
| `.eos/lifecycle.json`, `.eos/concepts.md` | Phase state machine read by `eos status`/`eos next`; explanations for `eos explain` (never loaded into agent context) | managed; edit to adapt |
| `.eos/ratchet.json`, `.eos/baseline/*.json` | Ratchet gates: which linters, and the recorded old violations (commit both) | yours / written by `eos ratchet` |
| `docs/eos/project-map.md`, `docs/eos/baseline-report.md`, `docs/plans/improvement-plan.md` | Written by `eos adopt`: map for agents, measured baseline, prioritised plan (P0/P1/P2) | reports are refreshed; the plan is yours |
| `.eos/suggested/` | `eos adopt` only: eos's version of a file you already had, for you to compare | yours to delete |
| `docs/architecture/{services,modules}.md` | Service or module catalog, seeded from what was detected | yours (seeded once) |

"Managed" means `eos update` replaces the file *only if you haven't edited it*. If you have, it writes `<file>.eos-new` next to it for you to merge by hand.

## Commands
| Command | Use |
|---|---|
| `eos bootstrap [--tools …] [--global-hooks] [--install-clis] [--dry-run]` | Machine setup. Safe to re-run. |
| `eos init [DIR] [--profile web-app\|api\|mobile\|data-ml\|internal-tool\|cli-library\|full] [--answers k=v,…] [--yes\|--interactive] [--stacks auto\|none\|id:dir,…] [--tools …] [--bmad] [--dry-run]` | Add eos to a project. The questionnaire picks packs, gates and the security level ([docs/PROFILES.md](PROFILES.md)). Re-run to switch profile. |
| `eos start [DIR] [--yes]` | First time? Asks what you are doing (new idea, existing code, rewrite, live product, several repos) and runs the right command, then shows the next step. |
| `eos adopt [DIR] [--scan-only\|--report-only] [--no-baseline] [init options]` | Existing project: scan (languages, frameworks, commands, CI, lint configs, agent rules, tests, dependencies, git hot spots), write the project map, baseline report and improvement plan, install eos **without overwriting any file you had**, gates in ratchet mode. |
| `eos next [DIR] [--brief] [--json] [--skip\|--unskip]` · `eos status [DIR]` | The one next step with its reason and command/prompt (blockers first; `--skip` drops a step you don't need, recorded). `status` shows the whole picture. |
| `eos lane [DIR] [--base REF] [--labels lane:<x>] [--json] [--ci]` | Classify the change from its diff: trivial (docs/copy), standard, risky (money, auth, crypto, PII, migrations, infra, CI, large diff), one-way-door (dropped data, removed contract lines); `spike/*` and `hotfix/*` branches have their own lane. Overrides are logged. In CI it writes the job summary and fails only spike PRs. |
| `eos verify [DIR] [--full] [--dry-run]` | The one check command: hooks on changed files; plus related tests (pytest by module name, `vitest related`, `jest --findRelatedTests`) for standard; plus the stack's full check and test-integrity for risky and one-way-door. Parallel across app dirs. |
| `eos spike <name>\|done` · `eos hotfix <name>\|done [--no-fetch]` | Escape hatches. Spike: throwaway branch, stop check off, guards on, CI refuses to merge it; `done` writes a lesson note. Hotfix: branch from `origin/main` (15 s fetch timeout), minimal steps, `done` writes a post-hoc review note with the git timeline. |
| `eos stats [DIR] [--days 30] [--json]` | Self-metrics from the local log: agent hook calls and latency, approval prompts by reason, stop-check and verify durations, git hook durations, escapes, lead time from merge commits; with tuning tips. |
| `eos explain [topic]` | Plain-language explanation of a principle (ratchet, strangler-fig, parity, modular-monolith, workspace, …) with sources. |
| `eos mode [set <mode>]` · `eos topology [set <shape>]` · `eos teach on\|off` · `eos gates strict\|ratchet` | Show or change the lifecycle mode (greenfield, brownfield, rewrite/refonte, maintain), repo shape, teaching mode, and gate style. |
| `eos ratchet [check\|init\|add <name> "<cmd>"\|update] [--tighten] [--strict]` | Baseline current lint/type/boundary violations and fail only on new ones; tighten as counts drop. |
| `eos workspace init\|add\|status\|sync\|change "<title>"` | Multi-repo workspace: map of repos, contracts and owners for agents, editor workspace file, cross-repo change plans with merge order. |
| `eos update [DIR]` | Refresh packs and templates from this repo into a project. |
| `eos sync [DIR] [--check]` | Regenerate adapters from `.eos/packs`, or (with `--check`) report drift. |
| `eos check` | Project gate: budgets, drift and frontmatter. Runs in CI, and in pre-commit only when agent-context files change. |
| `eos test-integrity [--base origin/main] [--strict]` | Flags new skips, removed asserts, lowered thresholds and gate edits (these block). New suppression comments block only in risky lanes or with `--strict`; elsewhere they warn. Runs in CI. |
| `eos budget [DIR]` | Token budget report. |
| `eos detect [DIR]` | Shows which stack packs would be used. |
| `eos new-stack <id> --markers go.mod --globs "**/*.go"` | Scaffold a new stack pack. |
| `eos doctor [DIR]` | Machine + project health. Every problem line ends with the command that fixes it. |
| `eos mcp list\|status\|use <profile\|phase> [--tools cline]` | Per-task MCP profiles (minimal, build, review, api, design, debug-ui, off) with the measured Cline token cost. |
| `eos models [task] [--failures N] [--check] [--usage]` | Model routing by task tier (premium / strong / cheap) from `personal/models.toml`; `--check` verifies ids and prices live on OpenRouter; `--usage` compares spend with your caps. |
| `eos new adr\|story\|plan "<title>"`, `eos new design` | Numbered ADR (plus INDEX line), story, or execution plan (`docs/plans/active/`); `design` writes `docs/design/direction.md` (design direction before UI code). |
| `eos new migration "<name>"` · `eos new service <name> [--owner]` · `eos new module <name>` | Rewrite pack: plan, parity report, data-migration plan, cutover and rollback runbooks plus `tests/characterization/`. Service: README, OpenAPI contract, Backstage `catalog-info.yaml`, AGENTS.md, catalog row. Module: public API file and catalog row. |
| `eos scaffold list\|<kind>` | Opt-in starter files, written once: release, security, api-contract, codeowners, compose, docker-python, docker-node, tests-python, e2e-node, reproducible (mise + devcontainer), boundaries (import-linter / dependency-cruiser module rules). |
| `eos uninstall [DIR] [--force]` | Removes what eos generated; keeps files you edited, memory, docs and scaffolds. |

## Layout of this repo
```
bin/eos.py                 the whole CLI (Python ≥3.10, stdlib only)
core/AGENTS.core.md        always-on rules (≤1.8k tokens with the generated map)
core/templates/            AGENTS.md, CLAUDE.md, memory/, ADR, story, plan, design direction, lessons, renovate, .github seeds
core/profiles.json         project profiles (+ by_mode, by_topology) → skill packs, scaffolds, MCP profile (docs/PROFILES.md)
core/lifecycle.json        modes → phases → exit criteria (eos status / next) · core/concepts.md (eos explain)
core/scaffold/             opt-in starter files for `eos scaffold`
core/pre-commit/base.yaml  stack-agnostic hooks · core/ci/eos-core.yml · core/protected.txt
packs/phases/*.md          25 phase packs (entry → standards → deliverables → checks → DoD → handoff → stop)
packs/stacks/<id>/         STACK.md + pre-commit.yaml + ci.yml  (python, python-fastapi, python-flask,
                           typescript, nextjs, react-native-expo, flutter, _template)
packs/ref/*.md             on-demand reference: decision matrices, security baseline, migration playbook, topologies
personal/PROFILE.md        generic profile template; your own goes in PROFILE.user.md (git-ignored, ≤400 tokens) · personal/skills/ (retro, handoff, new-stack)
personal/models.toml       model routing tiers + budget caps (override in models.user.toml, git-ignored)
mcp/servers.json           canonical MCP list + profiles (no secrets) · secrets.env.example · README
integrations/bmad/         BMAD v6 integration notes + _bmad/custom overrides
git-hooks/                 global hook dispatcher (gitleaks everywhere + per-repo pre-commit)
tests/                     unittest suite + selftest.sh (end-to-end) + fixtures/ (messy repo, 4-repo workspace)
                           + bench/ (hook latency bench, guard false-positive corpus, results per version)
versions.toml VERSION CHANGELOG.md docs/
```

## Versioning
- This repo uses SemVer in `VERSION`. A pack wording fix is a patch. A new pack, rule or check is a minor. A changed file layout or command is a major. Tag releases with `git tag -a vX.Y.Z`.
- Every project records the eos version and file hashes in `.eos/manifest.json`. `eos update` is the only path for upgrades and never silently overwrites your edits.
- Tool pins live in one place, `versions.toml`. Renovate (seeded in each project) keeps project-level pins fresh.
