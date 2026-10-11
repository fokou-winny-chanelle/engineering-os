---
id: ideation
title: Ideation & brainstorming
kind: phase
mode: intent
when: exploring ideas, options or a new product/feature concept
description: Use when brainstorming a new product, feature or technical idea before requirements exist.
globs: []
next: [discovery]
---
# Ideation & brainstorming

## Entry
A problem, opportunity or vague idea. No commitment yet. Nothing gets built in this phase.

## Standards
1. Diverge, then converge. Generate ≥5 distinct options (including "do nothing" and "buy, don't build") before scoring any of them.
2. Problem before solution. Write the problem in one sentence: *who* has it, *when*, and *what it costs them*. If you can't, go to discovery.
3. Separate facts from assumptions. Tag each claim `[fact: source]` or `[assumption]`. Never invent market numbers. Write "unknown" instead.
4. Score with explicit criteria: user value, effort (t-shirt size), risk (tech/regulatory/money), reversibility, strategic fit. Show the table.
5. Name the riskiest assumption for the top 1–2 options and the cheapest test of it (a conversation, prototype, spike ≤1 day, or a data query).
6. Kill criteria up front. Write what result would make you drop the idea.
7. In regulated domains (payments, lending, health, KYC), list the licences or compliance questions as risks. Don't answer them; a human must.
8. The AI acts as a facilitator. It asks one question at a time, challenges weak ideas politely, and doesn't flatter.

## Deliverables
- `docs/ideas/<slug>.md`: problem statement, options table, chosen direction, assumptions log, riskiest-assumption test, kill criteria.
- Optional BMAD: `bmad-brainstorming`, `bmad-forge-idea` or `bmad-party-mode` output in `_bmad-output/`.

## Automated checks
- None by design (thinking phase). Markdown lint runs on commit.

## Exit checklist (Definition of Done)
- [ ] Problem statement is one sentence and names the user.
- [ ] ≥5 options were considered, including do-nothing and buy.
- [ ] Every number has a source or is marked as an assumption.
- [ ] Riskiest assumption and its test are written down.
- [ ] Human decided: go to discovery, park, or kill.

## Handoff → discovery
Pass `docs/ideas/<slug>.md`. Discovery starts by testing the riskiest assumption.

## Stop & escalate
Stop if asked to decide go/kill on your own, or when the idea depends on legal or regulatory interpretation.
