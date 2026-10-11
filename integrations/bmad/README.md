# BMAD Method + engineering-os

BMAD gives you the **workflow and personas**: analyst, PM, architect, UX, dev, and the review and retro flows. engineering-os gives you the **standards, checks, memory and guardrails** that every one of those personas must follow. They don't compete. BMAD answers *"what do we do next?"*; the packs answer *"what does good look like, and how do we prove it?"*

## Verified facts (2026-10-09)
- Stable version: **v6.12.1**. Install with `npx bmad-method@6.12.1 install`. It needs Node ≥ 20.12 and `uv`.
- Headless install, tested and used by `eos init --bmad`:
  `npx -y bmad-method@6.12.1 install --directory . --modules bmm --tools cursor,cline --yes`
  You can list the tool ids with `npx bmad-method@6.12.1 install --list-tools`. Ids include `cursor` → `.agents/skills`, `cline` → `.cline/skills`, `claude-code` → `.claude/skills` and `codex` → `.agents/skills`.
- BMAD writes its config to `_bmad/` and its outputs to `_bmad-output/`. Overrides go in `_bmad/custom/<skill>.toml` (committed). Personal overrides go in `*.user.toml`, which is gitignored.
- Each agent has a `persistent_facts` array. Entries can be sentences or `file:` references (globs allowed). Override arrays **append** to the defaults. The merge was verified with `_bmad/scripts/resolve_customization.py`.
- The `main` branch and website describe an unreleased Skills-CLI flow (`npx skills add …`). Stay on the pinned stable version until it ships; the pin lives in `versions.toml`.

## How they connect
| BMAD step (skill) | Persona | eos pack(s) loaded via `persistent_facts` | Output location |
|---|---|---|---|
| `bmad-brainstorming`, `bmad-forge-idea` | Mary | ideation (skill) | `docs/ideas/` or `_bmad-output/` |
| `bmad-product-brief`, `bmad-prfaq`, `bmad-deep-recon` | Mary | discovery | `_bmad-output/planning-artifacts/` |
| `bmad-prd`, `bmad-spec`, `bmad-create-epics-and-stories` | John | requirements | same |
| `bmad-ux` | Sally | ux-design | same |
| `bmad-architecture` | Winston | architecture (data-modeling and api-design load as skills when needed) | same + `docs/adr/` |
| `bmad-sprint-planning`, `bmad-build`, `bmad-build-auto` | Amelia | none injected: stack, testing and backend/frontend packs attach by file path (injecting them too would load them twice) | code + tests |
| `bmad-code-review`, `bmad-review` | n/a | code-review (skill), security | PR comments |
| `bmad-retrospective` | n/a | then run **eos-retro** to turn lessons into checks | `docs/ai/lessons.md` |
| `bmad-project-context` | n/a | writes `<!-- bmad:context -->` into AGENTS.md "Project specifics" (eos never touches that part) | AGENTS.md |

The override files are in `custom/`. `eos init --bmad` installs BMAD and seeds them (once; after that they're yours).

## Existing code (brownfield) and "what next?"
- Run `eos adopt` first: it maps the repo, baselines the linters (ratchet) and writes an improvement plan without overwriting your files.
- Then run `bmad-project-context` to set up (or audit) the verified agent instructions for the existing codebase. Older ids such as `bmad-generate-project-context` still forward to it; use the current name ([BMAD: project context](https://docs.bmad-method.org/explanation/project-context/), [skills and agents](https://docs.bmad-method.org/reference/skills-and-agents/)).
- In the pinned v6.12.1, `bmad-help` shows BMAD's own view of the next skill. The website already documents the unreleased `main`, where the hub is called `bmad`; trust the skills installed in your repo. `eos next` shows the eos view (phase exit criteria, gates, blockers) and names the BMAD skill for planning steps when `_bmad/` is installed. They agree on product steps; eos adds the safety steps (ratchet, characterization tests, parity).
- For a change to existing code, `bmad-correct-course` re-plans when a story turns out bigger than expected.

## Rules of engagement
1. **Pick the track by risk, not by mood.**
   - Quick Flow is for small changes.
   - BMad Method is for features.
   - Enterprise is for regulated or high-risk work. Anything that touches money is at least BMad Method.
2. **A story is one `bmad-build` session.** Keep it around 500 changed lines or fewer. If it grows, split it, or run `bmad-correct-course`.
3. **"Done" is decided by commands, not personas.** Amelia's own checklist doesn't count until the AGENTS.md **full check** is green and `eos test-integrity` is clean.
4. **`bmad-build-auto` needs subagents.** Start with "Halt after planning" and review the plan before letting it build.
5. **Review happens in a fresh context.** Run `bmad-code-review` or `bmad-review` in a new chat, or use a different model, never in the session that wrote the code.
6. **Update BMAD deliberately:** bump the pin, run the installer in a branch, run `eos check`, and commit.
