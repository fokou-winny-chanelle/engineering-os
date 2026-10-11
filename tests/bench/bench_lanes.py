"""Measure `eos lane` and `eos verify` per lane on one fixture (FastAPI-style api/ with 60 pytest tests
+ a Next.js web/ stub), so versions compare on the same inputs.

Usage: python3 tests/bench/bench_lanes.py <eos_repo> [runs]   (prints JSON; needs git, pre-commit, pytest)
Wall-clock, median of N runs, on this machine. Each scenario starts from a clean feature branch.
"""

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
tmp = Path(tempfile.mkdtemp(prefix="eoslanes-"))
proj, home = tmp / "proj", tmp / "home"
env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PRE_COMMIT_HOME=os.path.expanduser("~/.cache/pre-commit"))
env.pop("EOS_HOME", None)
env.pop("EOS_LANE", None)


def sh(cmd, cwd=proj, stdin=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, check=False)
    if check and p.returncode != 0:
        raise SystemExit(f"failed: {cmd}\n{p.stdout}\n{p.stderr}")
    return p


def timed(fn, n=N):
    xs, last = [], None
    for _ in range(n):
        t = time.perf_counter()
        last = fn()
        xs.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(xs)), round(max(xs)), last


(proj / "api/app/payments").mkdir(parents=True)
(proj / "api/tests").mkdir(parents=True)
(proj / "web/app").mkdir(parents=True)
(proj / "docs").mkdir()
(proj / "api/pyproject.toml").write_text(
    '[project]\nname="api"\nversion="0.1.0"\ndependencies=["fastapi"]\n\n[tool.pytest.ini_options]\npythonpath=["."]\n'
)
(proj / "api/app/__init__.py").write_text("")
for i in range(60):
    (proj / f"api/app/mod{i}.py").write_text(f'"""Module {i}."""\n\n\ndef f{i}(x: int) -> int:\n    return x + {i}\n')
    (proj / f"api/tests/test_mod{i}.py").write_text(
        f"from app.mod{i} import f{i}\n\n\ndef test_f{i}() -> None:\n    assert f{i}(1) == {i + 1}\n"
    )
(proj / "api/app/payments/__init__.py").write_text("")
(proj / "api/app/payments/refund.py").write_text(
    '"""Refunds."""\n\n\ndef refund(cents: int) -> int:\n    return cents\n'
)
(proj / "api/tests/test_refund.py").write_text(
    "from app.payments.refund import refund\n\n\ndef test_refund() -> None:\n    assert refund(5) == 5\n"
)
(proj / "web/package.json").write_text(
    '{"name":"web","private":true,"scripts":{"lint":"echo lint","typecheck":"echo tc","test":"echo test"},'
    '"dependencies":{"next":"16.0.0"}}\n'
)
(proj / "web/pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
(proj / "web/next.config.ts").write_text("export default {}\n")
(proj / "docs/intro.md").write_text("# Intro\n\nHello wrold.\n")
sh(["git", "init", "-q", "-b", "main"])
sh(["git", "config", "user.email", "b@example.com"])
sh(["git", "config", "user.name", "bench"])
sh(
    [sys.executable, str(repo / "bin/eos.py"), "bootstrap", "--home", str(home), "--tools", "all", "--no-mcp"],
    check=False,
)
sh([sys.executable, str(repo / "bin/eos.py"), "init", str(proj), "--tools", "all", "--yes"])
(tmp / "gitconfig").write_text("")
env["GIT_CONFIG_GLOBAL"] = str(tmp / "gitconfig")
sh(["git", "add", "-A"])
sh(["git", "commit", "-qm", "chore: setup", "--no-verify"])
sh(["pre-commit", "install", "--install-hooks"], check=False)
eos = [sys.executable, ".eos/bin/eos.py"]
out: dict = {
    "eos": (repo / "VERSION").read_text().strip(),
    "rev": sh(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"]).stdout.strip(),
    "runs": N,
    "fixture": "api/ 61 modules + 61 pytest tests, web/ Next.js stub, eos init --yes (all tools)",
}
SCEN = {
    "trivial_docs_typo": lambda: (proj / "docs/intro.md").write_text("# Intro\n\nHello world.\n"),
    "standard_py_change": lambda: (proj / "api/app/mod1.py").write_text(
        '"""Module 1."""\n\n\ndef f1(x: int) -> int:\n    """Add one."""\n    return x + 1\n'
    ),
    "risky_payments_change": lambda: (proj / "api/app/payments/refund.py").write_text(
        '"""Refunds."""\n\n\ndef refund(cents: int) -> int:\n    """Full refund."""\n    return cents\n'
    ),
}
for name, change in SCEN.items():
    sh(["git", "checkout", "-q", "main"])
    sh(["git", "checkout", "-qB", f"feat/{name}"])
    change()
    lane_ms = timed(lambda: sh([*eos, "lane"], check=False))
    plan = sh([*eos, "verify", "--dry-run"], check=False).stdout.strip().splitlines()
    sh([*eos, "verify"], check=False)  # warm-up
    v = timed(lambda: sh([*eos, "verify"], check=False))
    last = v[2]
    out[name] = {
        "lane_ms": lane_ms[:2],
        "verify_ms": v[:2],
        "verify_exit": last.returncode,
        "lane_line": plan[0] if plan else "",
        "steps": [ln.strip() for ln in plan[1:]],
        "verify_tail": last.stdout.strip().splitlines()[-1] if last.stdout.strip() else last.stderr[-200:],
    }
    sh(["git", "checkout", "-q", "--", "."])
out["eos_check_ms"] = timed(lambda: sh([*eos, "check"], check=False))[:2]
out["eos_next_ms"] = timed(lambda: sh([*eos, "next"], check=False))[:2]
if not os.environ.get("KEEP"):
    shutil.rmtree(tmp, ignore_errors=True)
else:
    out["dir"] = str(proj)
print(json.dumps(out, indent=1))
