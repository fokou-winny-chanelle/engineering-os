"""Run the eos Spectral ruleset against fixture specs and compare with their `# expect:` headers.

Usage: SPECTRAL="npx --yes @stoplight/spectral-cli@6.17.0" python3 tests/spectral_check.py RULESET FIXTURE_DIR
Each fixture lists the eos-* rule codes it must trigger on `# expect:` lines (none for clean fixtures).
A fixture fails if an expected code is missing, an unexpected eos-* code fires, or a clean fixture
gets any result at all (including the built-in spectral:oas rules).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def expected(path: Path) -> set[str]:
    codes: set[str] = set()
    for line in path.read_text().splitlines():
        if line.startswith("# expect:"):
            codes |= set(re.findall(r"\beos-[a-z0-9-]+", line))
    return codes


def run(ruleset: Path, fixture: Path) -> list[dict]:
    cmd = shlex.split(os.environ.get("SPECTRAL", "npx --yes @stoplight/spectral-cli@6.17.0"))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.json"
        subprocess.run(
            [
                *cmd,
                "lint",
                str(fixture),
                "--ruleset",
                str(ruleset),
                "--format",
                "json",
                "--output",
                str(out),
                "--fail-severity",
                "error",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if not out.exists():
            raise SystemExit(f"spectral produced no output for {fixture}")
        return json.loads(out.read_text() or "[]")


def main(argv: list[str]) -> int:
    ruleset, fixtures = Path(argv[1]), Path(argv[2])
    bad = 0
    for fx in sorted(fixtures.glob("*.yaml")):
        want = expected(fx)
        results = run(ruleset, fx)
        got = {r["code"] for r in results if str(r["code"]).startswith("eos-")}
        problems = []
        if want - got:
            problems.append(f"missing {sorted(want - got)}")
        if got - want:
            problems.append(f"unexpected {sorted(got - want)}")
        if not want and results:
            problems.append("clean fixture has results: " + ", ".join(sorted({str(r["code"]) for r in results})))
        print(
            f"{'FAIL' if problems else 'ok  '} {fx.name}: {len(want)} expected, {len(got)} eos codes fired"
            + (f" ({'; '.join(problems)})" if problems else "")
        )
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
