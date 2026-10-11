---
id: code-review
title: Code review
kind: phase
mode: intent
when: reviewing a diff or PR, or preparing one for review
description: Use when reviewing a pull request or diff, or preparing a PR for review.
globs: []
next: [release]
---
# Code review

## Entry
A PR with a summary, linked story/ACs, green CI, and a diff of a reviewable size (about 400 changed lines or fewer; split it if bigger).

## Review order (highest risk first)
1. Correctness vs ACs. Does the code do what the spec says, including unhappy paths? Are the tests real (asserting outcomes, not mocks of the unit)?
2. Security and money (security pack checklist): authz on every resource, input bounds, secrets, idempotency, rounding.
3. Data and compatibility: migrations are safe (expand/contract), the API has no unannounced breaking change, and old clients keep working.
4. Failure handling: timeouts, retries, transactions, error mapping, logs/metrics on failure.
5. Design: boundaries respected, no needless abstraction, follows existing patterns, dependency additions justified.
6. Readability: names, small functions, comments that explain *why*. Style is the linter's job; don't comment on it.
7. Duplication and drift: AI copies existing patterns, good or bad. Flag copy-pasted blocks and new helpers that duplicate shared ones. If an AI reviews AI code, use a different model and this checklist as the rubric. A human approves money, auth and security changes.

## Standards for findings
- Each finding has a severity (blocker / major / minor / nit), a location (`file:line`), evidence (quote or failing scenario), and a suggested fix.
- "Looks fine" is not a review. A blocker must name the concrete scenario that breaks.
- Separate *must-fix* from *suggestions*. Approve with nits rather than block on taste.
- An AI reviewer works from the diff plus the linked spec in a fresh context (not the session that wrote the code). Use the tool's own reviewer for the mechanics (Cursor `/review`, `/review-security` or Bugbot on the PR; Claude Code `/code-review`, `/security-review`; Codex `/review`) and this pack as its rubric. A different model is better than the author model.
- Re-run the checks yourself when a claim matters ("tests pass"). Trust commands, not prose.
- The human reviewer owns the decision. AI review never replaces a human on money, auth, crypto, migrations or infra.

## Deliverables
- Review comments in the PR (severity, location, evidence, fix), a summary verdict (approve / changes requested), and follow-up tickets for deferred majors.

## Author checklist (before requesting review)
- [ ] The PR description covers: what, why, AC IDs, risk areas, how it was tested (commands and results), screenshots for UI, rollout/rollback notes.
- [ ] Self-review done on the diff; no debug code; commits are conventional.
- [ ] `eos test-integrity` is clean, or the test changes are explained.

## Automated checks
- All required CI checks are green; the AI review bot ran; CODEOWNERS approval for protected paths.

## Exit checklist (Definition of Done)
- [ ] All blockers and majors are resolved or have tickets with an owner; nits are optional.
- [ ] Required human approvals are present (two for money or security if the team size allows).
- [ ] The final diff was re-checked after the last fix commits.

## Handoff → release
Merge using the agreed strategy (usually squash with a conventional title). The release notes come from the commits.

## Stop & escalate
Escalate when author and reviewer disagree on a blocker after one round. Ask the tech lead and record the decision as an ADR if it is architectural.
