#!/usr/bin/env sh
# A realistic "messy" existing repo: user-owned agent rules, configs and CI that `eos adopt` must not clobber.
set -eu
d="$1"; rm -rf "$d"; mkdir -p "$d" && cd "$d"
git init -q -b main
mkdir -p app/billing app/users tests .github/workflows web/src
cat > AGENTS.md <<'X'
# Legacy shop

Our own rules: always use the `Money` class for amounts. Never touch app/billing/legacy.py.
X
printf 'Read AGENTS.md. Use pytest -x.\n' > CLAUDE.md
printf 'Be concise. Python 3.11.\n' > .cursorrules
printf 'Cline: run make test before finishing.\n' > .clinerules
cat > .pre-commit-config.yaml <<'X'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
X
cat > .github/workflows/ci.yml <<'X'
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test
X
printf '[lint]\nselect = ["E", "F"]\n' > ruff.toml
printf 'test:\n\tpytest -q\nlint:\n\truff check .\n' > Makefile
cat > pyproject.toml <<'X'
[project]
name = "legacy-shop"
version = "0.1.0"
dependencies = ["flask>=2.0", "sqlalchemy", "requests"]
X
cat > app/__init__.py <<'X'
import os, sys
X
cat > app/billing/legacy.py <<'X'
import json
def total(items):
    t = 0
    for i in items: t += i["price"]  # TODO: use Money
    return t
X
printf 'from flask import Flask\napp = Flask(__name__)\nunused = 1\nimport re\n' > app/users/views.py
printf 'def helper(x):\n    return x  # FIXME\n' > app/users/models.py
printf 'from app.billing.legacy import total\n\ndef test_total():\n    assert total([{"price": 2}]) == 2\n' > tests/test_billing.py
printf '{"name":"web","private":true,"scripts":{"dev":"vite","build":"vite build"},"dependencies":{"react":"^18.2.0"}}\n' > web/package.json
printf '{"root": true, "rules": {"no-unused-vars": "error"}}\n' > web/.eslintrc.json
printf 'export const a = 1;\n' > web/src/main.ts
printf 'export const b = 2;\n' > web/src/util.ts
printf 'SECRET_KEY=hunter2\n' > .env
git add -A && git -c user.name=t -c user.email=t@x commit -qm "init"
printf '\ndef extra():\n    return 1\n' >> app/users/models.py
git add -A && git -c user.name=t -c user.email=t@x commit -qm "more"
