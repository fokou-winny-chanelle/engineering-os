---
id: maintenance
title: Maintenance, refactoring & tech debt
kind: phase
mode: intent
when: refactoring, upgrading dependencies, paying down tech debt or removing dead code
description: Use for refactors, upgrades, deprecations, dead code, performance tuning or tech-debt triage.
globs: []
next: [code-review]
---
# Maintenance, refactoring & tech debt

## Entry
A ticketed debt item, an upgrade (dependency, runtime, framework), a postmortem action, or a lesson that repeats.

## Standards
1. Keep a tech-debt register (`docs/tech-debt.md` or tickets): item, impact (risk, speed, cost), effort, owner. Review it monthly and budget a fixed share of capacity (e.g. 15–20%) rather than "when we have time".
2. Refactors preserve behaviour. Add characterisation tests first if coverage is weak. Never mix a refactor and a behaviour change in one PR.
3. Strangler pattern for big changes. Put a new path beside the old one behind a flag or router, migrate step by step, then delete the old path. Avoid big-bang rewrites.
4. Upgrades.
   - Read the changelog and migration guide first, using the docs MCP rather than memory.
   - Upgrade one major version at a time, run the codemods, run the full checks, and keep the lockfile diff reviewable.
   - Renovate batches minor/patch updates and handles majors individually.
5. Deprecate before you delete. Announce, mark (annotations or headers), measure usage, then remove. Feature flags have an expiry date.
6. Measure performance work. Benchmark or profile before and after on realistic data; no speculative optimisation.
7. Delete dead code confidently, guided by coverage, usage telemetry and search. Git remembers it.
8. Run retros on the AI system too. When an AI mistake repeats twice, add a lesson. When a lesson repeats, turn it into an automated check (lint rule, test, hook) and delete the prose rule. Keep packs within budget (`eos check`).
9. Garbage collection. On a regular cadence (weekly works), run a clean-up pass for duplication, dead code, stale docs and golden-principle violations. Small PRs, easy to review. Track the rest in `docs/plans/tech-debt.md`.

## Deliverables
- A small PR with a behaviour-preserving diff, before/after evidence (tests and benchmarks), and an updated debt register/ADR.

## Automated checks
- Full stack checks, `eos test-integrity` (refactors must not change tests' assertions), and benchmarks where relevant.
- Scheduled: dependency audit, Renovate dashboard, dead-code and unused-dependency tools (stack pack).

## Exit checklist (Definition of Done)
- [ ] Behaviour is unchanged (same tests pass, no assertions altered) or the change is approved separately.
- [ ] The upgrade is complete: no deprecated API warnings left, and the lockfile is reviewed.
- [ ] The debt register is updated, and follow-ups are ticketed.

## Handoff → code-review
Pass the PR plus the evidence (tests, benchmarks, warnings removed).

## Stop & escalate
Stop when a "refactor" needs a behaviour change, or when an upgrade breaks more than one module. Re-plan and split it.
