#!/usr/bin/env python3
"""Check semgrep `generic` (pattern-regex) rules against ruleid/ok fixtures.

`semgrep --test` does not read annotations in files it parses as generic text (*.sql, *.prisma), so this
runs `semgrep scan --json` and compares: a `ruleid: <id>` comment must be followed by a line that rule
matches; an `ok: <id>` comment must be followed by a line it does not match. Stdlib only.
Usage: python3 tests/semgrep_generic_check.py RULES.yml FIXTURE_DIR   (SEMGREP="uvx -q semgrep" to override)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ANNOT = re.compile(r"(?:--|//|#)\s*(ruleid|ok):\s*([\w.-]+)")


def expectations(d: Path) -> tuple[set[tuple[str, int, str]], set[tuple[str, int, str]]]:
    want, forbid = set(), set()
    for f in sorted(p for p in d.iterdir() if p.is_file()):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, start=1):
            m = ANNOT.search(line)
            if m:
                (want if m.group(1) == "ruleid" else forbid).add((f.name, i + 1, m.group(2)))
    return want, forbid


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    rules, d = argv[0], Path(argv[1])
    sg = os.environ.get("SEMGREP") or ("semgrep" if shutil.which("semgrep") else "uvx -q semgrep")
    with tempfile.TemporaryDirectory() as tmp:  # semgrep's default ignore list skips tests/ directories
        for f in d.iterdir():
            if f.is_file():
                shutil.copy(f, tmp)
        r = subprocess.run(
            [
                *shlex.split(sg),
                "scan",
                "--config",
                str(Path(rules).resolve()),
                "--json",
                "--metrics=off",
                "--quiet",
                ".",
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
    try:
        results = json.loads(r.stdout)["results"]
    except (json.JSONDecodeError, KeyError):
        print(f"semgrep failed:\n{r.stderr}", file=sys.stderr)
        return 2
    got = {(Path(x["path"]).name, x["start"]["line"], x["check_id"].rsplit(".", 1)[-1]) for x in results}
    want, forbid = expectations(d)
    missing, wrong = sorted(want - got), sorted(forbid & got)
    for f, line, rid in missing:
        print(f"MISSED {f}:{line} expected {rid}")
    for f, line, rid in wrong:
        print(f"FALSE POSITIVE {f}:{line} {rid}")
    if missing or wrong:
        return 1
    print(f"generic semgrep fixtures: {len(want)} ruleid and {len(forbid)} ok annotations pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
