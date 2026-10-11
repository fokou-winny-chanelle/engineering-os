---
id: requirements
title: Requirements & specification
kind: phase
mode: both
when: writing PRDs, specs, user stories or acceptance criteria
description: Use when writing or changing a PRD, spec, epic, user story or acceptance criteria.
globs: ["docs/prd*", "docs/specs/**", "specs/**", "**/stories/**", "_bmad-output/planning-artifacts/**"]
next: [ux-design, architecture]
---
# Requirements & specification

## Entry
An approved discovery brief (or a small change request on the Quick Flow track).

## Standards
1. Pick the track by size and risk. Quick Flow means a spec of one or two pages. The BMad Method track adds a PRD, architecture and stories. The Enterprise track also adds security, compliance and operations documents. Anything touching money or regulation goes to BMad Method at minimum.
2. Testable acceptance criteria in EARS form:
   - `WHEN <trigger> THE SYSTEM SHALL <response>`
   - `IF <unwanted condition> THEN THE SYSTEM SHALL <response>`
   - `WHILE <state> …`
   - `WHERE <feature enabled> …`
   Each criterion gets an ID such as `AC-12` and is written so it can become one automated test.
3. Non-functional requirements are numbers. Examples: latency p95 < 300 ms at N rps, availability target, RPO/RTO, data retention, accessibility (WCAG 2.2 AA), languages, supported devices and bandwidth, cost ceiling.
4. Unhappy paths first. For each flow, cover timeouts, duplicates and retries, partial failure, invalid input, permission denied, concurrency, and limits.
5. Money and state rules are explicit. State the currency and minor units, rounding, fees, refunds and reversals, idempotency, and the order of the state machine. Ask a human whenever any of these is unclear.
6. Traceability. Each story links to a requirement or persona, and each AC links to a test. Use the same IDs in test names.
7. Scope. Keep non-goals and "later" items in a parking-lot list. If a change during build adds ACs, run `bmad-correct-course` (or re-approve the spec) instead of letting scope creep in silently.
8. Stories are vertical slices. A story should take about a day or less, be independently testable, and touch about 500 changed lines or fewer (roughly one `bmad-build` session).

## Deliverables
- A PRD or spec: `docs/prd.md` or `specs/<feature>/spec.md` (the BMAD equivalent lives in `_bmad-output/planning-artifacts/`).
- Epics and stories with ACs (`bmad-create-epics-and-stories`).
- A table of non-functional requirements and an open-questions list.

## Automated checks
- Markdown lint.
- Optional script: every `AC-\d+` must appear in at least one test name before release (traceability check).

## Exit checklist (Definition of Done)
- [ ] Every AC is in EARS form, has an ID and is testable. There are no vague words ("fast", "secure", "user-friendly").
- [ ] Each main flow has unhappy-path ACs.
- [ ] Non-functional requirements are quantified. Money and state rules are confirmed by a human.
- [ ] Non-goals are listed. Open questions are closed or assigned.
- [ ] Product owner approved (implementation readiness check passed).

## Handoff → ux-design and/or architecture
Pass the PRD/spec, the NFR table and the story list. Architecture must address every NFR.

## Stop & escalate
Stop on conflicting requirements, on undefined money or regulatory behaviour, or when a story can't be made testable.
