"""Test fixture repos, in Python so they build the same on Windows (no POSIX `sh` needed).

python3 tests/fixtures/make_fixtures.py messy <dir>      a "messy" existing repo `eos adopt` must not clobber
python3 tests/fixtures/make_fixtures.py workspace <dir>  4 sibling git repos (contracts, api, web, infra)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# core.excludesFile is pointed at the null device so the developer's global gitignore
# (which eos bootstrap itself seeds with .env, for example) can't change what the fixtures track.
GIT_ID = [
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@x",
    "-c",
    "core.autocrlf=false",
    "-c",
    "commit.gpgsign=false",
    "-c",
    f"core.excludesFile={os.devnull}",
]


def git(d: Path, *args: str) -> None:
    subprocess.run(["git", *GIT_ID, *args], cwd=d, check=True, capture_output=True)


def write(d: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def fresh(d: Path) -> Path:
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d


def commit_all(d: Path, msg: str) -> None:
    git(d, "add", "-A")
    git(d, "commit", "-qm", msg)


MESSY = {
    "AGENTS.md": "# Legacy shop\n\nOur own rules: always use the `Money` class for amounts. Never touch app/billing/legacy.py.\n",
    "CLAUDE.md": "Read AGENTS.md. Use pytest -x.\n",
    ".cursorrules": "Be concise. Python 3.11.\n",
    ".clinerules": "Cline: run make test before finishing.\n",
    ".pre-commit-config.yaml": "repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v4.6.0\n"
    "    hooks:\n      - id: trailing-whitespace\n",
    ".github/workflows/ci.yml": "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
    "      - uses: actions/checkout@v4\n      - run: make test\n",
    "ruff.toml": '[lint]\nselect = ["E", "F"]\n',
    "Makefile": "test:\n\tpytest -q\nlint:\n\truff check .\n",
    "pyproject.toml": '[project]\nname = "legacy-shop"\nversion = "0.1.0"\n'
    'dependencies = ["flask>=2.0", "sqlalchemy", "requests"]\n',
    "app/__init__.py": "import os, sys\n",
    "app/billing/legacy.py": 'import json\ndef total(items):\n    t = 0\n    for i in items: t += i["price"]  # TODO: use Money\n'
    "    return t\n",
    "app/users/views.py": "from flask import Flask\napp = Flask(__name__)\nunused = 1\nimport re\n",
    "app/users/models.py": "def helper(x):\n    return x  # FIXME\n",
    "tests/test_billing.py": 'from app.billing.legacy import total\n\ndef test_total():\n    assert total([{"price": 2}]) == 2\n',
    "web/package.json": '{"name":"web","private":true,"scripts":{"dev":"vite","build":"vite build"},'
    '"dependencies":{"react":"^18.2.0"}}\n',
    "web/.eslintrc.json": '{"root": true, "rules": {"no-unused-vars": "error"}}\n',
    "web/src/main.ts": "export const a = 1;\n",
    "web/src/util.ts": "export const b = 2;\n",
    ".env": "SECRET_KEY=hunter2\n",
}


def make_messy(d: Path) -> None:
    d = fresh(Path(d))
    git(d, "init", "-q", "-b", "main")
    write(d, MESSY)
    commit_all(d, "init")
    with (d / "app/users/models.py").open("a", encoding="utf-8", newline="\n") as f:
        f.write("\ndef extra():\n    return 1\n")
    commit_all(d, "more")


WORKSPACE = {
    "contracts": {
        "openapi.yaml": "openapi: 3.1.0\ninfo: {title: shop, version: 1.0.0}\npaths: {}\n",
        "README.md": "# contracts\n",
    },
    "api": {
        "pyproject.toml": '[project]\nname = "shop-api"\nversion = "0.1.0"\ndependencies = ["fastapi"]\n',
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        **{f"app/m{i}.py": f"def f{i}():\n    return {i}\n" for i in range(1, 5)},
        "tests/test_main.py": "def test_ok():\n    assert True\n",
    },
    "web": {
        "package.json": '{"name":"shop-web","private":true,"scripts":{"build":"next build","lint":"eslint .",'
        '"typecheck":"tsc --noEmit","test":"vitest run"},"dependencies":{"next":"15.0.0","react":"19.0.0"}}\n',
        ".env.example": "API_URL=http://api:8000  # shop api\nAPI_SERVICE=api\n",
        "tsconfig.json": '{"compilerOptions":{"strict":true}}\n',
        "src/page.tsx": "export default function Page() { return null }\n",
    },
    "infra": {"main.tf": "terraform {}\n", "README.md": "# infra\n"},
}


def make_workspace(d: Path) -> None:
    d = fresh(Path(d))
    for name, files in WORKSPACE.items():
        r = d / name
        r.mkdir()
        git(r, "init", "-q", "-b", "main")
        write(r, files)
        commit_all(r, "init")


if __name__ == "__main__":
    kinds = {"messy": make_messy, "workspace": make_workspace}
    if len(sys.argv) != 3 or sys.argv[1] not in kinds:
        sys.exit(__doc__)
    kinds[sys.argv[1]](Path(sys.argv[2]))
