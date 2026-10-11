---
name: eos-new-stack-pack
description: Create a new engineering-os stack pack (e.g. Go, Rust, Laravel, Flutter) from the template, using official docs for current tool versions; use when eos init reports an unknown stack.
disable-model-invocation: true
---
# eos-new-stack-pack

1. Run `eos new-stack <id> --title "<Title>" --markers <file1,file2> --globs "<glob1,glob2>"` in the engineering-os repo. It copies `packs/stacks/_template/`.
2. Research the stack with **official docs and the release pages** (use the docs MCP or the web). Record each tool's current version with its link. Never guess versions or flags.
3. Fill in `STACK.md` (≤1,200 tokens):
   - the toolchain table
   - layout
   - the 8 rules
   - testing
   - pitfalls: leave empty until real mistakes appear
   Fill `fast_check` and `full_check` with commands you **actually ran** on a sample project.
4. Fill in `pre-commit.yaml` (prefer upstream hook repos, pinned) and `ci.yml` (official setup action, least-privilege `permissions`).
5. Pin versions in `versions.toml`. Run `eos budget` and `python -m unittest discover tests`. Run `eos init` into a temp project that has the marker file and confirm the pack is detected.
6. Open a PR in the engineering-os repo with the source links. Bump the minor `VERSION` and add a CHANGELOG entry.
