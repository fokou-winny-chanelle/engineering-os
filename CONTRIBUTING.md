# Contributing to engineering-os

Thanks for helping. This repo is a CLI (`bin/eos.py`, Python 3.10+, standard library only) plus Markdown packs. A few rules keep it small, fast and trustworthy.

## Ground rules

1. **Always-on context must not grow.** Anything loaded at every session start (core rules, profile, skill descriptions) has a token budget. `eos budget` and the tests enforce it. New knowledge goes into a phase or stack pack (loaded on demand) or a deep reference under `packs/ref/`.
2. **No invented facts.** Versions, prices, limits and API behaviour must cite a source (a link to official docs or a release), with a `verified:` date in the frontmatter of references. If you can't verify a claim, leave it out.
3. **Stdlib only** in `bin/eos.py`. Projects vendor this file, so it must run anywhere Python runs.
4. **Safety stays on.** Don't loosen the guard, lanes or test-integrity checks to make something pass. Explain the trade-off in the PR instead.
5. **Vendored content** (`packs/vendor/`) is copied byte for byte at a pinned commit, with its licence and hashes in `PROVENANCE.json`. It stays quarantined until a maintainer reviews it. Don't edit vendored files; re-vendor them.

## Development setup

```sh
git clone https://github.com/<you>/engineering-os && cd engineering-os
uv tool install pre-commit && pre-commit install --install-hooks   # or: pipx install pre-commit
python3 -m unittest discover -s tests       # ~1 min; some tests skip when optional tools are missing
sh tests/selftest.sh                         # end to end: init into fixtures, hooks, actionlint (POSIX)
```

Optional tool tests: `EOS_TEST_TOOLS=1` (k6, mutmut, Hypothesis), `EOS_TEST_PG_DSN=...` (real Postgres). Lint with `uvx ruff@0.16.10 check bin tests core` and `uvx ruff@0.16.10 format bin tests core`.

## Pull requests

- **Small and focused.** One change per PR, with a test for any behaviour change.
- **Conventional commit messages** (`feat:`, `fix:`, `docs:`, ...). The commit-msg hook checks them.
- **Add an entry to `CHANGELOG.md`** under an `Unreleased` heading.
- If you change a pack or reference, run `python3 bin/eos.py library lint --strict` and `python3 bin/eos.py budget`.
- If you touch latency-sensitive paths (guard hook, lanes, verify), include before and after numbers from `tests/bench/`.
- Say in the PR description if AI tools helped write the change. That's fine; reviewers just read it with that in mind.

## Adding a stack pack

`eos new-stack <id> --markers <file> --globs "<glob>"` scaffolds `packs/stacks/<id>/` (STACK.md, pre-commit.yaml, ci.yml). Pin every tool in `versions.toml` and every GitHub Action to a commit SHA.

## Reporting bugs and security issues

Bugs: open an issue with the template. Security issues: **privately**, see [SECURITY.md](SECURITY.md).
