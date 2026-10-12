## Working rules
1. Size the process to the lane (`python3 .eos/bin/eos.py lane`). trivial (docs, copy) and standard: make the change and verify, no plan. risky (money, auth, crypto, PII, migrations, infra, CI, or a large diff): state a 5-line plan (goal, files, risks, checks, rollback); wait for approval if it changes money, auth or security behaviour, otherwise continue. one-way-door (dropping data, breaking a public contract): wait for approval.
2. Done means `python3 .eos/bin/eos.py verify` passes (it picks the checks for the lane; stack commands below).
3. Keep checks honest. Don't delete, skip or loosen tests, asserts, thresholds or lint rules, or add ignore comments to get green. Leave CI, hooks, lockfiles and `.eos/` alone unless that is the task. If a test looks wrong, explain why and ask.
4. Secrets: don't open `.env*` or key files; refer to env var names only. The guard hook blocks these reads.
5. Money, auth, crypto, PII, migrations or infra changes need human review: list those files in the PR summary.
6. Ask one question only when requirements, money rules or security behaviour are unclear. Otherwise pick the conventional option, state the assumption and continue.
7. Follow existing patterns. For a new dependency, say why and confirm the package exists.
8. On `spike/*` branches: no tests, plans or docs; the code is thrown away. On `hotfix/*`: smallest fix plus a regression test, no refactors.
9. End each task in plain words: what you did, what you verified (a line per check; say what you skipped), and the next step: where (terminal, this chat or GitHub) and what to type. Offer to do git/PR steps. Gloss internal names (test-integrity, labels).

## When stuck
- The same check fails after 3 real fix attempts, or the same command gives the same result 3 times: stop, write `memory/handoff.md` (≤30 lines: goal, failing command, what you tried, next step) and ask. The hooks enforce this.
- Two failed attempts at a hard bug or design: say so and suggest a stronger model or a fresh session.
- The diff grows well past the plan, or reaches a path in `.eos/protected.txt`: re-plan.

## Context
- Read only what the task needs. For library APIs, check the installed version (lockfile) and the official docs rather than recalling them.
- Resumed work: read `memory/handoff.md` if it exists. Decisions: `docs/adr/INDEX.md`, then only the ADR you need.
- Asked "what next?" or "where are we?": run `python3 .eos/bin/eos.py next` and relay it.

## Memory (only when there is state worth keeping)
- Work stops unfinished: write `memory/handoff.md`. Git history is the progress log; don't keep a separate one.
- A one-way-door decision gets an ADR plus an INDEX line. A repeated mistake: propose an automated check (preferred) or one line in `docs/ai/lessons.md`.
