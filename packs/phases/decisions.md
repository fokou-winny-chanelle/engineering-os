---
id: decisions
title: Decision engine (stack, data, hosting, auth, architecture, mobile approach)
kind: phase
mode: intent
when: choosing a stack, database, hosting, auth, monolith vs services, mobile approach, or build vs buy
description: Use when choosing a stack, database, hosting, auth, services split, mobile approach or build vs buy.
globs: []
next: [architecture, requirements]
---
# Decision engine

## Entry
A choice that is expensive to undo, or one the team keeps re-arguing. Read `memory/active-context.md`, the "Product profile" in AGENTS.md and `docs/adr/INDEX.md` first. If a matching ADR exists, follow it unless the facts changed.

## Standards
1. **Classify the door first.**
   - **One-way door** (Type 1): hard to reverse, e.g. primary database, cloud lock-in, auth provider, mobile framework, public API shape, data residency. Go slowly, write an ADR, and get a human decision. The agent proposes; the human decides.
   - **Two-way door** (Type 2): easy to reverse, e.g. a library behind an interface, or a UI kit. Decide fast and note it in the PR.
2. **Ask before you match.** Fill in the questionnaire in `.eos/packs/ref/decision-matrices.md` §0. Unknown answers stay "unknown". Don't invent requirements.
3. **Start from the default, then look for reasons to leave it.** Each matrix gives a boring default and the specific conditions that change it. To leave the default you need a named condition that is true for this product.
4. **Boring by default.** Use proven, well-documented technology that the team (and AI models) know well. Spend at most about 3 "innovation tokens", and only where the product is different.
5. **Total cost, not sticker price.** Compare build, run, maintenance, people, exit/migration and compliance. Never quote a price from memory. Cite the vendor pricing page with its date, or leave the price out.
6. **Build vs buy.** Buy (or use open source) for commodity capabilities: auth, payments, email/SMS, error tracking, search. Build only your differentiator. Wrap every vendor behind your own interface so the door stays two-way.
7. **Make the decision checkable.** Turn the key quality into a fitness function, e.g. a layer rule, p95 latency budget, bundle size, or "no PII leaves region X". Add it to CI or monitoring.
8. **Record it.** `eos new adr "<decision>"`: context, options (at least 2 real ones plus "do nothing"), decision, consequences, review trigger (the fact that would make you revisit it).

## Deliverables
- A filled questionnaire (in the ADR context section), the matrix rows you used, an ADR with status `proposed`, and fitness-function tasks.

## Automated checks
- `eos check` (ADR index consistent). New fitness functions run in CI.

## Exit checklist (Definition of Done)
- [ ] Door type stated. A human approved every one-way-door ADR.
- [ ] At least 2 real options were compared on the same criteria, with cited facts and no invented numbers.
- [ ] The default was kept, or the condition that overrode it is named.
- [ ] Vendor lock-in is wrapped behind an interface, or explicitly accepted.
- [ ] A review trigger and a fitness function are recorded.

## Handoff → architecture / requirements
Pass the ADR link, constraints for the architecture pack, and any new non-functional requirements.

## Stop & escalate
Stop when the choice depends on budget, legal or data-residency questions, team hiring, or a contract. These are human calls. Also stop when two options are close and the matrix can't separate them. Present the trade-off; don't pick at random.
