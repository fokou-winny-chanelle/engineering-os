---
name: eos-retro
description: Run a short AI-workflow retrospective after a story, incident or bad session; turns repeated mistakes into lessons, rules or automated checks, and keeps context files small.
disable-model-invocation: true
---
# eos-retro: turn mistakes into checks

Run at the end of a story or sprint, after an incident, or whenever the agent made the same mistake twice.

1. **Collect evidence. Don't rely on memory.** Use `git log --oneline -20`, the PR review comments, CI failures, `memory/progress.md` and `memory/handoff.md`, and the current `docs/ai/lessons.md`.
2. **List the mistakes.** For each one, give: what happened, its impact, the root cause (missing context? wrong pack? no check? ambiguous spec?), and how many times it has happened (search lessons.md).
3. **Pick the cheapest durable fix**, in this order of preference:
   1. **An automated check**: a lint rule, a test, a type, a pre-commit hook, a CI step, or a hook in `.eos/protected.txt`.
   2. **A pack edit**: one line in the right phase or stack pack (in the engineering-os repo if it's general, in `.eos/packs` if it's project-only).
   3. **A lesson line** in `docs/ai/lessons.md`: `YYYY-MM-DD | context | do / don't | automation ticket`.
4. **Prune.** If a lesson is now enforced by a check, delete it. Run `python .eos/bin/eos.py check` (budgets) and keep every file within budget. If a pack is too long, cut the least-used lines.
5. **Output** a table (mistake → fix type → file → status) plus the exact diffs proposed. **Apply them only after the human approves.** Rule changes are reviewed like code.
6. If a fix is general (it would help every project), say so. The human then upstreams it to the engineering-os repo, and `eos update` delivers it everywhere.
