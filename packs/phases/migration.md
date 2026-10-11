---
id: migration
title: Change existing systems safely (refactor, re-platform, rewrite)
kind: phase
mode: both
when: refactoring, re-platforming or rewriting existing code ('refonte'), or changing untested legacy code
description: Use to refactor, re-platform or rewrite code: characterization tests, strangler fig, parity, data migration, cutover.
globs: ["docs/migration/**", "**/characterization/**", "**/golden/**", "**/*.approved.*", "**/parity/**"]
next: [release, operations]
---
# Change existing systems safely

## Entry
- An existing system whose behaviour users depend on.
- A stated goal, e.g. "move billing off the PHP monolith", "upgrade framework v4 to v6", "split orders into a module".
- An ADR saying why: refactor, re-platform or rewrite, and why the cheaper options were rejected.

## Standards
1. **Pick the smallest change that meets the goal.** The order is refactor in place, then re-platform (same behaviour, new runtime/infra), then rewrite piece by piece. A big-bang rewrite is a last resort: it needs a named business reason and human approval.
2. **Safety net before change.** Pin current behaviour with characterization (golden-master/approval) tests before you edit untested code. Record real inputs and outputs, including the odd ones. Bugs are pinned too, and marked `# current behaviour, see ticket`. Fix them in a separate, visible change.
3. **Strangler fig.** Put a seam in front of the old system: a routing layer, facade, proxy or branch-by-abstraction interface. Move one slice at a time behind it. Every slice can be switched back.
4. **Slices are thin and ordered by risk.** Start with a read-only, low-traffic, well-understood slice. Each slice in `docs/migration/<name>/plan.md` has: scope, parity criteria, flag name, data touched, rollback step, owner and status.
5. **Parity is measured, not assumed.** Run old and new side by side on the same inputs: a shadow/dual run, or the Scientist pattern (serve the old result, compare the new one, log differences). Define "equal" first (ordering, rounding, timestamps). A slice moves on only when mismatches are zero or explained in `parity.md`.
6. **Flags and dual-run.** New paths go behind a flag that is off by default, with percentage or cohort rollout and a kill switch. Remove each flag after cutover; a flag is debt with an owner and a removal date.
7. **Data migration safety.**
   - Use expand → migrate → contract: add new columns or tables, backfill in batches (idempotent and resumable), dual-read or verify, switch reads, switch writes, then remove the old ones in a later release.
   - Verify with counts, checksums and sampled row comparisons.
   - Avoid application dual-writes without an outbox or CDC.
   - Back up before each irreversible step, and test the restore.
8. **Money, auth and PII slices** need human review, reconciliation reports (old total = new total) and a longer dual run.
9. **Cutover is a rehearsed event.** Write `cutover-runbook.md` and `rollback-runbook.md` before the day, rehearse them in staging, set a time limit for the go/no-go decision, and keep the old path warm until the rollback window closes.
10. **Finish the job.** Decommission the old code, data, flags, jobs and DNS. A half-migrated system is the most expensive state.
11. **Refactors:** keep them behaviour-preserving, use small commits, keep tests green at each step, and don't mix them with feature changes. Upgrades: follow the official migration guide, one major version at a time.

Details, patterns and sources: `.eos/packs/ref/migration-playbook.md`.

## Deliverables
- `eos new migration "<name>"` creates `docs/migration/<name>/` with `plan.md`, `parity.md`, `data-migration.md`, `cutover-runbook.md` and `rollback-runbook.md`.
- Characterization tests next to the code they pin, e.g. `tests/characterization/`.
- An ADR for the approach.

## Automated checks
- Characterization and parity tests run in CI and stay green on the old path until it is removed.
- Ratchet gates (`eos ratchet check`): no new lint or type violations in touched code.
- Migration SQL lint (squawk) for expand/contract steps.

## Exit checklist (Definition of Done)
- [ ] Every slice is done, with its parity evidence recorded.
- [ ] Cutover and rollback were rehearsed, and the go/no-go was signed off by a human.
- [ ] Old code, data, flags and jobs are removed, or a dated ticket exists for each.
- [ ] Dashboards and alerts now point at the new system (operations pack).

## Handoff → release, operations
Pass the runbooks, the flag list and the decommission plan.

## Stop & escalate
Stop and escalate when:
- parity mismatches have no explanation;
- a data step can't be reversed and has no tested backup;
- the plan turns into a big-bang cutover.

Present the options; don't decide alone.
