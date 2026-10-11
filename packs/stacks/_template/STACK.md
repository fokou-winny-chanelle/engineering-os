---
id: STACK_ID
title: STACK_TITLE
kind: stack
mode: files
when: editing STACK_TITLE code or config
description: STACK_TITLE conventions - toolchain, layout, typing, errors, testing, pitfalls. Fill in and keep under 1,200 tokens.
globs: ["**/*.EXT"]
markers: ["MARKER_FILE"]
contains: []
requires: []
fast_check: "FORMAT_AND_LINT_COMMAND"
full_check: "LINT && TYPECHECK && TEST && BUILD"
ci: STACK_ID
---
# Stack: STACK_TITLE

<!-- Fill every section. Facts must come from the official docs for the version you use; link them in the PR that adds this pack. Delete these comments. -->

## Toolchain (pins in versions.toml / lockfile)
| Job | Tool | Command |
|---|---|---|
| Deps + env | | |
| Format + lint | | |
| Types / compile | | |
| Tests (unit, integration) | | |
| Boundaries | | |
| Dependency audit | | |

## Layout
<!-- Where transport / services / domain / adapters / tests live in this stack. -->

## Rules
1. Types / compile-time safety: …
2. Validation at boundaries: …
3. Errors: …
4. Money and time types: …
5. Concurrency model: …
6. Config and secrets: …
7. DB access and migrations: …
8. Logging and observability: …

## Testing
<!-- Test runner, fixtures, real-DB integration approach, contract tests. -->

## Pitfalls the AI often makes
<!-- Fill from real mistakes (retros). Start empty rather than guessing. -->
