"""Measure what eos adds to the inner loop: agent hook latency, commit hooks, stop check, eos check.

Usage: python3 tests/bench/bench_hooks.py <eos_repo> [runs]   (prints JSON; needs git + pre-commit, warm cache)
Same fixture for every version so before/after numbers compare. Wall-clock, median of N runs, on this machine.
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
N = int(sys.argv[2]) if len(sys.argv) > 2 else 15
tmp = Path(tempfile.mkdtemp(prefix="eosbench-"))
proj, home = tmp / "proj", tmp / "home"
env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PRE_COMMIT_HOME=os.path.expanduser("~/.cache/pre-commit"))
env.pop("EOS_HOME", None)


def sh(cmd, cwd=proj, stdin=None, check=True):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if check and p.returncode != 0:
        raise SystemExit(f"failed: {cmd}\n{p.stdout}\n{p.stderr}")
    return p


def timed(fn, n=N):
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(xs)), round(max(xs))


(proj / "api/app").mkdir(parents=True)
(proj / "api/tests").mkdir(parents=True)
(proj / "web/app").mkdir(parents=True)
(proj / "docs").mkdir()
(proj / "api/pyproject.toml").write_text(
    '[project]\nname="api"\nversion="0.1.0"\ndependencies=["fastapi"]\n', encoding="utf-8", newline="\n"
)
for i in range(40):
    (proj / f"api/app/mod{i}.py").write_text(
        f'"""Module {i}."""\n\n\ndef f{i}(x: int) -> int:\n    return x + {i}\n', encoding="utf-8", newline="\n"
    )
(proj / "web/package.json").write_text(
    '{"name":"web","private":true,"scripts":{"lint":"echo lint","typecheck":"echo tc","test":"echo test"},'
    '"dependencies":{"next":"16.0.0"}}\n',
    encoding="utf-8",
    newline="\n",
)
(proj / "web/pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8", newline="\n")
(proj / "web/next.config.ts").write_text("export default {}\n", encoding="utf-8", newline="\n")
(proj / "docs/intro.md").write_text("# Intro\n\nHello wrold.\n", encoding="utf-8", newline="\n")
sh(["git", "init", "-q", "-b", "main"])
sh(["git", "config", "user.email", "b@example.com"])
sh(["git", "config", "user.name", "bench"])
sh(
    [sys.executable, str(repo / "bin/eos.py"), "bootstrap", "--home", str(home), "--tools", "all", "--no-mcp"],
    check=False,
)
sh([sys.executable, str(repo / "bin/eos.py"), "init", str(proj), "--tools", "all", "--yes"])
(tmp / "gitconfig").write_text("", encoding="utf-8", newline="\n")
env["GIT_CONFIG_GLOBAL"] = str(tmp / "gitconfig")  # no global hooksPath from bootstrap
sh(["git", "add", "-A"])
sh(["git", "commit", "-qm", "chore: setup", "--no-verify"])
sh(["git", "checkout", "-qb", "feat/bench"])
sh(["pre-commit", "install", "--install-hooks"])  # default_install_hook_types from the config

eos = [sys.executable, ".eos/bin/eos.py"]
out: dict = {
    "eos": (repo / "VERSION").read_text(encoding="utf-8").strip(),
    "rev": sh(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"]).stdout.strip(),
    "runs": N,
}


# what the agent tool actually runs (hook.py launcher since 0.6; eos.py guard before)
HOOK = [sys.executable, ".eos/bin/hook.py"] if (proj / ".eos/bin/hook.py").exists() else [*eos, "guard"]


def guard(payload):
    return lambda: sh([*HOOK, "claude-tool"], stdin=json.dumps(payload), check=False)


out["guard_read_ms"] = timed(guard({"tool_name": "Read", "tool_input": {"file_path": "api/app/mod1.py"}}))
out["guard_edit_ms"] = timed(guard({"tool_name": "Edit", "tool_input": {"file_path": "api/app/mod1.py"}}))
out["guard_shell_ms"] = timed(
    guard({"tool_name": "Bash", "tool_input": {"command": "uv run pytest -q"}, "session_id": str(time.time())})
)
out["eos_check_ms"] = timed(lambda: sh([*eos, "check"]), n=5)
k = [0]


def commit_md():
    k[0] += 1
    (proj / "docs/intro.md").write_text(f"# Intro\n\nHello world {k[0]}.\n", encoding="utf-8", newline="\n")
    sh(["git", "add", "docs/intro.md"])
    sh(["git", "commit", "-qm", f"docs: fix typo {k[0]}"])


def commit_py():
    k[0] += 1
    (proj / "api/app/mod1.py").write_text(
        f'"""Module 1."""\n\n\ndef f1(x: int) -> int:\n    return x + {k[0]}\n', encoding="utf-8", newline="\n"
    )
    sh(["git", "add", "api/app/mod1.py"])
    sh(["git", "commit", "-qm", f"fix: bump {k[0]}"])


commit_md()  # warm-up (hook envs, caches)
commit_py()
out["commit_docs_typo_ms"] = timed(commit_md, n=5)
out["commit_py_change_ms"] = timed(commit_py, n=5)


def stop():
    k[0] += 1
    (proj / "api/app/mod2.py").write_text(
        f'"""Module 2."""\n\n\ndef f2(x: int) -> int:\n    return x + {k[0]}\n', encoding="utf-8", newline="\n"
    )
    sh([*eos, "guard", "claude-stop"], stdin=json.dumps({"session_id": f"s{k[0]}"}), check=False)


out["stop_check_py_ms"] = timed(stop, n=5)
if not os.environ.get("KEEP"):
    shutil.rmtree(tmp, ignore_errors=True)
else:
    out["dir"] = str(proj)
print(json.dumps(out, indent=1))
