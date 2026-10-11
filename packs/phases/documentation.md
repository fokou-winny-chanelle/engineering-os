---
id: documentation
title: Documentation
kind: phase
mode: files
when: writing or editing docs, READMEs, guides or API docs
description: Use when writing or editing documentation - READMEs, guides, how-tos, API docs, onboarding, ADR prose. Diataxis structure, docs-as-code, examples that run, keep it short and current.
globs: ["docs/**", "**/README*", "**/CONTRIBUTING*", "**/*.mdx"]
next: []
---
# Documentation

## Entry
A change that alters behaviour, setup, operations or decisions (docs ship in the same PR as the code).

## Standards
1. Know the doc type (Diataxis). Don't mix the four types in one page:
   - *Tutorial*: learning by doing.
   - *How-to*: a recipe for a goal.
   - *Reference*: exact facts, preferably generated.
   - *Explanation*: the why, including ADRs.
2. Docs as code. Docs are in the repo, reviewed in PRs and linted. Keep reference docs generated from the source of truth (OpenAPI → API docs, `--help` → CLI docs) and never hand-copy them.
3. README contract (every repo or service):
   - what it is (2 lines)
   - quick start (≤5 commands from clone to running)
   - how to run checks and tests
   - config/env vars (names only)
   - architecture link
   - owners
   - runbook and dashboard links
4. Examples run. Code samples are tested or copied from tested code. Commands use real paths and flags. Versions are stated.
5. Plain language.
   - Short sentences and active voice.
   - Explain jargon on first use.
   - Write for a bilingual reader (avoid idioms).
   - Prefer lists and tables over long paragraphs.
6. Freshness. Each doc names an owner. A stale doc is worse than no doc, so delete or fix it. Check links in CI.
7. AI context docs are docs too. Keep AGENTS.md, the packs, memory files and lessons short and current. Remove a rule once a tool enforces it.

## Deliverables
- Updated README, how-to, reference or ADR as the change requires, plus changelog entries for user-visible changes.

## Automated checks
- Markdown lint, a link checker, spell check (optional, EN/FR dictionaries), generated-docs freshness (regenerate, then `git diff --exit-code`).
- `eos check` keeps AI context files within their token budgets.

## Exit checklist (Definition of Done)
- [ ] A new teammate can run the quick start without asking anyone.
- [ ] Docs changed in the same PR as the behaviour.
- [ ] No broken links, and examples were executed.
- [ ] Each doc has a clear type and owner.

## Handoff
Done. Docs are part of the PR that code-review checks.

## Stop & escalate
Ask when you are unsure whether something is public, confidential or regulated before documenting it.
