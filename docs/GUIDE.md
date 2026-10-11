# A plain-language guide to engineering-os

This guide is for you if you build software with AI tools but don't know (or don't want to memorise) the engineering principles behind the steps. You don't need to read anything else to start. Each section ends with the command that does the work.

Not set up yet, or on a new computer? Start with [NEW-MACHINE.md](NEW-MACHINE.md) (install, keys, Cline, first check), then come back here.

## 1. What eos does, in one minute
AI coding agents are fast but forgetful. They don't know your project's rules, they repeat mistakes, and they say "done" before anything is checked. eos gives every agent you use (Cursor, Cline, Claude Code, Codex) the same short rules, loads detailed guidance only when it's needed, checks the work automatically, and tells **you** what to do next.

`eos start` sets a folder up the first time. After that, five commands cover a normal day:

| Command | What it does |
|---|---|
| `eos next` | Where you are, the one next step, why it matters, and the exact command or the sentence to give your agent. `eos next --skip` if you don't need that step. |
| `eos verify` | Runs the checks this change needs, and no more. Your agent runs it too before saying "done". |
| `eos lane` | How risky the change is (see section 3) and what that means for planning, checks and review. |
| `eos spike <name>` / `eos hotfix <name>` | The two escape hatches: a throwaway experiment, or an urgent production fix. |
| `eos stats` | How much time eos itself is costing you, so you can tune it with numbers instead of guesses. |

`eos explain <topic>` explains any idea in plain words; `eos status` shows the full picture.

## 2. Which situation are you in?
Projects are in one of four situations (eos calls them **modes**). eos guesses yours from the folder and tells you why. You can always correct it with `eos mode set <mode>`.

**A new idea (greenfield).** Little or no code yet. The steps go in order: write the idea down → check the riskiest assumptions → agree what version 1 does (requirements) → sketch the screens (if there are any) → choose the simplest structure and write down the big decisions → build in small stories → release → watch it in production. Skipping ahead is the classic way to build the wrong thing well.
→ `eos start`, then `eos next` after every step.

**Existing code you're taking over (brownfield).** The order is: map it, measure it, put a safety net under it, then improve it in small slices. `eos adopt` does the first two **without changing any of your files**: your rules and configs stay as they are. Where eos would have written a file you already have, it puts its version in `.eos/suggested/` for you to compare. It writes three short documents: a project map (for agents), a baseline report (the numbers today) and a prioritised improvement plan.
→ `eos adopt`, then `eos next`.

**Replacing or re-platforming a system (rewrite, "refonte").** Rewriting everything at once is famously risky. eos follows the *strangler fig* pattern: put a switch point (the "seam") in front of the old system, move one thin slice at a time behind a feature flag, prove each slice behaves the same (parity), and only switch off the old path with a rehearsed way back (rollback).
→ `eos start` (choose rewrite) or `eos new migration "<name>"`, then `eos explain strangler-fig`.

**A live product you keep running (maintain).** The main risk is breaking what users rely on. eos asks for targets for what users feel (SLOs), a written procedure for the likely incidents (runbooks), and small, reversible releases.
→ `eos mode set maintain`, then `eos next`.

## 3. Lanes: the process fits the risk
A typo and a payment change should not go through the same process. eos looks at what you changed and puts it in a **lane**:

| Lane | Examples | What it means |
|---|---|---|
| trivial | docs, copy, translations, images | Just make the change. Hooks check the changed files; no new tests, no plan. Merge when CI is green. |
| standard | most code changes | Make the change; `eos verify` runs the hooks plus the tests related to the files you touched. A plan only for work that spans several sessions. |
| risky | money, logins, permissions, personal data, database migrations, infrastructure, CI, or a very large diff | A five-line plan first (you approve it when money, logins or security behaviour change); `eos verify` runs the full check; you review the flagged files line by line. |
| one-way door | dropping a column or table, removing something from a public API | Hard or impossible to undo. You approve the written plan before merge, it gets an ADR (decision note) and a way back or forward. |

Two more lanes come from the branch name:
- **Spike** (`eos spike try-redis`): you want to learn something fast and throw the code away. No tests, plans or docs; the agent's stop check is off; secrets and force-push protection stay on. CI refuses to merge a spike branch, so experiments can't leak into production. `eos spike done` writes a short "what we learned" note.
- **Hotfix** (`eos hotfix login-500`): production is broken. A branch from the latest `main`, the smallest fix plus a test that catches the bug, `eos verify`, a pull request labelled `hotfix`, merge when CI is green. The review happens the next day: `eos hotfix done` writes the review note with the timeline from git. Money and login changes are still flagged for a second person.

eos guesses the lane from the paths and the size of the diff. If it's wrong, a `lane:<name>` label on the pull request (or `EOS_LANE=<name>`) overrides it, and the override is logged.

## 4. The ideas behind the steps
You will see these words in `eos next`. Each has a longer explanation in `eos explain`.

- **Done means checked.** An agent's "done" counts only when the project's checks pass (tests, lint, types). The agent runs them itself and shows you one line per check. `eos explain definition-of-done`
- **Small, reversible steps.** Small changes are easy to review and easy to undo. Risky ones go behind a feature flag so they can be switched off in seconds. `eos explain feature-flags`
- **Safety net before change.** Before changing code nobody fully understands, record what it does today with tests (*characterization tests*). Then any accidental change shows up as a failing test. `eos explain characterization-tests`
- **The ratchet.** On existing code, eos records today's lint and type errors as a *baseline*. New code must be clean; old problems don't block you. When the count goes down, the baseline goes down with it, and it can never go back up. `eos explain ratchet`
- **Decisions are written down.** A one-page note per big decision (an *ADR*) stops every new session from re-arguing it. `eos explain adr`
- **Humans review the risky parts.** Money, logins, personal data, database migrations and infrastructure always get a human reviewer, however good the agent is.
- **Less context, better answers.** Agents read their instructions on every request. eos keeps the always-on part short (about 1,900 tokens) and loads the rest only when a matching file is touched or a matching task comes up. `eos explain packs`

## 5. The shape of your code
eos also detects the **shape** of your repository and adapts the checks:

| Shape | What it is | When it fits |
|---|---|---|
| Single app | One app in one repo | Most projects start here |
| Monorepo | Several apps or packages in one repo | A web app and an API built together; eos wires checks and CI per app |
| Modular monolith | One app split into modules with enforced boundaries | **The recommended default** when the app grows: most of the benefits of services without the running costs. `eos explain modular-monolith` |
| Microservices | Separately deployed services that talk through contracts | Different teams or very different scaling needs. `eos explain microservices` |
| Multi-repo workspace | Several separate repos that belong together | `eos workspace init` in the parent folder gives agents a map of how the repos relate. `eos explain workspace` |

Correct a wrong guess with `eos topology set <shape>`.

## 6. What a normal session looks like
1. Open the project in your editor. Ask your agent for the task, or run `eos next` if you don't know what the task should be.
2. The agent works. Small changes it just makes. For risky ones it shows a short plan first, and waits for you when money, logins or security are involved.
3. Before saying done, it runs `eos verify`. If the checks fail three times, it stops, writes a short handoff note (`memory/handoff.md`) and asks you.
4. You commit on a branch and open a pull request; CI runs the full checks.

The agent doesn't suggest a next step after every task any more (that cost a tool call and tokens each time). Ask "what next?" and it runs `eos next` for you.

Example (`eos next` on an existing project, right after `eos adopt`; the last two lines appear with `eos teach on`):

```
You are here: brownfield · phase Safety net (1/4 phases done)
Next: Pin current behaviour of the most-changed files
Why: You can't change code safely without knowing what it does today; these tests catch accidental changes.
How: ask your agent: "Read docs/eos/project-map.md (hot spots). Write characterization tests that pin what the top hot spot does today (migration pack). No behaviour changes."
Guide: the agent uses the 'migration' pack for this step.
Learn the idea: `eos explain characterization-tests`
```

## 7. Teaching mode
Off by default (it makes every answer longer). `eos teach on` makes agents explain each decision in one or two plain sentences (which principle, and why it applies here) and define a term the first time they use it. `eos teach off` makes them terse again. It changes one line in `AGENTS.md`.

## 8. When something goes wrong
| You see | What it means | What to do |
|---|---|---|
| `Note: Merge 1 eos update(s) waiting next to your files` | You edited a file eos manages; the new version is in `<file>.eos-new`. It never blocks you. | When convenient: compare the two, keep what you want, delete the `.eos-new`, run `eos sync` |
| `eos next` keeps suggesting a step you don't need | The phase checklist is generic | `eos next --skip` (undo with `--unskip`) |
| The lane is wrong | The guess uses paths and diff size | PR label `lane:<name>`, or add paths to `lanes` in `.eos/config.json` |
| Commits or the agent feel slow | Something in the checks is expensive | `eos stats` lists the slow parts with a tip for each |
| `ratchet found new violations` | The change added a lint/type problem that wasn't there before | Fix only the new ones listed. Old ones can wait. |
| `Resume the unfinished work in memory/handoff.md` | An agent stopped mid-task and left notes | Ask the agent to continue from the note, or delete it if the work is abandoned |
| `Move your changes off 'main' to a branch` | You have uncommitted work on a protected branch | `git switch -c feat/<name>`, then commit |
| The mode or shape is wrong | Detection is a guess | `eos mode set <mode>` / `eos topology set <shape>` |

## 9. Where to go next
- `docs/WORKFLOW.md`: the full flow for each mode, with the command at every handoff.
- `docs/PROFILES.md`: how the project type, mode and shape choose what gets installed.
- `docs/BLUEPRINT.md`: the full design and its sources.
