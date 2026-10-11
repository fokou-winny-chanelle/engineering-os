#!/usr/bin/env python3
"""engineering-os (eos): a stack-agnostic operating system for AI-assisted engineering.

One stdlib-only file (Python >= 3.10), so it runs anywhere and can be vendored into each project
as .eos/bin/eos.py (used there by hooks, pre-commit and CI without installing anything).

Commands (run `eos <cmd> -h` for options):
  bootstrap      set up this machine: personal profile, global skills, MCP configs, git ignore/hooks
  init [DIR]     add the OS to a project: core AGENTS.md, phase + detected stack packs, adapters, hooks, CI
  update [DIR]   pull newer packs/templates from the eos repo into a project (keeps your local edits)
  sync [DIR]     regenerate tool adapters from .eos/packs (after editing a pack locally); --check = drift test
  check          project gate used by pre-commit/CI: budgets + adapter drift + frontmatter
  detect [DIR]   show which stack packs would be selected
  budget [DIR]   token budget report (repo or project)
  doctor         what is installed / missing on this machine (never prints secret values)
  new-stack ID   scaffold a new stack pack from packs/stacks/_template
  test-integrity flag weakened tests (skips, removed asserts, lowered thresholds) vs a base ref
  diff-coverage  coverage of the changed lines only (Cobertura/LCOV), stricter on money/auth paths
  quarantine     flaky-test quarantine with owner, ticket and expiry (check | list | add)
  mutation-plan  mutation-testing targets for risky changed code; mutation-score judges the run
  ops ACTION     SLO schema + burn-rate alert rules, runbook per alert, feature-flag expiry (check | alerts | budget | runbook)
  guard MODE     agent hook entry point (cursor-*/claude-*/cline-*); reads JSON on stdin
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fnmatch
import gzip
import hashlib
import io
import json
import math
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class _LazyRx:
    """A module-level regex compiled on first use. eos.py is imported by every agent hook call, and compiling
    ~70 patterns up front cost several ms per call (v0.7.1 efficiency evaluation)."""

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self.pattern, self.flags = pattern, flags

    def __getattr__(self, name: str):
        rx = self.__dict__.get("_rx")
        if rx is None:
            rx = self.__dict__["_rx"] = re.compile(self.pattern, self.flags)
        return getattr(rx, name)


def _lazy_rx(pattern: str, flags: int = 0) -> _LazyRx:
    return _LazyRx(pattern, flags)


SELF = Path(__file__).resolve()
TOOLS_ALL = ("cursor", "cline", "claude", "codex")
DEFAULT_TOOLS = ("cursor", "cline")
BMAD_TOOL_IDS = {"cursor": "cursor", "cline": "cline", "claude": "claude-code", "codex": "codex"}
CHARS_PER_TOKEN = 4  # rough estimate; good enough for budgets (real tokenizers vary by ~20%)
BUDGET = {
    "phase": 1200,
    "stack": 1200,
    "core": 1100,  # AGENTS.md eos blocks incl. the product-profile block (~70-110 tokens) since v0.4
    "agents_md": 1600,
    "profile": 400,
    "desc_chars": 160,
    "rule": 800,
    "skill_descs": 500,
}
# Memory files: max non-empty lines (eos check). progress.md is appended forever unless capped.
MEMORY_CAPS = (
    ("memory/active-context.md", 40),
    ("memory/handoff.md", 30),
    ("docs/ai/lessons.md", 40),
    ("memory/progress.md", 200),
)
MANAGED_NOTE = "<!-- eos-managed from {src}; edit there + `eos sync` -->"
# Path-attached rules carry only what matters while editing; phase gates stay in the pack/skill (read on demand).
RULE_SECTIONS = ("## Standards", "## Automated checks")
IS_WINDOWS = os.name == "nt"
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "dist",
    "build",
    ".next",
    "__pycache__",
    ".eos",
    "_bmad",
    "_bmad-output",
    ".tox",
    "vendor",
    "target",
    ".turbo",
    "coverage",
    ".mypy_cache",
    ".ruff_cache",
}
# Known ecosystems without a shipped pack yet -> suggest `eos new-stack`.
UNSUPPORTED_MARKERS = {
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "jvm",
    "build.gradle.kts": "kotlin-jvm",
    "composer.json": "php",
    "artisan": "laravel",
    "Gemfile": "ruby",
    "pubspec.yaml": "flutter",
    "mix.exs": "elixir",
    "Package.swift": "swift",
    "deno.json": "deno",
}


# ----------------------------------------------------------------------------- small utilities
def eprint(*a: object) -> None:
    print(*a, file=sys.stderr)


def sha(text: str | bytes) -> str:
    data = text.encode() if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()[:16]


def tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write(p: Path, text: str, mode: int | None = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    if mode is not None and not IS_WINDOWS:
        os.chmod(p, mode)


def resolve_argv(argv: list[str]) -> list[str]:
    """Resolve a bare program name on PATH. shutil.which honours PATHEXT, so on Windows `npx` becomes
    C:\\Program Files\\nodejs\\npx.cmd (CreateProcess alone only tries .exe). Paths are left alone."""
    if argv and argv[0] and not os.path.dirname(argv[0]):
        found = shutil.which(argv[0])
        if found:
            return [found, *argv[1:]]
    return argv


def split_cmd(cmd: str) -> list[str]:
    """Split a command line. On Windows backslashes are path separators, not escapes, so split
    non-POSIX and drop the surrounding quotes (POSIX splitting turns C:\\tools\\x.exe into C:toolsx.exe)."""
    if not IS_WINDOWS:
        return shlex.split(cmd)
    return [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w for w in shlex.split(cmd, posix=False)]


def popen_args(argv: list[str]) -> list[str] | str:
    """What to hand to subprocess. A Windows shell step ["cmd", "/c", <command line>] becomes one verbatim
    command line: in a list, Python would escape the user's quotes as \\" (MSVC rules), which cmd.exe does not
    understand, so `"C:\\Users\\Jane Doe\\python.exe" lint.py` broke. /s keeps everything between the outer quotes
    as typed (what shell=True does); /d skips AutoRun macros. Everything else: resolve the program on PATH."""
    if IS_WINDOWS and len(argv) == 3 and argv[0] == "cmd" and argv[1] == "/c":
        return f'"{os.environ.get("COMSPEC") or "cmd.exe"}" /d /s /c "{argv[2]}"'
    return resolve_argv(argv)


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 60, env: dict | None = None) -> tuple[int, str]:
    args = popen_args(cmd)
    cmd = args if isinstance(args, list) else cmd
    try:
        r = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            check=False,
        )
        rc = 127 if isinstance(args, str) and r.returncode == 9009 else r.returncode  # cmd.exe: not recognized
        return rc, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: {' '.join(cmd)}"


def find_eos_home() -> Path | None:
    env = os.environ.get("EOS_HOME")
    for cand in ([Path(env)] if env else []) + [SELF.parent.parent]:
        if (cand / "packs" / "phases").is_dir() and (cand / "core").is_dir():
            return cand.resolve()
    return None


def eos_version(home: Path | None) -> str:
    if home and (home / "VERSION").exists():
        return read(home / "VERSION").strip()
    return "unknown"


# ----------------------------------------------------------------------------- frontmatter + packs
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Tiny YAML subset: `key: value`, `key: "quoted"`, `key: [json, list]`. Enough for our own packs."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    meta: dict = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, val = line.partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {line!r}")
        val = val.strip()
        if val.startswith("["):
            try:
                meta[key.strip()] = json.loads(val)
            except ValueError:  # unquoted list: [a, b]
                meta[key.strip()] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
        elif val.startswith('"'):
            meta[key.strip()] = json.loads(val)
        else:
            meta[key.strip()] = val
    return meta, text[end + 5 :]


REQUIRED_PACK_KEYS = ("id", "title", "kind", "mode", "when", "description", "globs")
PHASE_SECTIONS = (
    "## Entry",
    "## Standards",
    "## Deliverables",
    "## Automated checks",
    "## Exit checklist",
    "## Handoff",
    "## Stop & escalate",
)


class Pack:
    def __init__(self, path: Path, rel_src: str):
        self.path = path
        self.src = rel_src  # e.g. .eos/packs/phases/backend.md
        self.text = read(path)
        try:
            self.meta, self.body = parse_frontmatter(self.text)
        except ValueError as exc:
            raise SystemExit(f"{rel_src}: invalid frontmatter: {exc}") from None
        m = self.meta
        self.id: str = m.get("id", path.stem)
        self.kind: str = m.get("kind", "phase")
        self.mode: str = m.get("mode", "files")
        self.globs: list[str] = list(m.get("globs", []))
        self.description: str = m.get("description", "")
        self.when: str = m.get("when", "")

    def validate(self) -> list[str]:
        errs = []
        for k in REQUIRED_PACK_KEYS:
            if k not in self.meta:
                errs.append(f"{self.src}: missing frontmatter key '{k}'")
        if self.mode not in ("files", "intent", "both"):
            errs.append(f"{self.src}: mode must be files|intent|both")
        if self.mode in ("files", "both") and not self.globs:
            errs.append(f"{self.src}: mode '{self.mode}' needs globs")
        for g in self.globs:
            if "," in g or "{" in g:
                errs.append(f"{self.src}: glob {g!r} must not contain ',' or braces (Cursor globs are comma-separated)")
        if self.mode in ("intent", "both") and len(self.description) > BUDGET["desc_chars"]:
            errs.append(f"{self.src}: description {len(self.description)} chars > {BUDGET['desc_chars']}")
        limit = BUDGET[self.kind] if self.kind in BUDGET else BUDGET["phase"]
        if tokens(self.text) > limit:
            errs.append(f"{self.src}: ~{tokens(self.text)} tokens > budget {limit}")
        if self.mode in ("files", "both") and tokens(rule_slice(self)) > BUDGET["rule"]:
            errs.append(f"{self.src}: path-rule slice ~{tokens(rule_slice(self))} tokens > {BUDGET['rule']}")
        if self.kind == "phase":
            for s in PHASE_SECTIONS:
                if s not in self.body:
                    errs.append(f"{self.src}: missing section '{s}'")
        return errs


def load_home_packs(home: Path) -> tuple[dict[str, Pack], dict[str, Pack]]:
    phases = {p.stem: Pack(p, f"packs/phases/{p.name}") for p in sorted((home / "packs/phases").glob("*.md"))}
    stacks = {}
    for d in sorted((home / "packs/stacks").iterdir()):
        if d.is_dir() and (d / "STACK.md").exists() and not d.name.startswith("_"):
            stacks[d.name] = Pack(d / "STACK.md", f"packs/stacks/{d.name}/STACK.md")
    return phases, stacks


def load_project_packs(root: Path) -> tuple[dict[str, Pack], dict[str, Pack]]:
    base = root / ".eos/packs"
    phases = {p.stem: Pack(p, f".eos/packs/phases/{p.name}") for p in sorted((base / "phases").glob("*.md"))}
    stacks = {p.stem: Pack(p, f".eos/packs/stacks/{p.name}") for p in sorted((base / "stacks").glob("*.md"))}
    return phases, stacks


# ----------------------------------------------------------------------------- stack detection
def iter_files(root: Path, depth: int = 3):
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            yield rel / f


def _contains(path: Path, words: list[str]) -> bool:
    try:
        if path.stat().st_size > 2_000_000:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return any(re.search(rf"(?<![\w-]){re.escape(w.lower())}(?![\w-])", text) for w in words)


def as_dirs(v) -> list[str]:
    """Manifest `stacks` values are a dir (str) or, in monorepos, a list of dirs (since v0.5)."""
    if isinstance(v, str):
        return [v]
    return [str(x) for x in (v or [])]


def primary_dir(v) -> str:
    d = as_dirs(v)
    return d[0] if d else "."


def _within(child: str, parent: str) -> bool:
    return parent in (".", "") or child == parent or child.startswith(parent.rstrip("/") + "/")


def _pack_dirs(found: dict[str, list[str]]) -> dict[str, str | list[str]]:
    return {k: (v[0] if len(v) == 1 else v) for k, v in sorted(found.items())}


def detect_stacks(root: Path, stacks: dict[str, Pack]) -> tuple[dict[str, str | list[str]], list[str]]:
    """Return ({stack_id: dir or [dirs]}, [ecosystems found that have no pack yet]).

    Every directory with a stack's marker is wired (monorepos: apps/web + apps/admin, services/*), except
    directories nested inside one already found for the same stack (a workspace root covers its members)."""
    found: dict[str, list[str]] = {}
    unsupported: set[str] = set()
    files = sorted(iter_files(root), key=lambda p: (len(p.parts), str(p)))
    for rel in files:
        name = rel.name
        if name in UNSUPPORTED_MARKERS:
            unsupported.add(UNSUPPORTED_MARKERS[name])
        if name.endswith(".csproj"):
            unsupported.add("dotnet")
        d = rel.parent.as_posix() or "."
        for sid, pack in stacks.items():
            if any(_within(d, x) for x in found.get(sid, [])):
                continue
            markers = pack.meta.get("markers", [])
            if not any(fnmatch.fnmatch(name, m) for m in markers):
                continue
            words = pack.meta.get("contains", [])
            if words and not _contains(root / rel, words):
                continue
            found.setdefault(sid, []).append(d)
    changed = True  # requirements: nextjs -> typescript, python-fastapi -> python (same dir)
    while changed:
        changed = False
        for sid in list(found):
            for req in stacks[sid].meta.get("requires", []):
                if req not in stacks:
                    continue
                for d in found[sid]:
                    if not any(_within(d, x) for x in found.get(req, [])):
                        found.setdefault(req, []).append(d)
                        changed = True
    unsupported -= set(found)
    return _pack_dirs(found), sorted(unsupported)


def detect_pm(node_dir: Path) -> str:
    for lock, pm in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ):
        if (node_dir / lock).exists():
            return pm
    try:
        pm_field = json.loads(read(node_dir / "package.json")).get("packageManager", "")
        for pm in ("pnpm", "yarn", "bun", "npm"):
            if pm_field.startswith(pm):
                return pm
    except (OSError, ValueError):
        pass
    return "pnpm"


PM_INFO = {
    "pnpm": {
        "dir": "pnpm --dir {d}",
        "exec": "pnpm exec",
        "install": "pnpm install --frozen-lockfile",
        "audit": "pnpm audit --prod",
        "lock": "pnpm-lock.yaml",
        "setup": "      - uses: pnpm/action-setup@0977fd99725f1db4007ccb2928dbb4e90d06cc86 # v6.0.10\n        with:\n          package_json_file: {d}/package.json\n      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n        with:\n"
        "          node-version: 24\n          cache: pnpm\n          cache-dependency-path: {d}/pnpm-lock.yaml\n",
    },
    "npm": {
        "dir": "npm --prefix {d}",
        "exec": "npx",
        "install": "npm ci",
        "audit": "npm audit --omit=dev",
        "lock": "package-lock.json",
        "setup": "      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n        with:\n          node-version: 24\n          cache: npm\n"
        "          cache-dependency-path: {d}/package-lock.json\n",
    },
    "yarn": {
        "dir": "yarn --cwd {d}",
        "exec": "yarn",
        "install": "yarn install --immutable",
        "audit": "yarn npm audit --environment production",
        "lock": "yarn.lock",
        "setup": "      - run: corepack enable\n      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n        with:\n          node-version: 24\n"
        "          cache: yarn\n          cache-dependency-path: {d}/yarn.lock\n",
    },
    "bun": {
        "dir": "bun --cwd {d}",
        "exec": "bunx",
        "install": "bun install --frozen-lockfile",
        "audit": "bun audit",
        "lock": "bun.lock",
        "setup": "      - uses: oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0\n",
    },
}


# ----------------------------------------------------------------------------- managed writes
BLOCK_ORDER = ["core", "product", "topology", "workspace", "stack", "map", "ws-core", "ws-repos", "ws-contracts"]


def block_region(name: str, body: str) -> str:
    b, e = f"<!-- eos:{name}:begin -->", f"<!-- eos:{name}:end -->"
    return f"{b}\n{body.strip()}\n{e}" if body.strip() else f"{b}\n{e}"


class Writer:
    """Applies a file plan with ownership rules and records hashes in the manifest."""

    def __init__(self, root: Path, manifest: dict, dry: bool, force: bool, adopt: bool = False):
        self.root, self.manifest, self.dry, self.force = root, manifest, dry, force
        self.adopt = adopt  # existing project: never touch files eos did not create; suggest instead
        self.files: dict[str, str] = manifest.setdefault("files", {})
        self.report: list[tuple[str, str]] = []
        self.touched: set[str] = set()

    def _log(self, status: str, rel: str) -> None:
        self.report.append((status, rel))

    def managed(self, rel: str, content: str, mode: int | None = None) -> None:
        """eos owns the file, unless you edited it: then we write <file>.eos-new next to it."""
        self.touched.add(rel)
        p = self.root / rel
        blocker = self._file_in_path(p)
        if blocker:
            return self._log(f"SKIPPED ({blocker} is a file, not a folder)", rel)
        if not p.exists():
            self._do_write(p, content, mode)
            self.files[rel] = sha(content)
            return self._log("created", rel)
        cur = read(p)
        if cur == content:
            self.files[rel] = sha(content)
            return self._log("unchanged", rel)
        if self.force or self.files.get(rel) == sha(cur):
            self._do_write(p, content, mode)
            self.files[rel] = sha(content)
            return self._log("updated", rel)
        if self.adopt and rel not in self.files:  # yours from before eos: leave it, park our version
            self._do_write(self.root / ".eos/suggested" / rel, content, mode)
            return self._log("kept yours (eos version in .eos/suggested/)", rel)
        self._do_write(p.with_name(p.name + ".eos-new"), content, mode)
        self._log("CONFLICT (kept yours, wrote .eos-new)", rel)

    def prune(self, prefixes: tuple[str, ...]) -> None:
        """Remove generated files no longer in the plan (e.g. a pack the profile dropped). Edited ones stay."""
        for rel in sorted(self.files):
            if rel in self.touched or not rel.startswith(prefixes):
                continue
            p = self.root / rel
            if p.exists() and sha(read(p)) != self.files[rel] and not self.force:
                self._log("kept (edited; no longer selected)", rel)
                continue
            if not self.dry:
                if p.exists():
                    p.unlink()
                d = p.parent
                while d != self.root and d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
                    d = d.parent
                del self.files[rel]
            self._log("removed", rel)

    def seed(self, rel: str, content: str) -> None:
        """Written once; yours afterwards (memory files, ADR index, config)."""
        p = self.root / rel
        if p.exists():
            return self._log("kept", rel)
        blocker = self._file_in_path(p)
        if blocker:
            return self._log(f"SKIPPED ({blocker} is a file, not a folder)", rel)
        self._do_write(p, content)
        self._log("created", rel)

    def blocks(self, rel: str, blocks: dict[str, str], template: str) -> None:
        """Replace only <!-- eos:NAME:begin --> ... <!-- eos:NAME:end --> regions; the rest is yours.

        An empty body empties an existing region and adds nothing where there is none (e.g. no topology)."""
        p = self.root / rel
        existed = p.exists()
        cur = read(p) if existed else template
        new = cur
        for name in sorted(blocks, key=lambda n: BLOCK_ORDER.index(n) if n in BLOCK_ORDER else 99):
            body = blocks[name]
            b, e = f"<!-- eos:{name}:begin -->", f"<!-- eos:{name}:end -->"
            region = block_region(name, body)
            if b in new and e in new:
                new = re.sub(re.escape(b) + r".*?" + re.escape(e), lambda _m, r=region: r, new, flags=re.DOTALL)
                continue
            if not body.strip():
                continue
            prev = (
                [n for n in BLOCK_ORDER[: BLOCK_ORDER.index(name)] if f"<!-- eos:{n}:end -->" in new]
                if (name in BLOCK_ORDER)
                else []
            )
            if prev:  # keep the documented order: insert after the previous eos block
                end = f"<!-- eos:{prev[-1]}:end -->"
                i = new.index(end) + len(end)
                new = new[:i] + "\n\n" + region + new[i:]
                continue
            lines = new.split("\n", 1)  # existing file without markers: insert after the title line
            if lines[0].startswith("# ") and len(lines) > 1:
                new = lines[0] + "\n\n" + region + "\n" + lines[1]
            else:
                new = region + "\n\n" + new
        if existed and new == cur:
            return self._log("unchanged", rel)
        self._do_write(p, new)
        self._log("updated blocks" if existed else "created", rel)

    def append_lines(self, rel: str, lines: list[str]) -> None:
        p = self.root / rel
        cur = read(p) if p.exists() else ""
        have = set(cur.splitlines())
        missing = [ln for ln in lines if ln not in have]
        if not missing:
            return self._log("unchanged", rel)
        sep = "" if (not cur or cur.endswith("\n")) else "\n"
        self._do_write(p, cur + sep + "\n".join(missing) + "\n")
        self._log(f"appended {len(missing)} lines", rel)

    def json_hooks(self, rel: str, ours: dict, key: str) -> None:
        """Merge hook entries into an existing JSON config: replace older eos entries, keep everything else."""
        p = self.root / rel
        try:
            cur = json.loads(read(p)) if p.exists() else {}
        except ValueError:
            return self._log("SKIPPED (invalid JSON, fix by hand)", rel)
        merged = json.loads(json.dumps(cur))
        for k, v in ours.items():
            if k != key:
                merged.setdefault(k, v)
        dst = merged.setdefault(key, {})
        for event, entries in ours[key].items():
            existing = [x for x in dst.get(event, []) if HOOK_MARK not in json.dumps(x)]
            dst[event] = existing + entries
        content = json.dumps(merged, indent=2) + "\n"
        if p.exists() and read(p) == content:
            return self._log("unchanged", rel)
        self._log("merged" if p.exists() else "created", rel)
        self._do_write(p, content)

    def _file_in_path(self, p: Path) -> str | None:
        d = p.parent
        while d != self.root and self.root in d.parents:
            if d.is_file():
                return d.relative_to(self.root).as_posix()
            d = d.parent
        return None

    def _do_write(self, p: Path, content: str, mode: int | None = None) -> None:
        if not self.dry:
            write(p, content, mode)


# ----------------------------------------------------------------------------- rendering adapters
def fm_list(key: str, items: list[str]) -> str:
    return f"{key}:\n" + "".join(f'  - "{i}"\n' for i in items)


def rule_slice(pk: Pack) -> str:
    """Edit-time slice of a phase pack (title + Standards + Automated checks + pointer). Stack packs stay whole."""
    body = pk.body.lstrip("\n")
    if pk.kind != "phase":
        return body
    parts = re.split(r"(?m)^(?=## )", body)
    keep = [parts[0]] + [p for p in parts[1:] if p.startswith(RULE_SECTIONS)]
    out = "".join(keep).rstrip() + "\n"
    if len(keep) < len(parts):
        more = ", deep references" if deep_refs_of(pk) else ""
        out += (
            f"\nEntry, deliverables, exit checklist{more} and handoff: read `{pk.src}` when starting or finishing"
            " this phase.\n"
        )
    return out


def scoped_globs(pk: Pack, stack_dirs: dict | None) -> list[str]:
    """Stack packs attach only inside their own directory (a FastAPI `api/app/` must not pull in Next.js rules)."""
    dirs = as_dirs((stack_dirs or {}).get(pk.id, ".")) if pk.kind == "stack" else ["."]
    out: list[str] = []
    for d in dirs:
        d = d.strip("/").removeprefix("./")
        if d in ("", "."):
            return pk.globs
        out += [g if g.startswith(d + "/") else f"{d}/{g}" for g in pk.globs]
    return out


# Which skill folders each tool scans (verified 2026-10-10; docs/research/v0.7-native-capabilities.md).
# Cursor and Cline list every SKILL.md they find and do not merge same-name skills, so writing one skill to
# several of their folders lists it twice on every request. skill_dirs() picks folders so each tool sees one copy.
SKILL_READERS = {
    "project": {
        ".claude/skills": {"claude", "cursor", "cline"},
        ".agents/skills": {"cursor", "codex"},
        ".cline/skills": {"cline"},
    },
    "global": {
        ".claude/skills": {"claude", "cursor"},
        ".agents/skills": {"cursor", "codex"},
        ".cline/skills": {"cline"},
    },
}


def skill_dirs(tools: list[str] | set[str], scope: str = "project") -> tuple[list[str], list[str]]:
    """Return (folders to write, tools left without native skills). A tool is skipped rather than given a
    second folder that another selected tool also scans; skipped tools use .eos/packs/INDEX.md (AGENTS.md says so)."""
    want = [t for t in ("claude", "cline", "cursor", "codex") if t in tools]
    readers = SKILL_READERS[scope]
    chosen: list[str] = []
    seen: dict[str, int] = {}
    for t in want:
        if seen.get(t):
            continue
        native = {"claude": ".claude/skills", "cline": ".cline/skills"}.get(t, ".agents/skills")
        for d, who in sorted(readers.items(), key=lambda kv: (-len(kv[1] & set(want)), kv[0] != native)):
            if t in who and all(not seen.get(o) for o in who & set(want)):
                chosen.append(d)
                for o in who & set(want):
                    seen[o] = 1
                break
    return chosen, [t for t in want if not seen.get(t)]


def render_adapters(
    packs: list[Pack], tools: list[str], stack_dirs: dict | None = None
) -> dict[str, tuple[str, int | None]]:
    """Return {relpath: (content, mode)} for every per-tool adapter file. One pack -> thin per-tool copies.

    Path rules never carry a description (it would be listed every request, and "both" packs are already
    listed once as a skill). Skills carry the full pack.
    """
    out: dict[str, tuple[str, int | None]] = {}
    sdirs = skill_dirs(tools)[0]
    for pk in packs:
        note = MANAGED_NOTE.format(src=pk.src)
        body = pk.body.lstrip("\n")
        rbody = rule_slice(pk)
        globs = scoped_globs(pk, stack_dirs)
        name = f"eos-{pk.id}"
        auto = pk.mode in ("files", "both") and bool(pk.globs)
        intent = pk.mode in ("intent", "both")
        if "cursor" in tools and auto:
            out[f".cursor/rules/{name}.mdc"] = (
                f"---\nglobs: {','.join(globs)}\nalwaysApply: false\n---\n{note}\n{rbody}",
                None,
            )
        if "cline" in tools and auto:
            out[f".clinerules/{name}.md"] = (f"---\n{fm_list('paths', globs)}---\n{note}\n{rbody}", None)
        if "claude" in tools and auto:
            out[f".claude/rules/{name}.md"] = (f"---\n{fm_list('paths', globs)}---\n{note}\n{rbody}", None)
        if intent:
            skill = f"---\nname: {name}\ndescription: {json.dumps(pk.description)}\n---\n{note}\n{body}"
            for d in sdirs:
                out[f"{d}/{name}/SKILL.md"] = (skill, None)
    if packs:
        idx = ["# Pack index (read one line, then only the pack you need)", ""]
        idx += [f"- {pk.id}: {pk.when} → `{pk.src}`" for pk in packs]
        out[".eos/packs/INDEX.md"] = ("\n".join(idx) + "\n", None)
    return out


def render_agents_blocks(
    core_md: str,
    phases: list[Pack],
    stacks: list[Pack],
    stack_dirs: dict[str, str],
    pm: str,
    tools: list[str],
    product: str | None = None,
    gates: str | None = None,
    project_map: str | None = None,
) -> dict[str, str]:
    rows = []
    ratchet = gates == "ratchet"
    for s in stacks:
        dl = as_dirs(stack_dirs.get(s.id, "."))
        d = "`, `".join(dl[:4]) + (f"` +{len(dl) - 4} more (docs/eos/project-map.md)`" if len(dl) > 4 else "")
        fast = s.meta.get("fast_check", "").replace("{pm}", pm)
        full = s.meta.get("full_check", "").replace("{pm}", pm)
        base = ", ".join(s.meta.get("requires", [])) or "base pack"
        if ratchet:  # whole-repo formatters would rewrite legacy code: scope to what you touched
            fast_s = "format + lint only the files you changed" if fast else f"(as {base})"
            rows.append(f"| {s.id} | `{d}` | {fast_s} | tests for what you touched |")
            continue
        rows.append(
            f"| {s.id} | `{d}` | {f'`{fast}`' if fast else f'(as {base})'} | "
            f"{f'`{full}`' if full else f'(as {base})'} |"
        )
    if ratchet:
        stack_md = (
            "## Stacks & checks (ratchet: old violations are baselined; only new ones fail)\n"
            "| Stack | Dir | While iterating | Before saying done |\n|---|---|---|---|\n"
            + ("\n".join(rows) if rows else "| (none detected) | | | |")
            + "\nDone = `python3 .eos/bin/eos.py ratchet check` green + tests green. Never mass-reformat or fix"
            " unrelated old code in the same change; if a count drops, `eos ratchet update`."
        )
    else:
        stack_md = (
            '## Stacks & checks (run in Dir; "done" = full check green)\n'
            "| Stack | Dir | Fast check (while iterating) | Full check (before saying done) |\n|---|---|---|---|\n"
            + ("\n".join(rows) if rows else "| (none detected) | | create a pack: `eos new-stack` | |")
        )
    auto = [t for t in ("cursor", "cline", "claude") if t in tools]
    idx = "read `.eos/packs/INDEX.md`, then only the one pack the task needs."
    lines = ["## Packs (just in time)"]
    if auto:
        lines.append(
            f"In Cursor, Cline and Claude Code, packs attach by file path or load as skills. Other tools: {idx}"
        )
    else:
        lines.append(idx[0].upper() + idx[1:])
    if project_map:
        lines.append(f"Project map (folders, commands, hot spots): `{project_map}`. Read it before exploring.")
    out = {"core": core_md.strip(), "stack": stack_md, "map": "\n".join(lines)}
    if product:
        out["product"] = product
    return out


EOS_STUB = """#!/usr/bin/env python3
# eos-managed: entry point for `python3 .eos/bin/eos.py <command>`. The code is in eos_impl.py and is
# imported, so Python caches its bytecode in .eos/bin/__pycache__. Running the 13k-line file directly made
# Python recompile it on every call (measured: ~215 -> ~70 ms per command, v0.7.1 efficiency evaluation).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eos_impl  # noqa: E402

if __name__ == "__main__":
    sys.exit(eos_impl.main())
sys.modules[__name__] = eos_impl  # `import eos` (hook.py, tests) gets the real module
"""


def write_project_cli(w: Writer) -> None:
    """.eos/bin/eos.py (tiny stub) + eos_impl.py (this file). SELF is the full module whether eos runs from the
    engineering-os checkout or from a project's own copy."""
    w.managed(".eos/bin/eos.py", EOS_STUB, 0o755)
    w.managed(".eos/bin/eos_impl.py", read(SELF), 0o644)


HOOK_MARK = ".eos/bin/"  # any hook entry containing this is eos's (eos.py in <=0.5, hook.py since 0.6)
# Agent hooks fire on every tool call, so they start through a tiny launcher that imports eos.py: Python then
# caches the bytecode in .eos/bin/__pycache__ instead of recompiling 6k lines each time (measured: ~90 -> ~45 ms).
HOOK_PY = """#!/usr/bin/env python3
# eos-managed: fast entry point for agent hooks (imports eos.py so its bytecode is cached between calls).
import os
import sys


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import eos

    return int(eos.main(["guard", *sys.argv[1:]]))


sys.exit(main())
"""


def hooks_configs(py: str) -> dict:
    g = f"{py} .eos/bin/hook.py"
    cursor = {
        "version": 1,
        "hooks": {
            "beforeShellExecution": [{"command": f"{g} cursor-shell", "timeout": 15}],
            "preToolUse": [{"command": f"{g} cursor-tool", "timeout": 15}],
            "beforeReadFile": [{"command": f"{g} cursor-read", "timeout": 10}],
            "beforeMCPExecution": [{"command": f"{g} cursor-mcp", "timeout": 10}],
            "stop": [{"command": f"{g} cursor-stop", "timeout": 240, "loop_limit": 3}],
        },
    }
    cg = f'{py} "$CLAUDE_PROJECT_DIR/.eos/bin/hook.py"'
    claude = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit|Read",
                    "hooks": [{"type": "command", "command": f"{cg} claude-tool", "timeout": 15}],
                }
            ],
            "Stop": [{"hooks": [{"type": "command", "command": f"{cg} claude-stop", "timeout": 240}]}],
        }
    }
    cline = (
        "#!/usr/bin/env sh\n# eos-managed: Cline PreToolUse hook -> shared guard (Cline hooks: macOS/Linux).\n"
        f'exec {py} "$(dirname "$0")/../../.eos/bin/hook.py" cline-tool\n'
    )
    return {"cursor": cursor, "claude": claude, "cline": cline}


def dir_slug(d: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", d.lower()).strip("-") or "root"


def _scope_fragment(txt: str, d: str, first: bool) -> str:
    """One stack in several dirs: local hooks get a dir suffix and only see their dir's files; remote hook
    repos (e.g. ruff, which already covers every file) are kept once."""
    blocks = re.split(r"(?m)^(?=  - repo: )", txt)
    out = []
    for b in blocks:
        if not b.strip():
            continue
        if not b.startswith("  - repo: local"):
            if first:
                out.append(b)
            continue
        slug = dir_slug(d)
        hooks = re.split(r"(?m)^(?=      - id: )", b)
        head, items = hooks[0], hooks[1:]
        new_items = []
        for h in items:
            h = re.sub(r"^      - id: ([\w-]+)", lambda m, s=slug: f"      - id: {m.group(1)}-{s}", h, count=1)
            h = re.sub(r"(?m)^(        name: )(.*)$", lambda m, dd=d: f"{m.group(1)}{m.group(2)} [{dd}]", h, count=1)
            fm = re.search(r"(?m)^        files: '(.*)'$", h)
            scope = "^" + re.escape(d) + "/"
            if fm:
                h = h.replace(fm.group(0), f"        files: '{scope}.*(?:{fm.group(1)})'")
            else:
                h = h.rstrip("\n") + f"\n        files: '{scope}'\n"
            new_items.append(h)
        out.append(head + "".join(new_items))
    return "".join(out)


RATCHET_HOOK = """  # --- ratchet: old violations are baselined in .eos/baseline; only new ones block (eos ratchet) ---
  - repo: local
    hooks:
      - id: eos-ratchet
        name: eos ratchet (no new lint/type/boundary violations)
        entry: python .eos/bin/eos.py ratchet check
        language: python
        pass_filenames: false
        always_run: true
        stages: [pre-push]"""


def wants_conventional(root: Path) -> bool:
    """Conventional commit messages pay off only when a tool builds releases from them."""
    v = _load_cfg(root).get("conventional_commits")
    if v is not None:
        return bool(v)
    return (root / "release-please-config.json").exists() or (root / ".release-please-manifest.json").exists()


def compose_precommit(
    home: Path, stack_dirs: dict, pm: str, gates: str | None = None, conventional: bool = True
) -> str:
    base = read(home / "core/pre-commit/base.yaml").rstrip("\n")
    if not conventional:  # no commit-msg stage at all: one less hook run (~0.2 s) on every commit
        base = base.replace("[pre-commit, commit-msg, pre-push]", "[pre-commit, pre-push]")
        base = re.sub(r"\n      - id: eos-commit-msg\n(?:        .*\n?)+", "\n", base).rstrip("\n")
    parts = [base]
    if gates == "ratchet":  # stack hooks run whole-repo formatters/linters: parked in .eos/suggested until tightened
        return "\n".join([*parts, RATCHET_HOOK]) + "\n"
    for sid, v in stack_dirs.items():
        frag = home / f"packs/stacks/{sid}/pre-commit.yaml"
        if not frag.exists():
            continue
        dirs = as_dirs(v)
        for i, d in enumerate(dirs):
            txt = read(frag).replace("{{PY_DIR}}", d).replace("{{NODE_DIR}}", d).replace("{{DIR}}", d)
            txt = txt.replace("{{PM}}", pm)
            txt = txt.replace("{{PM_DIR}}", PM_INFO[pm]["dir"].format(d=d))
            if len(dirs) > 1:
                txt = _scope_fragment(txt, d, i == 0)
            if txt.strip():
                parts.append(f"  # --- stack: {sid}{f' ({d})' if len(dirs) > 1 else ''} ---\n" + txt.rstrip("\n"))
    return "\n".join(parts) + "\n"


def render_ci_all(home: Path, stack_dirs: dict, pm: str) -> list[tuple[str, str]]:
    """One workflow per stack, or per (stack, dir) in monorepos: each with its own path filter."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sid, v in stack_dirs.items():
        dirs = as_dirs(v)
        for d in dirs:
            r = render_ci(home, sid, d, pm)
            if not r:
                continue
            rel, txt = r
            if len(dirs) > 1:
                base = Path(rel).stem
                new = f"{base}-{dir_slug(d)}"
                txt = re.sub(rf"(?m)^name:\s*{re.escape(base)}\s*$", f"name: {new}", txt)
                txt = txt.replace(f".github/workflows/{base}.yml", f".github/workflows/{new}.yml")
                txt = re.sub(r'"\*\*/', f'"{d.rstrip("/")}/**/', txt)
                rel = f".github/workflows/{new}.yml"
            if rel not in seen:
                seen.add(rel)
                out.append((rel, txt))
    return out


def render_ci(home: Path, sid: str, d: str, pm: str) -> tuple[str, str] | None:
    src = home / f"packs/stacks/{sid}/ci.yml"
    if not src.exists():
        return None
    info = PM_INFO[pm]
    txt = read(src).replace("{{PY_DIR}}", d).replace("{{NODE_DIR}}", d).replace("{{DIR}}", d).replace("{{PM}}", pm)
    prefix = "" if d in (".", "") else d.rstrip("/") + "/"
    vers = read_versions(home)
    txt = txt.replace("{{PREFIX}}", prefix).replace("{{FLUTTER_VERSION}}", vers.get("flutter", "stable"))
    txt = (
        txt.replace("{{PM_SETUP}}", info["setup"].format(d=d))
        .replace("{{PM_INSTALL}}", info["install"])
        .replace("{{PM_AUDIT}}", info["audit"])
        .replace("{{LOCKFILE}}", info["lock"])
        .replace("{{PM_EXEC}}", info["exec"])
        .replace("{{NODE_PREFIX}}", "" if d in (".", "") else d.rstrip("/") + "/")
    )
    m = re.search(r"^name:\s*(\S+)", txt, re.MULTILINE)
    return f".github/workflows/{m.group(1) if m else 'ci-' + sid}.yml", txt


# ----------------------------------------------------------------------------- project profiles + questionnaire
# key, question, allowed answers (first = what a bare Enter keeps when nothing is known: "unknown")
QUESTIONS = (
    ("money", "Does the product move money (payments, wallets, mobile money)?", ("unknown", "yes", "no")),
    ("personal_data", "Does it store personal or sensitive data?", ("unknown", "yes", "no")),
    ("llm", "Does the product itself call LLMs or run AI agents?", ("unknown", "yes", "no")),
    (
        "scale",
        "Users in 12 months: small (<10k), medium (10k-1M), large (>1M)?",
        ("unknown", "small", "medium", "large"),
    ),
    ("low_bandwidth", "Many users on low-end phones or slow/expensive networks?", ("unknown", "yes", "no")),
)
# first matching detected stack decides the suggested profile; nothing matched -> "full" (all packs, v0.3 behaviour)
STACK_PROFILE_HINTS = (
    ("react-native-expo", "mobile"),
    ("flutter", "mobile"),
    ("nextjs", "web-app"),
    ("python-fastapi", "api"),
    ("python-flask", "api"),
)


def load_profiles(home: Path) -> dict:
    return json.loads(read(home / "core/profiles.json"))


def guess_profile(stack_ids) -> str:
    ids = set(stack_ids)
    return next((prof for sid, prof in STACK_PROFILE_HINTS if sid in ids), "full")


def parse_answers(s: str | None) -> dict[str, str]:
    """`money=yes,scale=large` -> dict; unknown keys or values stop with a clear message."""
    out: dict[str, str] = {}
    allowed = {k: c for k, _q, c in QUESTIONS}
    for item in (s or "").split(","):
        if not item.strip():
            continue
        k, _, v = item.partition("=")
        k, v = k.strip().replace("-", "_"), v.strip().lower()
        if k not in allowed:
            raise SystemExit(f"unknown answer '{k}'. Keys: {', '.join(allowed)}")
        if v not in allowed[k]:
            raise SystemExit(f"answer {k}={v!r} must be one of: {', '.join(allowed[k])}")
        out[k] = v
    return out


def complete_answers(answers: dict) -> dict[str, str]:
    return {k: answers.get(k, "unknown") for k, _q, _c in QUESTIONS}


def security_level(answers: dict) -> int:
    """Fail-safe default: unknown money/personal-data answers count as yes (ASVS L2)."""
    risky = any(answers.get(k, "unknown") in ("yes", "unknown") for k in ("money", "personal_data"))
    return 2 if risky else 1


def select_phases(
    spec: dict, profile: str, answers: dict, phases: dict, mode: str | None = None, topology: str | None = None
) -> list[str]:
    """Files-mode packs always (free until a matching file is edited); intent/both packs per profile,
    plus the packs the lifecycle mode and repo topology need (profiles.json by_mode / by_topology)."""
    if profile not in spec["profiles"]:
        raise SystemExit(f"unknown profile '{profile}'. Profiles: {', '.join(spec['profiles'])}")
    prof = spec["profiles"][profile]
    skills = set(phases) if "*" in prof["skills"] else set(spec["base"]) | set(prof["skills"])
    if answers.get("scale") in ("medium", "large"):
        skills.add("performance-scale")
    skills |= set(spec.get("by_mode", {}).get(mode or "", []))
    skills |= set(spec.get("by_topology", {}).get(topology or "", []))
    return [pid for pid, pk in phases.items() if pk.mode == "files" or pid in skills]


MODES = ("greenfield", "brownfield", "rewrite", "maintain")
MODE_ALIASES = {
    "refonte": "rewrite",
    "replatform": "rewrite",
    "re-platform": "rewrite",
    "migration": "rewrite",
    "ideation": "greenfield",
    "new": "greenfield",
    "adopt": "brownfield",
    "existing": "brownfield",
    "legacy": "brownfield",
    "maintenance": "maintain",
    "scale-up": "maintain",
    "mature": "maintain",
}
MODE_TITLES = {
    "greenfield": "new product (no code yet, or very little)",
    "brownfield": "existing codebase being adopted and improved",
    "rewrite": "refactor / re-platform / rewrite ('refonte') of an existing system",
    "maintain": "mature product: maintenance and scale-up",
}
MODE_LINES = {
    "brownfield": "- Existing code: keep new code clean, leave unrelated old code alone, and add a characterization"
    " test before changing untested code.",
    "rewrite": "- Rewrite in progress (`docs/migration/`): old and new must behave the same (parity tests) until"
    " cutover; every slice is reversible (migration skill).",
    "maintain": "- Mature product: small reversible changes (flags, expand/contract), watch SLOs, no drive-by refactors.",
}
TEACH_LINE = "- Teaching mode: explain each decision in 1-2 plain sentences (the principle and why it applies); define jargon once."


# Plain glosses (3-6 words) for terms eos prints to people. Shown once, in parentheses, next to the term.
MODE_PLAIN = {
    "greenfield": "a brand-new project",
    "brownfield": "existing code you're improving",
    "rewrite": "replacing an old system step by step",
    "maintain": "a live product you keep running",
}
TOPOLOGY_PLAIN = {
    "single": "one app in one repo",
    "monorepo": "several apps in one repo",
    "modular-monolith": "one app split into modules",
    "microservices": "many small separate services",
}
GATES_PLAIN = {
    "strict": "every problem blocks a commit",
    "ratchet": "old problems allowed, new ones blocked",
}
PLAIN_TERMS = {  # for `eos next` / `eos status` with teaching on (first occurrence only)
    "characterization tests": "tests that record today's behaviour",
    "golden-master": "saved output to compare against",
    "hot spots": "the most-changed files",
    "linters": "tools that flag code problems",
    "ratchet": "old problems allowed, new ones blocked",
    "ADR": "a short written decision record",
    "PRD": "the written requirements",
    "SLO": "a reliability target users feel",
    "runbook": "step-by-step fix instructions",
    "P0/P1": "most urgent items",
    "seam": "the switch between old and new",
    "parity": "behaves exactly like before",
    "cutover": "switching users to the new system",
    "acceptance criteria": "how we know it's done",
    "PR": "a reviewed change request",
}


def gloss(text: str, seen: set[str]) -> str:
    """Add a plain gloss after the first use of each jargon term (case-sensitive for acronyms)."""
    for term, plain in PLAIN_TERMS.items():
        if term in seen:
            continue
        flags = 0 if term.isupper() or "/" in term else re.IGNORECASE
        m = re.search(rf"(?<![\w`/.-]){re.escape(term)}s?(?![\w`/-])", text, flags)
        if m:
            text = f"{text[: m.end()]} ({plain}){text[m.end() :]}"
            seen.add(term)
    return text


def _answers_kept_line(profile: str | None, how: str) -> str:
    return (
        f"answers: kept your earlier answers (project type: {profile or 'not set'}). To change them: "
        f"`eos {how} --reconfigure` (asks the questions again), or without questions, e.g. "
        f"`eos {how} --reconfigure --profile web-app --answers money=yes`."
    )


TOOL_NAMES = {"cursor": "Cursor", "cline": "Cline", "claude": "Claude Code", "codex": "Codex"}
FRONTEND_FW = ("Next.js", "Nuxt", "Angular", "Svelte", "Vue", "React")
BACKEND_FW = ("NestJS", "Express", "Fastify", "Django", "FastAPI", "Flask")
MOBILE_FW = ("Expo", "React Native")
LANG_NAMES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".rs": "Rust",
    ".ex": "Elixir",
    ".dart": "Dart",
}


def _join_words(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def describe_project(facts: dict, frameworks, topology: str | None = None) -> str:
    """One plain sentence: what kind of project this is, its history and how well it's tested."""
    fw = set(frameworks or [])
    front = [f for f in FRONTEND_FW if f in fw]
    back = [f for f in BACKEND_FW if f in fw]
    mobile = [f for f in MOBILE_FW if f in fw]
    if "Next.js" in front or "Nuxt" in front:  # Next.js is built on React, Nuxt on Vue: name the framework only
        front = [f for f in front if f not in ("React", "Vue")]
    if facts.get("code_files", 0) == 0:
        return "A new project (no code yet)"
    if mobile:
        what = f"A mobile app built with {mobile[0]}" + (f" and a {back[0]} backend" if back else "")
    elif front and back:
        what = f"A web app with a {_join_words(front[:2])} frontend and a {_join_words(back[:2])} backend"
    elif front:
        what = f"A web app built with {_join_words(front[:2])}"
    elif back:
        what = f"A backend (server) built with {_join_words(back[:2])}"
    else:
        langs = []
        for ext in facts.get("by_ext", {}):
            name = LANG_NAMES.get(ext)
            if name and name not in langs:
                langs.append(name)
        what = f"A project written in {_join_words(langs[:3])}" if langs else "A project"
    if topology == "monorepo":
        what += ", several apps in one repo"
    code, tests = facts.get("code_files", 0), facts.get("test_files", 0)
    ratio = tests / code if code else 0
    tested = (
        "no tests yet"
        if tests == 0
        else "few tests"
        if ratio < 0.1
        else "some tests"
        if ratio < 0.3
        else "a good number of tests"
    )
    hist = f"{facts['commits']} commits" if facts.get("git") else "not in git yet"
    return f"{what}; {hist}, {code} code files, {tested} ({tests} test file{'' if tests == 1 else 's'})."


def project_frameworks(root: Path, base=()) -> set[str]:
    """Frameworks named in every package.json / pyproject.toml / requirements.txt up to 3 folders deep, so a
    monorepo's apps (apps/web: Next.js, apps/api: NestJS) are described even when the stack is detected at the root."""
    fws = set(base or ())
    dirs = {
        rel.parent for rel in iter_files(root, 4) if rel.name in ("package.json", "pyproject.toml", "requirements.txt")
    }
    for d in sorted(dirs)[:200]:
        fws |= {FRAMEWORK_DEPS[k] for k in _deps(root / d) if k in FRAMEWORK_DEPS}
    return fws


def plain_summary(
    found: str, tools: list[str], hooks: bool, ci: bool, ratchet: bool, docs: list[tuple[str, str]]
) -> str:
    """The 4-line, jargon-free ending of init/adopt/start, for someone who isn't an engineer."""
    names = [TOOL_NAMES.get(t, t) for t in tools]
    setup = [f"rules for {_join_words(names)}" if names else "rules for your AI tools"]
    if hooks:
        setup.append("checks that run each time you commit")
    if ci:
        setup.append("the same checks on GitHub")
    if ratchet:
        setup.append("a starting point that won't fail you for old problems, only new ones")
    lines = [
        "In plain words:",
        f"  Found : {found}",
        f"  Set up: {_join_words(setup)}.",
        "  Read  : " + "; ".join(f"{p} ({why})" for p, why in docs) + ".",
        "  Next  : run `eos next` here. It names the one next step, says why, and gives the exact sentence to "
        "paste into " + ("Cline or Cursor" if "cline" in tools else "your AI chat") + ".",
    ]
    return "\n".join(lines)


def norm_mode(m: str | None) -> str | None:
    if not m:
        return None
    m = MODE_ALIASES.get(m.lower(), m.lower())
    if m not in MODES:
        raise SystemExit(f"unknown mode '{m}'. Modes: {', '.join(MODES)} (refonte = rewrite)")
    return m


def product_block(
    profile: str | None, answers: dict | None, mode: str | None = None, teaching: str | None = None
) -> str | None:
    """Short always-on summary of what this product is; drives security level and which packs matter."""
    if not profile:
        return None
    a = complete_answers(answers or {})

    def show(k: str) -> str:
        v = a[k]
        return "unknown (=yes)" if v == "unknown" and k in ("money", "personal_data") else v

    lvl = security_level(a)
    lines = [
        "## Product profile (set by `eos init --profile/--answers`)",
        (
            f"Type: {profile}. Money: {show('money')}. Personal data: {show('personal_data')}. LLM features: {a['llm']}. "
            f"Scale (12 mo): {a['scale']}. Low-end devices: {a['low_bandwidth']}."
        ),
        f"- Security target: OWASP ASVS 5.0 L{lvl}"
        + (f" + MASVS L{lvl}" if profile == "mobile" else "")
        + "; humans review money, auth, PII.",
    ]
    if a["low_bandwidth"] == "yes":
        lines.append("- Low-end devices: small payloads, offline-tolerant, test on a cheap Android phone.")
    if a["llm"] == "yes":
        lines.append("- LLM features: model input is untrusted (agent-security pack).")
    if a["scale"] == "large":
        lines.append("- Large scale: SLOs + capacity model before launch (performance-scale pack).")
    elif a["scale"] == "small":
        lines.append("- Small scale: no premature scaling (one DB, modular monolith).")
    if mode in MODE_LINES:
        lines.append(MODE_LINES[mode])
    if teaching == "on":
        lines.append(TEACH_LINE)
    return "\n".join(lines)


def workspace_block(ws: dict | None) -> str:
    """This repo's place in a multi-repo workspace (set by `eos workspace sync`)."""
    if not ws or not ws.get("self"):
        return ""
    me = ws["self"]
    others = [f"{r['name']} ({r.get('role', '?')})" for r in ws.get("repos", []) if r.get("name") != me]
    return "\n".join(
        [
            f"## Workspace: {ws.get('name', 'workspace')} (this repo = `{me}`, {ws.get('role', '?')})",
            f"- Sibling repos in `../`: {', '.join(others[:8]) or 'none'}. Map, contracts and owners: `../AGENTS.md`.",
            (
                "- A change that spans repos gets a plan (`eos workspace change`) and linked PRs; contract changes go"
                " provider-first and additive. Each repo's own rules and checks apply inside it."
            ),
        ]
    )


def extra_blocks(cfg: dict) -> dict[str, str]:
    """Per-project AGENTS.md blocks besides core/stack/map ('' = not applicable: region emptied/omitted)."""
    return {
        "product": product_block(cfg.get("profile"), cfg.get("answers"), cfg.get("mode"), cfg.get("teaching")) or "",
        "topology": topology_block(cfg.get("topology"), cfg.get("topology_details")),
        "workspace": workspace_block(cfg.get("workspace")),
    }


def ask_questions(spec: dict, profile: str, answers: dict, ask=input) -> tuple[str, dict[str, str]]:
    """Interactive questionnaire (TTY or --interactive). Enter keeps the shown default."""
    names = list(spec["profiles"])
    print("Project questionnaire (Enter keeps the default in brackets)")
    for i, n in enumerate(names, 1):
        print(f"  {i}. {n:<14} {spec['profiles'][n]['title']}")
    while True:
        raw = ask(f"Project type [{profile}]: ").strip()
        if not raw:
            break
        pick = names[int(raw) - 1] if raw.isdigit() and 0 < int(raw) <= len(names) else raw
        if pick in names:
            profile = pick
            break
        print(f"  choose 1-{len(names)} or a name")
    out = complete_answers(answers)
    for k, q, choices in QUESTIONS:
        while True:
            raw = ask(f"{q} ({'/'.join(choices)}) [{out[k]}]: ").strip().lower()
            if not raw:
                break
            match = [c for c in choices if c.startswith(raw)]
            if len(match) == 1:
                out[k] = match[0]
                break
            print(f"  answer one of: {', '.join(choices)}")
    return profile, out


# ----------------------------------------------------------------------------- topology (repo shape)
TOPOLOGIES = ("single", "monorepo", "modular-monolith", "microservices")
MONOREPO_FILES = {
    "pnpm-workspace.yaml": "pnpm workspaces",
    "turbo.json": "Turborepo",
    "nx.json": "Nx",
    "lerna.json": "Lerna",
    "rush.json": "Rush",
    "go.work": "Go workspace",
}
BOUNDARY_FILES = (
    ".importlinter",
    ".dependency-cruiser.js",
    ".dependency-cruiser.cjs",
    ".dependency-cruiser.mjs",
    ".dependency-cruiser.json",
    "packwerk.yml",
    "tach.toml",
)
SERVICE_ROOTS = ("services", "svc", "microservices")
MODULE_ROOTS = ("modules", "domains", "contexts", "bounded_contexts")
UNIT_MARKERS = (
    "Dockerfile",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Cargo.toml",
    "composer.json",
    "Gemfile",
    "mix.exs",
)
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".kt", ".rb", ".php", ".cs", ".rs", ".ex", ".dart")


def _has_code(d: Path, depth: int = 3) -> bool:
    for _dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in SKIP_DIRS and not x.startswith(".")]
        if any(f.endswith(CODE_EXT) for f in fn):
            return True
        if len(Path(_dp).relative_to(d).parts) >= depth:
            dn[:] = []
    return False


def compose_build_services(root: Path) -> list[str]:
    """Service names with a `build:` in compose.yaml / docker-compose.yml (no YAML parser: 2-space keys)."""
    for name in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"):
        p = root / name
        if not p.exists():
            continue
        out, cur, in_services = [], None, False
        for line in read(p).splitlines():
            if re.match(r"^services:\s*$", line):
                in_services = True
                continue
            if in_services and re.match(r"^\S", line):
                in_services = False
            if not in_services:
                continue
            m = re.match(r"^  ([\w.-]+):\s*$", line)
            if m:
                cur = m.group(1)
            elif cur and re.match(r"^\s{4,}build:", line) and cur not in out:
                out.append(cur)
        return out
    return []


def detect_topology(root: Path, stack_dirs: dict) -> tuple[str, list[str], dict]:
    """(topology, plain-words evidence, details). Detection only suggests; `--topology` or the manifest decides."""
    ev: list[str] = []
    tools = [label for f, label in MONOREPO_FILES.items() if (root / f).exists()]
    try:
        if "workspaces" in json.loads(read(root / "package.json")):
            tools.append("package.json workspaces")
    except (OSError, ValueError):
        pass
    for f, marker, label in (
        ("pyproject.toml", "[tool.uv.workspace]", "uv workspace"),
        ("Cargo.toml", "[workspace]", "Cargo workspace"),
    ):
        if (root / f).exists() and marker in read(root / f):
            tools.append(label)
    if tools:
        ev.append(f"monorepo tooling: {', '.join(tools)}")
    units = sorted({x for v in stack_dirs.values() for x in as_dirs(v) if x not in (".", "")})
    services: list[str] = []
    for sr in SERVICE_ROOTS:
        base = root / sr
        if base.is_dir():
            for c in sorted(base.iterdir()):
                if c.is_dir() and not c.name.startswith((".", "_")) and any((c / m).exists() for m in UNIT_MARKERS):
                    services.append(f"{sr}/{c.name}")
    if len(services) >= 2:
        ev.append(f"{len(services)} deployable services: {', '.join(services[:6])}")
    else:
        built = compose_build_services(root)
        if len(built) >= 3:
            services = built
            ev.append(f"compose builds {len(built)} services: {', '.join(built[:6])}")
    module_root, modules = "", []
    for dp, dn, _fn in os.walk(root):
        rel = Path(dp).relative_to(root)
        dn[:] = [
            x for x in dn if x not in SKIP_DIRS and not x.startswith(".") and x not in ("tests", "test", "node_modules")
        ]
        if len(rel.parts) >= 4:
            dn[:] = []
        if rel.name in MODULE_ROOTS and not any(p in SERVICE_ROOTS for p in rel.parts):
            kids = sorted(c.name for c in Path(dp).iterdir() if c.is_dir() and not c.name.startswith((".", "_")))
            kids = [k for k in kids if _has_code(Path(dp) / k)]
            if len(kids) >= 2:
                module_root, modules = rel.as_posix(), kids
                ev.append(f"{len(kids)} modules in {module_root}/: {', '.join(kids[:6])}")
                break
    boundary = []
    for f in BOUNDARY_FILES:
        hits = [p for p in iter_files(root, 2) if p.name == f]
        boundary += [h.as_posix() for h in hits]
    for f in ("pyproject.toml", "setup.cfg"):
        for h in (p for p in iter_files(root, 2) if p.name == f):
            if "importlinter" in read(root / h):
                boundary.append(f"{h.as_posix()} [importlinter]")
    if boundary:
        ev.append(f"boundary checks: {', '.join(boundary)}")
    if len(services) >= 2:
        topo = "microservices"
    elif modules or boundary:
        topo = "modular-monolith"
    elif tools or len({u.split("/")[0] for u in units}) >= 2 or len(units) >= 2:
        topo = "monorepo"
        if not tools:
            ev.append(f"{len(units)} apps/packages: {', '.join(units[:6])}")
    else:
        topo = "single"
    details = {
        "monorepo_tools": tools,
        "apps": units,
        "services": services,
        "module_root": module_root,
        "modules": modules,
        "boundary_checks": boundary,
    }
    return topo, ev, details


def _names(items: list[str], n: int = 6) -> str:
    short = [i.rsplit("/", 1)[-1] for i in items]
    return ", ".join(short[:n]) + (f" +{len(short) - n}" if len(short) > n else "")


def topology_block(topo: str | None, det: dict | None) -> str:
    """Always-on, a few lines: the boundary rule agents most often break in each repo shape."""
    det = det or {}
    if topo == "modular-monolith":
        mr = det.get("module_root") or "src/modules"
        mods = det.get("modules") or []
        return "\n".join(
            [
                f"## Architecture: modular monolith (`{mr}/`{': ' + _names(mods) if mods else ''})",
                (
                    "- A module uses another only through its public API (`api` module or package `__init__`/`index`);"
                    " never its internals or tables."
                ),
                (
                    "- Boundary check: `eos scaffold boundaries` (import-linter / dependency-cruiser); its error says the fix."
                    " New module: `eos new module <name>`. Owners: `docs/architecture/modules.md`."
                ),
            ]
        )
    if topo == "microservices":
        svcs = det.get("services") or []
        return "\n".join(
            [
                f"## Architecture: microservices ({_names(svcs) or 'services/'})",
                (
                    "- A service owns its data: never read another service's DB. Call others only through their contract"
                    " (OpenAPI / proto / AsyncAPI); change contracts additively (expand, migrate, then contract)."
                ),
                (
                    "- Catalog + owners: `docs/architecture/services.md`. New service: `eos new service <name>`."
                    " Run locally: `docker compose up`."
                ),
            ]
        )
    if topo == "monorepo":
        apps = det.get("apps") or []
        return "\n".join(
            [
                f"## Repo layout: monorepo ({_names(apps) or 'several apps'})",
                (
                    "- Check the app or package you changed (table below). Apps never import each other;"
                    " shared code goes in a package with an owner."
                ),
            ]
        )
    return ""


# ----------------------------------------------------------------------------- lifecycle mode
TEST_RX = _lazy_rx(r"(^|/)(tests?|__tests__|spec|e2e)(/|$)|(_test|\.test|\.spec|_spec)\.\w+$|(^|/)test_[^/]+\.py$")
CI_FILES = (
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    ".circleci/config.yml",
    ".drone.yml",
    ".woodpecker.yml",
    ".buildkite",
)


def git_out(root: Path, *a: str, timeout: int = 20) -> str:
    code, out = run(["git", *a], cwd=root, timeout=timeout)
    return out.strip() if code == 0 else ""


def repo_facts(root: Path) -> dict:
    """Cheap, offline facts about a repo (no network, no builds): sizes, git history, CI, tests."""
    code_files, test_files, by_ext = 0, 0, {}
    for rel in iter_files(root, 6):
        s = rel.as_posix()
        if rel.suffix in CODE_EXT:
            code_files += 1
            by_ext[rel.suffix] = by_ext.get(rel.suffix, 0) + 1
            if TEST_RX.search(s):
                test_files += 1
    is_git = (root / ".git").exists()
    commits = git_out(root, "rev-list", "--count", "HEAD") if is_git else ""
    first = git_out(root, "log", "--reverse", "--format=%ct", "--max-parents=0") if is_git else ""
    tags = git_out(root, "tag", "--list") if is_git else ""
    age_days = 0
    if first.split():
        age_days = int((time.time() - int(first.split()[0])) / 86400)
    return {
        "code_files": code_files,
        "test_files": test_files,
        "by_ext": dict(sorted(by_ext.items(), key=lambda kv: -kv[1])),
        "git": is_git,
        "commits": int(commits) if commits.isdigit() else 0,
        "tags": len(tags.splitlines()) if tags else 0,
        "age_days": age_days,
        "ci": [c for c in CI_FILES if (root / c).exists()],
    }


def detect_mode(root: Path, facts: dict | None = None) -> tuple[str, list[str]]:
    """Suggest a lifecycle mode from what is on disk; the user confirms (`eos mode set`)."""
    f = facts or repo_facts(root)
    ev = [f"{f['code_files']} source files, {f['test_files']} test files, {f['commits']} commits, {f['tags']} tags"]
    plans = list((root / "docs/migration").glob("*/plan.md")) + list((root / "docs/migration").glob("*.md"))
    if plans:
        return "rewrite", ev + [f"migration plan found: {plans[0].relative_to(root).as_posix()}"]
    if f["code_files"] < 5:
        return "greenfield", ev + ["little or no code yet"]
    if (f["age_days"] >= 365 and f["tags"] >= 3) or f["commits"] >= 1000:
        return "maintain", ev + [f"history of {f['age_days']} days with releases: a mature product"]
    return "brownfield", ev + ["existing code"]


CONTRACT_GLOBS = ("openapi.yaml", "openapi.yml", "openapi.json", "asyncapi.yaml", "asyncapi.yml", "*.proto")


def find_contracts(d: Path) -> list[str]:
    out = []
    for rel in iter_files(d, 3):
        if any(fnmatch.fnmatch(rel.name, g) for g in CONTRACT_GLOBS):
            out.append(rel.as_posix())
    return sorted(out)[:3]


def seed_catalogs(home: Path, root: Path, cfg: dict, w: Writer) -> None:
    """Service / module catalog, seeded once from what was detected (yours afterwards)."""
    det = cfg.get("topology_details") or {}
    if cfg.get("topology") == "microservices" and det.get("services"):
        rows = []
        for s in det["services"]:
            c = find_contracts(root / s) if (root / s).is_dir() else []
            contract = ", ".join(f"`{s}/{x}`" for x in c) or "<add a contract>"
            rows.append(f"| {s.rsplit('/', 1)[-1]} | <owner> | <purpose> | {contract} | <services> | <store> | <SLO> |")
        w.seed(
            "docs/architecture/services.md",
            read(home / "core/templates/architecture/services.md").rstrip("\n") + "\n" + "\n".join(rows) + "\n",
        )
    if cfg.get("topology") == "modular-monolith" and det.get("modules"):
        mr = det.get("module_root", "")
        rows = [f"| {m} | <owner> | <capability, tables> | `{mr}/{m}` public API | <modules> |" for m in det["modules"]]
        w.seed(
            "docs/architecture/modules.md",
            read(home / "core/templates/architecture/modules.md").rstrip("\n") + "\n" + "\n".join(rows) + "\n",
        )


def cmd_topology(args: argparse.Namespace) -> int:
    """Show the detected repo shape (and why); `set` confirms one and refreshes AGENTS.md."""
    home = find_eos_home()
    root = Path(args.dir).resolve()
    m = load_manifest(root)
    if home:
        _, stacks = load_home_packs(home)
        sd = m.get("stacks") or detect_stacks(root, stacks)[0]
    else:
        sd = m.get("stacks", {})
    topo, ev, det = detect_topology(root, sd)
    if args.action == "set":
        if args.value not in TOPOLOGIES:
            eprint(f"topology must be one of: {', '.join(TOPOLOGIES)}")
            return 2
        if not m:
            eprint("not an eos project yet: `eos init --topology ...` or `eos adopt`")
            return 2
        m["topology"], m["topology_details"] = args.value, det
        save_manifest(root, m)
        print(f"topology set to {args.value}. Run `eos update` to add/remove the packs it needs.")
        _resync(root)
        return 0
    print(f"detected: {topo}" + (f"   (saved: {m.get('topology')})" if m.get("topology") else ""))
    for e in ev:
        print(f"  why: {e}")
    if args.json:
        print(json.dumps({"detected": topo, "saved": m.get("topology"), "details": det}, indent=2))
    return 0


def cmd_mode(args: argparse.Namespace) -> int:
    """Show the detected lifecycle mode (and why); `set` confirms one."""
    root = Path(args.dir).resolve()
    m = load_manifest(root)
    mode, ev = detect_mode(root)
    if args.action == "set":
        new = norm_mode(args.value)
        if not m:
            eprint("not an eos project yet: `eos start`, `eos init --mode ...` or `eos adopt`")
            return 2
        m["mode"] = new
        save_manifest(root, m)
        print(
            f"mode set to {new} ({MODE_TITLES[new]}). Run `eos update` to add the packs it needs; `eos next` for the next step."
        )
        _resync(root)
        return 0
    print(f"detected: {mode} ({MODE_TITLES[mode]})" + (f"   (saved: {m.get('mode')})" if m.get("mode") else ""))
    for e in ev:
        print(f"  why: {e}")
    print("  modes: " + ", ".join(MODES) + "  (refonte = rewrite)")
    return 0


def cmd_teach(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    m = load_manifest(root)
    if not m:
        eprint("not an eos project")
        return 2
    if args.value:
        m["teaching"] = args.value
        save_manifest(root, m)
        _resync(root)
    print(
        f"teaching mode: {m.get('teaching') or 'off'}  "
        "(on = agents explain each decision in plain words and suggest the next step; off = terse)"
    )
    return 0


def cmd_gates(args: argparse.Namespace) -> int:
    """strict = every check on every file; ratchet = old violations baselined, only new ones fail (brownfield)."""
    root = Path(args.dir).resolve()
    m = load_manifest(root)
    if not m:
        eprint("not an eos project")
        return 2
    if args.value and args.value != (m.get("gates") or "strict"):
        if args.value == "ratchet" and not (root / RATCHET_FILE).exists():
            print("  tip: run `eos ratchet init` to record the baseline")
        m["gates"] = args.value
        save_manifest(root, m)
        if find_eos_home():
            ns = argparse.Namespace(
                dir=str(root),
                dry_run=False,
                force=False,
                verbose=False,
                no_ci=True,
                no_precommit=False,
                bmad=False,
                strict=False,
            )
            cmd_init(ns, update=True)
        else:
            _resync(root)
            print("  run `eos update` from your engineering-os checkout to refresh pre-commit hooks")
    print(
        f"gates: {m.get('gates') or 'strict'}  (strict = whole-repo checks block; "
        "ratchet = only new violations block, `eos ratchet check`)"
    )
    return 0


# ----------------------------------------------------------------------------- init / update / sync
CFG_KEYS = (
    "tools",
    "stacks",
    "phases",
    "python",
    "pm",
    "project_name",
    "profile",
    "answers",
    "mode",
    "teaching",
    "topology",
    "topology_details",
    "workspace",
    "gates",
    "project_map",
)
PRUNE_PREFIXES = (
    ".eos/packs/phases/",
    ".eos/packs/stacks/",
    ".eos/packs/ref/",
    ".eos/packs/vendor/",
    ".cursor/rules/eos-",
    ".clinerules/eos-",
    ".claude/rules/eos-",
    ".agents/skills/eos-",
    ".cline/skills/eos-",
    ".claude/skills/eos-",
)


def manifest_path(root: Path) -> Path:
    return root / ".eos/manifest.json"


def load_manifest(root: Path) -> dict:
    p = manifest_path(root)
    return json.loads(read(p)) if p.exists() else {}


def save_manifest(root: Path, manifest: dict) -> None:
    write(manifest_path(root), json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def project_plan(cfg: dict, w: Writer, phases: dict[str, Pack], stacks: dict[str, Pack], core_md: str) -> None:
    """AGENTS.md blocks + every adapter + hook config, from the packs as they exist in the project."""
    tools = cfg["tools"]
    sel_phases = [phases[p] for p in cfg["phases"] if p in phases]
    sel_stacks = [stacks[s] for s in cfg["stacks"] if s in stacks]
    blocks = render_agents_blocks(
        core_md,
        sel_phases,
        sel_stacks,
        cfg["stacks"],
        cfg.get("pm", "pnpm"),
        tools,
        gates=cfg.get("gates"),
        project_map=cfg.get("project_map"),
    )
    blocks.update(extra_blocks(cfg))
    w.blocks("AGENTS.md", blocks, cfg.get("_agents_template", "# AGENTS.md\n"))
    for rel, (content, mode) in sorted(render_adapters(sel_phases + sel_stacks, tools, cfg["stacks"]).items()):
        w.managed(rel, content, mode)
    hk = hooks_configs(cfg.get("python", "python3"))
    if "cursor" in tools:
        w.json_hooks(".cursor/hooks.json", hk["cursor"], "hooks")
    if "claude" in tools:
        w.json_hooks(".claude/settings.json", hk["claude"], "hooks")
        cp = w.root / "CLAUDE.md"
        if cp.exists() and "CLAUDE.md" not in w.files:
            if "@AGENTS.md" not in read(cp):  # yours: add only a marked import line, keep the rest
                w.blocks("CLAUDE.md", {"claude-import": "@AGENTS.md"}, "")
        elif cfg.get("_claude_md"):
            w.managed("CLAUDE.md", cfg["_claude_md"])
    if "cline" in tools:
        w.managed(".clinerules/hooks/PreToolUse", hk["cline"], 0o755)


def resolve_stacks(args: argparse.Namespace, root: Path, stacks: dict[str, Pack]) -> tuple[dict[str, str], list[str]]:
    if args.stacks in (None, "auto"):
        return detect_stacks(root, stacks)
    if args.stacks == "none":
        return {}, []
    acc: dict[str, list[str]] = {}
    for item in args.stacks.split(","):
        sid, _, d = item.strip().partition(":")
        if sid not in stacks:
            raise SystemExit(f"unknown stack '{sid}'. Available: {', '.join(stacks)}")
        if (d or ".") not in acc.setdefault(sid, []):
            acc[sid].append(d or ".")  # repeat an id for several dirs: python:svc/a,python:svc/b
    for sid in list(acc):
        for req in stacks[sid].meta.get("requires", []):
            for d in acc[sid]:
                if not any(_within(d, x) for x in acc.get(req, [])):
                    acc.setdefault(req, []).append(d)
    return _pack_dirs(acc), []


def cmd_init(args: argparse.Namespace, update: bool = False) -> int:
    home = find_eos_home()
    if not home:
        eprint("engineering-os repo not found (set EOS_HOME). init/update run from your engineering-os checkout.")
        return 2
    root = Path(args.dir).resolve()
    manifest = load_manifest(root)
    if update and not manifest:
        eprint(f"{root} has no .eos/manifest.json: run `eos init` first.")
        return 2
    if not update and not manifest and root.is_dir() and (looks_like_workspace(root) or (root / WS_FILE).exists()):
        eprint(
            f"{root} holds several git repos ({', '.join(find_child_repos(root)[:5])}): that is a multi-repo workspace.\n"
            "  Run `eos workspace init` here, and `eos adopt <repo>` (or `eos init <repo>`) inside each repo."
        )
        return 2
    if not update and not args.dry_run:
        root.mkdir(parents=True, exist_ok=True)
    phases, stacks = load_home_packs(home)
    spec = load_profiles(home)
    unsupported: list[str] = []
    adopt = bool(getattr(args, "adopt", False) or manifest.get("adopted"))  # adopted once = never clobber
    evidence: list[str] = []
    # --reconfigure (or --profile/--answers on a set-up project): ask again, current answers as defaults
    reconf = bool(manifest) and bool(
        getattr(args, "reconfigure", False) or getattr(args, "profile", None) or getattr(args, "answers", None)
    )
    answers_note = ""  # one plain line when a re-run silently keeps the earlier answers
    prev_phases = list(manifest.get("phases", []))
    if update:
        cfg = {k: manifest[k] for k in CFG_KEYS if k in manifest}
        if cfg.get("topology"):  # the confirmed shape stays; its details (new services, modules) refresh
            cfg["topology_details"] = detect_topology(root, cfg.get("stacks", {}))[2]
        prof = cfg.get("profile") or "full"  # projects from v0.3 and earlier had every pack
        if getattr(args, "teach", None):
            cfg["teaching"] = args.teach
        if reconf:
            answers = dict(cfg.get("answers", {}))
            answers.update(parse_answers(getattr(args, "answers", None)))
            prof = getattr(args, "profile", None) or prof
            tty = sys.stdin.isatty() and sys.stdout.isatty()
            if getattr(args, "interactive", False) or (
                tty and not getattr(args, "yes", False) and not args.dry_run and not getattr(args, "profile", None)
            ):
                prof, answers = ask_questions(spec, prof, answers)
            elif not getattr(args, "profile", None) and not getattr(args, "answers", None):
                answers_note = (
                    "answers: no terminal to ask on, so nothing changed. Use `--interactive`, or give "
                    "`--profile <type> --answers key=value,...`."
                )
            cfg["profile"], cfg["answers"] = prof, complete_answers(answers)
            # exactly what the new answers select: packs no longer wanted are pruned below (eos-owned and
            # unedited only; edited ones are kept and reported)
            cfg["phases"] = select_phases(spec, prof, cfg["answers"], phases, cfg.get("mode"), cfg.get("topology"))
        else:
            want = select_phases(spec, prof, cfg.get("answers", {}), phases, cfg.get("mode"), cfg.get("topology"))
            keep = set(cfg.get("phases", [])) | set(want)
            cfg["phases"] = [pid for pid in phases if pid in keep]  # new packs arrive only if the profile wants them
            if getattr(args, "cmd", None) in ("update", "adopt"):
                answers_note = _answers_kept_line(cfg.get("profile"), args.cmd)
    else:
        tools = parse_tools(args.tools or ",".join(load_global_state().get("tools", DEFAULT_TOOLS)))
        stack_dirs, unsupported = resolve_stacks(args, root, stacks)
        node_dir = next((primary_dir(d) for s, d in stack_dirs.items() if stacks[s].meta.get("ci") == "node"), None)
        pm = args.pm or (detect_pm(root / node_dir) if node_dir else "pnpm")
        cfg = {
            "tools": tools,
            "stacks": stack_dirs,
            "phases": list(phases),
            "pm": pm,
            "python": args.python or ("python" if IS_WINDOWS else "python3"),
            "project_name": args.name or root.name,
        }
        answers = dict(manifest.get("answers", {}))
        answers.update(parse_answers(args.answers))
        profile = args.profile or manifest.get("profile") or guess_profile(stack_dirs)
        tty = sys.stdin.isatty() and sys.stdout.isatty()
        if args.interactive or (tty and not args.yes and not args.dry_run and not args.profile):
            profile, answers = ask_questions(spec, profile, answers)
        elif manifest and not reconf and getattr(args, "cmd", None) == "init":
            answers_note = _answers_kept_line(profile, "init")
        cfg["profile"] = profile
        cfg["answers"] = complete_answers(answers)
        topo, tev, det = detect_topology(root, stack_dirs)
        cfg["topology"] = getattr(args, "topology", None) or manifest.get("topology") or topo
        cfg["topology_details"] = det
        mode, mev = detect_mode(root)
        cfg["mode"] = norm_mode(getattr(args, "mode", None)) or manifest.get("mode") or mode
        cfg["teaching"] = getattr(args, "teach", None) or manifest.get("teaching") or "on"  # `eos teach off`
        cfg["gates"] = manifest.get("gates") or ("ratchet" if adopt else "strict")
        if manifest.get("workspace"):
            cfg["workspace"] = manifest["workspace"]
        elif (wr := find_ws_root(root.parent)) is not None:  # joining an existing workspace
            wsd = load_ws(wr)
            me = next((r for r in wsd.get("repos", []) if (wr / r.get("path", r["name"])).resolve() == root), None)
            if me:
                cfg["workspace"] = {
                    "self": me["name"],
                    "name": wsd.get("name", wr.name),
                    "role": me.get("role", "?"),
                    "repos": [{"name": x["name"], "role": x.get("role", "?")} for x in wsd["repos"]],
                }
        evidence = [f"mode {cfg['mode']}: " + "; ".join(mev)] + ([f"topology {topo}: " + "; ".join(tev)] if tev else [])
        cfg["phases"] = select_phases(spec, profile, cfg["answers"], phases, cfg["mode"], cfg["topology"])
    cfg["_agents_template"] = read(home / "core/templates/AGENTS.md").replace("{{PROJECT_NAME}}", cfg["project_name"])
    cfg["_claude_md"] = read(home / "core/templates/CLAUDE.md")
    w = Writer(root, manifest, args.dry_run, args.force, adopt=adopt)
    # 1. canonical copies inside the project (self-contained: hooks, pre-commit and CI need nothing else)
    core_md = read(home / "core/AGENTS.core.md")
    write_project_cli(w)
    w.managed(".eos/bin/hook.py", HOOK_PY, 0o755)
    # nearest-config-wins: your `ruff check .` / `ruff format --check .` skip eos's generated files
    w.managed(
        ".eos/ruff.toml",
        '# eos-managed: generated eos files are not your code; your linters skip them.\nexclude = ["*"]\n',
    )
    w.managed(".eos/packs/core.md", core_md)
    for pid in cfg["phases"]:
        w.managed(f".eos/packs/phases/{pid}.md", phases[pid].text)
    for sid in cfg["stacks"]:
        w.managed(f".eos/packs/stacks/{sid}.md", stacks[sid].text)
    # deep references: read on demand by packs, never always-on (docs/LIBRARY.md)
    sel = [phases[p] for p in cfg["phases"]] + [stacks[x] for x in cfg["stacks"]]
    for dest, src in refs_to_install(home, sel).items():
        w.managed(dest, read(src))
    if any(deep_refs_of(pk) for pk in sel):
        w.managed(".eos/packs/ref/INDEX.md", library_index_for(home, sel))
    w.managed(".eos/lifecycle.json", read(home / "core/lifecycle.json"))  # eos status / next (edit to adapt)
    w.managed(".eos/concepts.md", read(home / "core/concepts.md"))  # eos explain (never always-on)
    w.seed(".eos/protected.txt", read(home / "core/protected.txt"))
    w.seed(
        ".eos/config.json",
        json.dumps(
            {
                "loop_limit": 3,
                "stop_check": "auto",
                "stop_check_timeout": 180,
                "cline_ask": "cancel",
                "mcp_write_ask": True,
                "push_policy": "feature-branches",
                "protected_branches": ["main", "master", "develop", "trunk", "release/*", "production"],
            },
            indent=2,
        )
        + "\n",
    )
    # 2. memory + docs seeds (yours after creation)
    t = home / "core/templates"
    for rel, src in (
        ("memory/handoff.md", "memory/handoff.md"),
        ("docs/adr/INDEX.md", "adr/INDEX.md"),
        ("docs/adr/0000-template.md", "adr/0000-template.md"),
        ("docs/ai/lessons.md", "lessons.md"),
        ("docs/plans/tech-debt.md", "plans/tech-debt.md"),
    ):
        w.seed(rel, read(t / src))
    w.seed(".github/renovate.json", read(t / "renovate.json"))
    if not args.no_ci:  # PR/issue templates carry the AC -> test map and risk boxes the review needs
        for rel in (
            "pull_request_template.md",
            "ISSUE_TEMPLATE/story.yml",
            "ISSUE_TEMPLATE/bug.yml",
            "ISSUE_TEMPLATE/config.yml",
        ):
            w.seed(f".github/{rel}", read(t / "github" / rel))
    w.append_lines(".gitignore", read(home / "core/gitignore.txt").splitlines())
    seed_catalogs(home, root, cfg, w)
    # 3. adapters, built from the packs as they now exist in the project (respects local pack edits)
    if args.dry_run or not (root / ".eos/packs").is_dir():
        pp = {k: v for k, v in phases.items() if k in cfg["phases"]}
        ps = {k: v for k, v in stacks.items() if k in cfg["stacks"]}
        for pk in list(pp.values()) + list(ps.values()):
            pk.src = f".eos/packs/{'phases' if pk.kind == 'phase' else 'stacks'}/{pk.id}.md"
        pcore = core_md
    else:
        pp, ps = load_project_packs(root)
        pcore = read(root / ".eos/packs/core.md")
    project_plan(cfg, w, pp, ps, pcore)
    w.prune(PRUNE_PREFIXES)  # packs/adapters the profile no longer selects (edited files are kept)
    # 4. quality gates
    if not args.no_precommit:
        w.managed(
            ".pre-commit-config.yaml",
            compose_precommit(home, cfg["stacks"], cfg["pm"], cfg.get("gates"), wants_conventional(root)),
        )
        if cfg.get("gates") == "ratchet":
            w.managed(
                ".eos/suggested/pre-commit-strict.yaml",
                compose_precommit(home, cfg["stacks"], cfg["pm"], None, wants_conventional(root)),
            )
    if not args.no_ci:
        w.managed(".github/workflows/eos-core.yml", read(home / "core/ci/eos-core.yml"))
        for rel, txt in render_ci_all(home, cfg["stacks"], cfg["pm"]):
            w.managed(rel, txt)
    # 5. manifest
    manifest.update({k: v for k, v in cfg.items() if not k.startswith("_")})
    if adopt:
        manifest["adopted"] = True
    manifest["eos_version"] = eos_version(home)
    manifest["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    manifest.setdefault("created", manifest["updated"])
    if not args.dry_run:
        save_manifest(root, manifest)
    if args.bmad:
        bmad_install(home, root, cfg["tools"], args.dry_run, w)
    # 6. report
    print(
        f"eos {'update' if update else 'init'} -> {root}  (eos {manifest['eos_version']}{', DRY RUN' if args.dry_run else ''})"
    )
    print(f"  tools : {', '.join(cfg['tools'])}")
    if cfg.get("profile"):
        a = cfg.get("answers", {})
        known = ", ".join(f"{k}={v}" for k, v in a.items() if v != "unknown") or "none (unknown = cautious defaults)"
        print(
            f"  profile: {cfg['profile']}  answers: {known}  -> security level ASVS L{security_level(a)} "
            "(OWASP checklist: L1 basic, L2 most apps, L3 critical)"
        )
        sc = spec["profiles"].get(cfg["profile"], {}).get("scaffolds", [])
        todo = [s for s in sc if s not in manifest.get("scaffolded", [])]
        if todo and (not update or reconf):
            print(f"  suggested scaffolds (ready-made starter files): {', '.join(todo)}  (eos scaffold <name>)")
        mp = spec["profiles"].get(cfg["profile"], {}).get("mcp_profile")
        if mp and (not update or reconf):
            print(
                f"  suggested MCP profile (connectors your AI tools use): eos mcp use {mp}"
                "  (machine-wide; switch per phase any time)"
            )
    if reconf:
        before = set(prev_phases)
        added = [p for p in cfg["phases"] if p not in before]
        dropped = [p for p in phases if p in before and p not in cfg["phases"]]
        print(
            f"  packs : {len(added)} added{' (' + ', '.join(added) + ')' if added else ''}, {len(dropped)} no longer"
            f" needed{' (' + ', '.join(dropped) + ')' if dropped else ''}: eos's own unedited copies are removed,"
            " files you edited are kept and listed below"
        )
    if cfg.get("mode") or cfg.get("topology"):
        mo, to, ga = cfg.get("mode") or "-", cfg.get("topology") or "-", cfg.get("gates") or "strict"
        print(
            f"  mode  : {mo}{' (' + MODE_PLAIN[mo] + ')' if mo in MODE_PLAIN else ''}   "
            f"shape: {to}{' (' + TOPOLOGY_PLAIN[to] + ')' if to in TOPOLOGY_PLAIN else ''}"
        )
        print(
            f"          teaching: {cfg.get('teaching') or 'off'} (agents explain their choices)   "
            f"gates: {ga}{' (' + GATES_PLAIN[ga] + ')' if ga in GATES_PLAIN else ''}"
        )
        for e in evidence:
            print(f"          why: {e}")
        if not update:
            print("          wrong? `eos mode set <mode>` / `eos topology set <shape>` (then `eos update`)")
    has_node = any(stacks[s].meta.get("ci") == "node" for s in cfg["stacks"] if s in stacks)
    print(
        f"  stacks: {', '.join(k + '@' + '+'.join(as_dirs(v)) for k, v in cfg['stacks'].items()) or '(none)'}"
        + (f"   (node package manager: {cfg['pm']})" if has_node else "")
    )
    for sid, v in cfg["stacks"].items():
        if not (stacks.get(sid) and stacks[sid].meta.get("ci") == "node"):
            continue
        for d in as_dirs(v):
            try:
                scripts = json.loads(read(root / d / "package.json")).get("scripts", {})
            except (OSError, ValueError):
                scripts = {}
            lacking = [x for x in ("lint", "typecheck", "test") if x not in scripts]
            if lacking:
                print(
                    f"  note: {d}/package.json has no script(s) {', '.join(lacking)}; hooks and CI call them (add them)."
                )
    if unsupported:
        print(f"  no pack yet for: {', '.join(unsupported)} -> `eos new-stack <id>` (see packs/stacks/_template)")
    counts: dict[str, int] = {}
    skipped: dict[str, list[str]] = {}
    for status, rel in w.report:
        counts[status] = counts.get(status, 0) + 1
        if status.startswith("SKIPPED") and not args.verbose:
            skipped.setdefault(status, []).append(rel)
            continue
        if status not in ("unchanged", "kept") and (
            args.verbose or status.startswith(("CONFLICT", "kept yours", "kept (edited"))
        ):
            print(f"  {status:<14} {rel}")
    for status, rels in skipped.items():
        print(f"  {status}: {len(rels)} file(s), e.g. {rels[0]}  (-v lists all)")
        blk = re.match(r"SKIPPED \((.+) is a file, not a folder\)", status)
        if blk:
            print(
                f"          -> {blk.group(1)} is a single file, but eos needs a folder with that name for these rules."
                f" Move it to {blk.group(1)}/project.md (the tool reads both), then run `eos update`."
            )
    print("  summary: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    conflicts = any(s.startswith("CONFLICT") for s, _ in w.report)
    if conflicts:
        print(
            "  conflicts: compare each <file> with <file>.eos-new, merge by hand, delete the .eos-new, run `eos sync`."
        )
    hooks_note = ""
    if not args.no_precommit and not args.dry_run and (root / ".git").exists():
        if shutil.which("pre-commit"):
            code, _ = run(["pre-commit", "install"], cwd=root, timeout=120)
            hooks_note = (
                "pre-commit hooks installed (checks that run when you commit)"
                if code == 0
                else "`pre-commit install` failed: run it by hand"
            )
            if code == 0 and sys.stdout.isatty() and not os.environ.get("EOS_NO_WARM"):
                # download hook tools now, in the background, while the network is up: the first commit then
                # doesn't stall (or fail) on a flaky connection. Log: .eos/state/hook-warm.log
                try:
                    (root / ".eos/state").mkdir(parents=True, exist_ok=True)
                    log = open(root / ".eos/state/hook-warm.log", "w", encoding="utf-8")  # noqa: SIM115
                    subprocess.Popen(
                        resolve_argv(["pre-commit", "install-hooks"]),
                        cwd=root,
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                    )
                    hooks_note += "; downloading hook tools in the background"
                except OSError:
                    pass
        else:
            hooks_note = "install pre-commit (`uv tool install pre-commit`), then `pre-commit install`"
    if hooks_note:
        print(f"  hooks : {hooks_note}")
    if answers_note:
        print("  " + answers_note)
    if not update and not getattr(args, "_from_adopt", False):
        print("  next: fill 'Project specifics' in AGENTS.md, commit `chore: add engineering-os`, then `eos doctor`.")
        if not args.dry_run:
            facts = repo_facts(root)
            fws = project_frameworks(root)
            print()
            print(
                plain_summary(
                    describe_project(facts, fws, cfg.get("topology")),
                    cfg["tools"],
                    hooks=not args.no_precommit,
                    ci=not args.no_ci,
                    ratchet=cfg.get("gates") == "ratchet",
                    docs=[
                        (
                            "AGENTS.md",
                            "the rules your AI tools follow; add your project's details under 'Project specifics'",
                        )
                    ],
                )
            )
    return 1 if conflicts and args.strict else 0


def bmad_install(home: Path, root: Path, tools: list[str], dry: bool, w: Writer) -> None:
    ver = read_versions(home).get("bmad-method", "latest")
    ids = ",".join(BMAD_TOOL_IDS[t] for t in tools if t in BMAD_TOOL_IDS)
    cmd = [
        "npx",
        "-y",
        f"bmad-method@{ver}",
        "install",
        "--directory",
        str(root),
        "--modules",
        "bmm",
        "--tools",
        ids,
        "--yes",
    ]
    print("  bmad  : " + " ".join(cmd))
    if not dry:
        if not shutil.which("npx"):
            print("  bmad  : SKIPPED, npx not found (BMAD needs Node >= 20.12)")
        else:
            code, out = run(cmd, cwd=root, timeout=900)
            print(f"  bmad  : {'ok' if code == 0 else f'FAILED (exit {code})'}")
            if code:
                print("\n".join(out.splitlines()[-15:]))
    for f in sorted((home / "integrations/bmad/custom").glob("*.toml")):
        w.seed(f"_bmad/custom/{f.name}", read(f))


def _project_cfg(root: Path, manifest: dict) -> dict:
    cfg = {k: manifest[k] for k in CFG_KEYS if k in manifest}
    if (root / "CLAUDE.md").exists() and "claude" in cfg.get("tools", []):
        cfg["_claude_md"] = read(root / "CLAUDE.md")  # never rewritten by sync; update owns it
    return cfg


def cmd_sync(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    manifest = load_manifest(root)
    if not manifest:
        eprint("no .eos/manifest.json here; run `eos init` first")
        return 2
    phases, stacks = load_project_packs(root)
    cfg = _project_cfg(root, manifest)
    core_md = read(root / ".eos/packs/core.md")
    if args.check:
        return 1 if drift(root, cfg, phases, stacks, core_md) else 0
    w = Writer(root, manifest, args.dry_run, args.force)
    project_plan(cfg, w, phases, stacks, core_md)
    if not args.dry_run:
        save_manifest(root, manifest)
    changed = [(s, r) for s, r in w.report if s != "unchanged"]
    for s, r in changed:
        print(f"  {s:<14} {r}")
    print(f"eos sync: {len(changed)} file(s) changed")
    return 0


# GitHub Actions used by generated workflows, pinned to full commit SHAs (resolved with `git ls-remote` on
# 2026-10-10). Tags are mutable (CISA tj-actions alert, March 2025); the `# vX.Y.Z` comment lets Renovate
# (`helpers:pinGitHubActionDigests`, seeded in .github/renovate.json) update SHA and comment together.
ACTION_PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-node": ("949feb2413d6458794dcd2491c4babbbce0c15c1", "v7.1.0"),
    "astral-sh/setup-uv": ("1c37ad07a6a961277cf70c0d37d6f313000f5884", "v10.3.0"),
    "pnpm/action-setup": ("0977fd99725f1db4007ccb2928dbb4e90d06cc86", "v6.0.10"),
    "oven-sh/setup-bun": ("0c5077e51419868618aeaa5fe8019c62421857d6", "v2.2.0"),
    "googleapis/release-please-action": ("45996ed1f6d02564a971a2fa1b5860e934307cf7", "v5.0.0"),
    "actions/dependency-review-action": ("a1d282b36b6f3519aa1f3fc636f609c47dddb294", "v5.0.0"),
    "anchore/sbom-action": ("e22c389904149dbc22b58101806040fa8d37a610", "v0.24.0"),
    "github/codeql-action": ("24c54180a607b1449ed407dd24f251e4e9147c8d", "v4.38.3"),
    "oasdiff/oasdiff-action": ("b9325c9e0a27ab65b0da3b766522cedec6be81dc", "v0.1.18"),
    "subosito/flutter-action": ("1a449444c387b1966244ae4d4f8c696479add0b2", "v2.23.0"),
    "jdx/mise-action": ("2d8d4cafcbd33be2ea37d2b6f5ad595363d1f1ca", "v5.1.1"),
    "grafana/setup-k6-action": ("43b9fc21641a76002687994433dd586f56e791b1", "v1.2.2"),
    "actions/upload-artifact": ("cf430e030ddbb5b0abf93d22962f4752f3646cd9", "v7.0.2"),
    "actions/setup-java": ("de7274f081f381c8f8158605e0321c36c376e2e6", "v6.0.1"),
    "reactivecircus/android-emulator-runner": ("a421e43855164a8197daf9d8d40fe71c6996bb0d", "v2.38.0"),
}
USES_RX = _lazy_rx(r"""^\s*(?:-\s*)?uses:\s*['"]?([^\s'"#]+)['"]?\s*(#.*)?$""", re.MULTILINE)


def unpinned_uses(text: str) -> list[str]:
    """`uses:` references in a workflow that are not pinned to a full 40-hex commit SHA.
    Local actions (`./…`) and `docker://` images are skipped (pin images by digest separately)."""
    out = []
    for m in USES_RX.finditer(text):
        ref = m.group(1)
        if ref.startswith(("./", "docker://")) or "{" in ref:
            continue
        if not re.search(r"@[0-9a-f]{40}$", ref):
            out.append(ref)
    return out


def workflow_pin_problems(root: Path, manifest: dict) -> tuple[list[str], list[str]]:
    """Errors for eos-generated workflows with unpinned actions, warnings for your own workflows."""
    errs, warns = [], []
    owned = set(manifest.get("files", {}))
    wf = root / ".github/workflows"
    for f in sorted([*wf.glob("*.yml"), *wf.glob("*.yaml")]) if wf.is_dir() else []:
        rel = f.relative_to(root).as_posix()
        bad = unpinned_uses(read(f))
        if bad:
            msg = f"{rel}: actions not pinned to a commit SHA: {', '.join(sorted(set(bad)))} (pin `owner/repo@<sha> # vX.Y.Z`)"
            (errs if rel in owned else warns).append(msg)
    return errs, warns


def drift(root: Path, cfg: dict, phases: dict, stacks: dict, core_md: str) -> list[str]:
    problems = []
    sel_p = [phases[p] for p in cfg["phases"] if p in phases]
    sel_s = [stacks[s] for s in cfg["stacks"] if s in stacks]
    for rel, (content, _m) in render_adapters(sel_p + sel_s, cfg["tools"], cfg["stacks"]).items():
        p = root / rel
        if any(par.is_file() for par in p.parents if root in par.parents):
            continue  # e.g. a user's .clinerules file: eos skipped these on purpose (see the improvement plan)
        if not p.exists():
            problems.append(f"missing adapter: {rel}")
        elif read(p) != content:
            problems.append(f"adapter differs from its pack: {rel}")
    text = read(root / "AGENTS.md") if (root / "AGENTS.md").exists() else ""
    blocks = render_agents_blocks(
        core_md,
        sel_p,
        sel_s,
        cfg["stacks"],
        cfg.get("pm", "pnpm"),
        cfg["tools"],
        gates=cfg.get("gates"),
        project_map=cfg.get("project_map"),
    )
    blocks.update(extra_blocks(cfg))
    for name, body in blocks.items():
        if not body.strip() and f"<!-- eos:{name}:begin -->" not in text:
            continue
        if block_region(name, body) not in text:
            problems.append(f"AGENTS.md block '{name}' out of sync")
    for p in problems:
        print("  drift: " + p)
    if problems:
        print("  fix: python .eos/bin/eos.py sync   (edit packs in .eos/packs, never the generated copies)")
    return problems


# ----------------------------------------------------------------------------- new / scaffold / uninstall
def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "untitled"


def _next_number(folder: Path) -> int:
    nums = [int(m.group(1)) for p in folder.glob("[0-9]*.md") if (m := re.match(r"(\d{4})-", p.name))]
    return max(nums, default=0) + 1


def cmd_new(args: argparse.Namespace) -> int:
    """eos new adr|story|plan "<title>": numbered file from the template (+ ADR INDEX line); eos new design."""
    home = find_eos_home()
    root = Path(args.dir).resolve()
    today = dt.datetime.now().astimezone().date().isoformat()
    if args.kind == "design":
        dest = root / "docs/design/direction.md"
        if dest.exists():
            eprint(f"{dest.relative_to(root).as_posix()} exists: edit it (change direction on purpose, in its own PR)")
            return 1
        if not home:
            eprint("needs the engineering-os repo (set EOS_HOME)")
            return 2
        body = read(home / "core/templates/design/direction.md").replace("<product>", args.title or root.name, 1)
        if args.dry_run:
            print(f"would create {dest.relative_to(root).as_posix()}")
            return 0
        write(dest, body)
        print(
            f"created {dest.relative_to(root).as_posix()}: fill it, critique it against the rejected defaults, get approval"
        )
        return 0
    if not args.title:
        eprint(f'eos new {args.kind} needs a title, e.g. eos new {args.kind} "Offline sync"')
        return 2
    if args.kind == "critique":  # a dated rubric sheet for one screen (design critique loop)
        if not home:
            eprint("needs the engineering-os repo (set EOS_HOME)")
            return 2
        dest = root / f"docs/design/critiques/{today}-{_slug(args.title)}.md"
        if dest.exists():
            eprint(f"{dest.relative_to(root).as_posix()} exists: add the next round to it")
            return 1
        body = read(home / "core/templates/design/critique.md").replace("<screen>", args.title, 1)
        body = body.replace("YYYY-MM-DD", today, 1)
        if args.dry_run:
            print(f"would create {dest.relative_to(root).as_posix()}")
            return 0
        write(dest, body)
        print(
            f"created {dest.relative_to(root).as_posix()}: screenshot, score each row against the rubric, fix, repeat"
        )
        return 0
    if args.kind in ("migration", "service", "module"):
        if not home:
            eprint("needs the engineering-os repo (set EOS_HOME)")
            return 2
        return {"migration": new_migration, "service": new_service, "module": new_module}[args.kind](
            args, home, root, today
        )
    if args.kind == "plan":
        folder = root / "docs/plans/active"
        tpl = home / "core/templates/plans/plan.md" if home else root / "docs/plans/_template.md"
        done = root / "docs/plans/completed"
        n = max(_next_number(folder), _next_number(done) if done.is_dir() else 1)
        dest = folder / f"{n:04d}-{_slug(args.title)}.md"
        if not tpl.exists():
            eprint(f"template not found ({tpl})")
            return 2
        body = read(tpl).replace("NNNN", f"{n:04d}", 1).replace("<plan title>", args.title, 1)
        body = body.replace("active | done | abandoned", "active", 1).replace("YYYY-MM-DD", today, 2)
        if args.dry_run:
            print(f"would create {dest.relative_to(root).as_posix()}")
            return 0
        write(dest, body)
        print(f"created {dest.relative_to(root).as_posix()}  (when finished: git mv it to docs/plans/completed/)")
        return 0
    if args.kind == "adr":
        folder, tpl = root / "docs/adr", root / "docs/adr/0000-template.md"
        if not tpl.exists() and home:
            tpl = home / "core/templates/adr/0000-template.md"
    else:
        folder = root / "docs/stories"
        tpl = (home / "core/templates/story.md") if home else root / "docs/stories/_template.md"
    if not tpl.exists():
        eprint(f"template not found ({tpl}); run `eos init` first")
        return 2
    n = _next_number(folder)
    dest = folder / f"{n:04d}-{_slug(args.title)}.md"
    body = read(tpl).replace("NNNN", f"{n:04d}", 1)
    body = re.sub(r"<(decision|story) title>", args.title, body, count=1)
    body = body.replace("YYYY-MM-DD", today, 1).replace("proposed | accepted | superseded by NNNN", "proposed", 1)
    body = body.replace("draft | ready | in progress | review | done", "draft", 1)
    if args.dry_run:
        print(f"would create {dest.relative_to(root).as_posix()}")
        return 0
    write(dest, body)
    print(f"created {dest.relative_to(root).as_posix()}")
    if args.kind == "adr":
        idx = folder / "INDEX.md"
        line = f"| {n:04d} | [{args.title}]({dest.name}) | proposed | {today} |"
        cur = read(idx) if idx.exists() else read(home / "core/templates/adr/INDEX.md") if home else ""
        write(idx, cur.rstrip("\n") + "\n" + line + "\n")
        print(f"  + INDEX line in {idx.relative_to(root).as_posix()} (set status to accepted when decided)")
    return 0


def _seed_files(root: Path, files: list[tuple[str, str]], dry: bool) -> list[tuple[str, str]]:
    """Create files that don't exist yet; never overwrite. Returns [(status, relpath)]."""
    out = []
    for rel, body in files:
        p = root / rel
        if p.exists():
            out.append(("kept", rel))
            continue
        if not dry:
            write(p, body)
        out.append(("created", rel))
    return out


def _append_row(root: Path, rel: str, template: str, row: str, key: str, dry: bool) -> str:
    p = root / rel
    cur = read(p) if p.exists() else template
    if re.search(rf"(?m)^\| {re.escape(key)} \|", cur):
        return "kept"
    if not dry:
        write(p, cur.rstrip("\n") + "\n" + row + "\n")
    return "updated" if p.exists() else "created"


def _print_report(title: str, rep: list[tuple[str, str]], nxt: str) -> None:
    print(title)
    for s, r in rep:
        print(f"  {s:<8} {r}")
    print(f"  next: {nxt}")


def new_migration(args: argparse.Namespace, home: Path, root: Path, today: str) -> int:
    slug = _slug(args.title)
    base = f"docs/migration/{slug}"
    files = []
    for name in ("plan.md", "parity.md", "data-migration.md", "cutover-runbook.md", "rollback-runbook.md"):
        body = read(home / "core/templates/migration" / name).replace("<name>", args.title)
        files.append((f"{base}/{name}", body.replace("YYYY-MM-DD", today, 2)))
    rep = _seed_files(root, files, args.dry_run)
    tests = root / "tests/characterization/README.md"
    if not tests.exists():
        rep += _seed_files(
            root,
            [
                (
                    "tests/characterization/README.md",
                    (
                        "# Characterization tests\n\nPin what the code does *today* before changing it (migration pack).\n"
                        "Record real inputs/outputs (scrub time and ids); mark known bugs as current behaviour + ticket.\n"
                        "Agents may add tests here but never loosen them (`eos test-integrity`).\n"
                    ),
                )
            ],
            args.dry_run,
        )
    m = load_manifest(root)
    if m and m.get("mode") != "rewrite" and not args.dry_run:
        print(f"  note: project mode is {m.get('mode') or 'unset'}; for a rewrite run `eos mode set rewrite`")
    _print_report(
        f"eos new migration: {base}/{' (DRY RUN)' if args.dry_run else ''}",
        rep,
        "fill plan.md (slices + seam), write characterization tests, then an ADR for the approach",
    )
    return 0


def _resync(root: Path) -> None:
    """Refresh AGENTS.md blocks/adapters after a manifest change (quiet `eos sync`)."""
    if not load_manifest(root):
        return
    ns = argparse.Namespace(dir=str(root), check=False, dry_run=False, force=False)
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        old = sys.stdout
        sys.stdout = devnull
        try:
            cmd_sync(ns)
        finally:
            sys.stdout = old


def new_service(args: argparse.Namespace, home: Path, root: Path, today: str) -> int:
    name = _slug(args.title)
    m = load_manifest(root)
    det = m.get("topology_details") or {}
    svcs = det.get("services") or []
    parent = svcs[0].rsplit("/", 1)[0] if svcs and "/" in svcs[0] else "services"
    base = f"{parent}/{name}"
    owner = args.owner or "<owner>"
    v = {
        "{{NAME}}": name,
        "{{OWNER}}": owner,
        "{{OWNER_PLAIN}}": owner.lstrip("@") if args.owner else "unknown",
        "{{SYSTEM}}": _slug(m.get("project_name", root.name)),
        "{{CONTRACT}}": f"{base}/openapi.yaml",
    }
    files = []
    for f in ("README.md", "catalog-info.yaml", "openapi.yaml", "AGENTS.md"):
        body = read(home / "core/templates/service" / f)
        for k, val in v.items():
            body = body.replace(k, val)
        files.append((f"{base}/{f}", body))
    rep = _seed_files(root, files, args.dry_run)
    row = f"| {name} | {owner} | <purpose> | `{base}/openapi.yaml` | <services> | <store> | <SLO> |"
    st = _append_row(
        root,
        "docs/architecture/services.md",
        read(home / "core/templates/architecture/services.md"),
        row,
        name,
        args.dry_run,
    )
    rep.append((st, "docs/architecture/services.md"))
    if m and not args.dry_run and base not in det.get("services", []):
        det.setdefault("services", []).append(base)
        m["topology_details"] = det
        save_manifest(root, m)
        _resync(root)
    _print_report(
        f"eos new service {name}: {base}/{' (DRY RUN)' if args.dry_run else ''}",
        rep,
        "copy a code skeleton from your best service, fill README + contract, add it to compose.yaml, "
        "then `eos update` (CI + hooks for the new dir) and an ADR if it splits an existing module",
    )
    return 0


def _module_root(root: Path, m: dict) -> str:
    det = m.get("topology_details") or {}
    if det.get("module_root"):
        return det["module_root"]
    py = next((primary_dir(d) for s, d in m.get("stacks", {}).items() if s == "python"), None)
    if py is not None:
        base = Path(py)
        for cand in ("app", "src"):
            if (root / base / cand).is_dir():
                return (base / cand / "modules").as_posix()
        return (base / "app/modules").as_posix()
    return "src/modules"


def new_module(args: argparse.Namespace, home: Path, root: Path, today: str) -> int:
    name = _slug(args.title).replace("-", "_")
    m = load_manifest(root)
    mr = _module_root(root, m)
    base = f"{mr}/{name}"
    owner = args.owner or "<owner>"
    readme = (
        f"# Module: {name}\n\n- **Owns:** <capability and tables>\n- **Owner:** {owner}\n"
        "- **Public API:** the only entry point other modules may import "
        "(`api` / package `__init__` / `index`).\n- **Depends on:** <modules, through their public API>\n"
        "- **Events published / consumed:** <names>\n"
    )
    files = [(f"{base}/README.md", readme)]
    py_dirs = [d for s, v in m.get("stacks", {}).items() if s == "python" for d in as_dirs(v)]
    ts_dirs = [d for s, v in m.get("stacks", {}).items() if s == "typescript" for d in as_dirs(v)]
    if any(_within(base, d) for d in py_dirs) or not ts_dirs:
        if not (root / mr / "__init__.py").exists():
            files.append((f"{mr}/__init__.py", ""))
        files.append((f"{base}/__init__.py", f'"""Module {name}: import other modules only via their .api."""\n'))
        files.append((f"{base}/api.py", f'"""Public API of module {name}. Other modules import only from here."""\n'))
    else:
        files.append((f"{base}/index.ts", f"// Public API of module {name}. Other modules import only from here.\n"))
    rep = _seed_files(root, files, args.dry_run)
    row = f"| {name} | {owner} | <capability, tables> | `{base}` public API | <modules> |"
    st = _append_row(
        root,
        "docs/architecture/modules.md",
        read(home / "core/templates/architecture/modules.md"),
        row,
        name,
        args.dry_run,
    )
    rep.append((st, "docs/architecture/modules.md"))
    det = m.get("topology_details") or {}
    if m and not args.dry_run and name not in det.get("modules", []):
        det.setdefault("modules", []).append(name)
        det["module_root"] = det.get("module_root") or mr
        m["topology_details"] = det
        save_manifest(root, m)
        _resync(root)
    _print_report(
        f"eos new module {name}: {base}/{' (DRY RUN)' if args.dry_run else ''}",
        rep,
        "fill the README, expose only what others need from the public API; `eos scaffold boundaries` enforces it",
    )
    return 0


# kind -> (what it is, [(template under core/scaffold, destination relative to the stack dir or root)], scope)
SCAFFOLDS = {
    "release": (
        "release-please: release PRs, version bumps and CHANGELOG from conventional commits",
        [
            ("release/release-please.yml", ".github/workflows/release-please.yml"),
            ("release/release-please-config.json", "release-please-config.json"),
            ("release/release-please-manifest.json", ".release-please-manifest.json"),
        ],
        "root",
    ),
    "security": (
        "dependency review, SBOM, CodeQL, Semgrep (eos security rules) + threat model and dependency policy docs",
        [
            ("security/security.yml", ".github/workflows/security.yml"),
            ("security/semgrep.yml", ".semgrep/eos-security.yml"),
            ("security/threat-model.md", "docs/security/threat-model.md"),
            ("security/dependency-policy.md", "docs/security/dependency-policy.md"),
        ],
        "root",
    ),
    "security-tests": (
        "webhook signature/replay verifier + tests, authorization-matrix test template (review with a human)",
        [
            ("security-tests/webhook_verify.py", "{{PY_PKG}}/webhook_verify.py"),
            ("security-tests/test_webhook_verify.py.tmpl", "tests/security/test_webhook_verify.py"),
            ("security-tests/test_authz_matrix.py", "tests/security/test_authz_matrix.py"),
        ],
        "python",
    ),
    "api-contract": (
        "OpenAPI gate: Spectral lint + oasdiff breaking changes, Schemathesis fuzzing; --spec path/to/openapi.json",
        [
            ("api-contract/api-contract.yml", ".github/workflows/api-contract.yml"),
            ("api-contract/spectral.yaml", ".spectral.yaml"),
            ("api-contract/api-fuzz.yml", ".github/workflows/api-fuzz.yml"),
        ],
        "root",
    ),
    "codeowners": (
        "CODEOWNERS for review routing; needs --owner @you",
        [("codeowners/CODEOWNERS", ".github/CODEOWNERS")],
        "root",
    ),
    "compose": (
        "local Postgres + Redis with health checks, and .env.example",
        [("compose/compose.yaml", "compose.yaml"), ("compose/env.example", ".env.example")],
        "root",
    ),
    "docker-python": (
        (
            "Dockerfile (uv, multi-stage, non-root), .dockerignore, FastAPI /healthz + /readyz with tests,"
            " hadolint + build workflow"
        ),
        [
            ("docker-python/Dockerfile", "Dockerfile"),
            ("docker-python/dockerignore", ".dockerignore"),
            ("docker-python/health.py", "{{PY_PKG}}/health.py"),
            ("docker-python/test_health.py.tmpl", "tests/test_health.py"),
            ("docker-lint/hadolint.yaml", "@.hadolint.yaml"),
            ("docker-lint/container.yml", "@.github/workflows/container.yml"),
        ],
        "python",
    ),
    "docker-node": (
        "Next.js standalone Dockerfile (multi-stage, non-root), .dockerignore, hadolint + build workflow",
        [
            ("docker-node/Dockerfile", "Dockerfile"),
            ("docker-node/dockerignore", ".dockerignore"),
            ("docker-lint/hadolint.yaml", "@.hadolint.yaml"),
            ("docker-lint/container.yml", "@.github/workflows/container.yml"),
        ],
        "node",
    ),
    "tests-python": (
        "pytest fixtures (testcontainers Postgres), factories, test strategy doc",
        [
            ("tests-python/conftest.py", "tests/conftest.py"),
            ("tests-python/factories.py", "tests/factories.py"),
            ("tests-python/strategy.md", "@docs/testing/strategy.md"),
        ],
        "python",
    ),
    "reproducible": (
        "mise.toml (pinned runtimes, lockfile) + .devcontainer + dev-environment doc",
        [
            ("reproducible/mise.toml.tmpl", "mise.toml"),
            ("reproducible/devcontainer.json.tmpl", ".devcontainer/devcontainer.json"),
            ("reproducible/dev-environment.md", "docs/dev-environment.md"),
        ],
        "root",
    ),
    "boundaries": (
        "module boundary check from the detected modules: .importlinter (Python) / .dependency-cruiser.cjs (TS)",
        [],
        "root",
    ),
    "db-safety": (
        "PostgreSQL gates: tuned .squawk.toml, Alembic SQL lint, schema lint (unindexed FKs, money as float), money rules",
        [
            ("db-safety/squawk.toml", ".squawk.toml"),
            ("db-safety/alembic_squawk.py", "scripts/db/alembic_squawk.py"),
            ("db-safety/schema_lint.sql", "scripts/db/schema_lint.sql"),
            ("db-safety/semgrep-data.yml", ".semgrep/eos-data.yml"),
            ("db-safety/db-safety.yml", ".github/workflows/db-safety.yml"),
        ],
        "root",
    ),
    "e2e-node": (
        "Playwright smoke test with axe accessibility check",
        [("e2e-node/playwright.config.ts", "playwright.config.ts"), ("e2e-node/smoke.spec.ts", "e2e/smoke.spec.ts")],
        "node",
    ),
    "lighthouse": (
        "Lighthouse CI budgets (LCP, CLS, TBT, script/total bytes) on key pages; reports kept private",
        [
            ("lighthouse/lighthouserc.json", "lighthouserc.json"),
            ("lighthouse/lighthouse.yml", "@.github/workflows/lighthouse.yml"),
        ],
        "node",
    ),
    "eslint-next": (
        "ESLint flat config: Next core-web-vitals + TypeScript + jsx-a11y, image/font/script rules as errors",
        [("eslint-next/eslint.config.mjs", "eslint.config.mjs")],
        "node",
    ),
    "web-security": (
        "nonce CSP + security headers via proxy.ts, a Playwright header test, Semgrep frontend rules (review with a human)",
        [
            ("web-security/csp.ts", "{{NODE_SRC}}lib/csp.ts"),
            ("web-security/proxy.ts", "{{NODE_SRC}}proxy.ts"),
            ("web-security/security-headers.spec.ts", "e2e/security-headers.spec.ts"),
            ("web-security/semgrep-frontend.yml", "@.semgrep/eos-frontend.yml"),
        ],
        "node",
    ),
    "i18n": (
        "French/English message catalogs (ICU plurals), XAF/date formatters for Africa/Douala + pinned tests",
        [
            ("i18n/fr.json", "messages/fr.json"),
            ("i18n/en.json", "messages/en.json"),
            ("i18n/format.ts", "{{NODE_SRC}}lib/format.ts"),
            ("i18n/format.test.ts", "{{NODE_SRC}}lib/format.test.ts"),
        ],
        "node",
    ),
    "design-tokens": (
        "DTCG 2025.10 token set (light + dark, contrast-checked), Style Dictionary 5 build (CSS @theme, JS, Dart), critique screenshots",
        [
            ("design-tokens/base.tokens.json", "design/tokens/base.tokens.json"),
            ("design-tokens/dark.tokens.json", "design/tokens/dark.tokens.json"),
            ("design-tokens/build-tokens.mjs", "design/build-tokens.mjs"),
            ("design-tokens/design-critique.spec.ts", "e2e/design-critique.spec.ts"),
        ],
        "node",
    ),
    "quarantine": (
        "flaky-test quarantine: tests/quarantine.json (owner, ticket, expiry; `eos check` fails when expired) + policy",
        [
            ("quarantine/quarantine.json", "tests/quarantine.json"),
            ("quarantine/flaky-tests.md", "docs/testing/flaky-tests.md"),
        ],
        "root",
    ),
    "property-python": (
        "Hypothesis property-test patterns: invariants, round trip, oracle",
        [("property-python/test_properties.py", "tests/test_properties.py")],
        "python",
    ),
    "property-node": (
        "fast-check + Vitest property-test patterns: invariants, round trip, oracle",
        [("property-node/properties.test.ts", "tests/properties.test.ts")],
        "node",
    ),
    "load-k6": (
        "k6 smoke + average-load scripts with thresholds, and a manual/weekly load workflow (never per PR)",
        [
            ("load-k6/smoke.js", "load/smoke.js"),
            ("load-k6/load.js", "load/load.js"),
            ("load-k6/load.yml", ".github/workflows/load.yml"),
        ],
        "root",
    ),
    "mutation": (
        "incremental mutation testing in CI for money/auth code: mutmut (Python), Stryker (Node), score gate",
        [
            ("mutation/mutation.yml", ".github/workflows/mutation.yml"),
            ("mutation/stryker.config.json", "{{NODE_DIR}}/stryker.config.json"),
        ],
        "root",
    ),
    "ops": (
        (
            "SLOs (ops/slo.json) + generated burn-rate alerts with promtool tests, runbook, incident and postmortem"
            " templates, secrets/PII-in-logs Semgrep rules, ops workflow"
        ),
        [
            ("ops/slo.json", "ops/slo.json"),
            ("ops/slo-burn-rate.test.yml", "ops/alerts/tests/slo-burn-rate.test.yml"),
            ("ops/api-slo.md", "docs/runbooks/api-slo.md"),
            ("ops/incident-response.md", "docs/ops/incident-response.md"),
            ("ops/postmortem.md", "docs/postmortems/_template.md"),
            ("ops/semgrep-ops.yml", ".semgrep/eos-ops.yml"),
            ("ops/ops.yml", ".github/workflows/ops.yml"),
        ],
        "root",
    ),
    "otel-python": (
        "OpenTelemetry for FastAPI/Flask: traces + metrics over OTLP, JSON logs with trace_id, redaction, test",
        [
            ("otel-python/telemetry.py", "{{PY_PKG}}/telemetry.py"),
            ("otel-python/test_telemetry.py.tmpl", "tests/test_telemetry.py"),
        ],
        "python",
    ),
    "otel-node": (
        "OpenTelemetry for Next.js: instrumentation.ts (Node SDK, OTLP) + JSON logger with trace_id",
        [
            ("otel-node/instrumentation.ts", "{{NODE_SRC}}instrumentation.ts"),
            ("otel-node/instrumentation.node.ts", "{{NODE_SRC}}instrumentation.node.ts"),
            ("otel-node/logger.ts", "{{NODE_SRC}}lib/logger.ts"),
        ],
        "node",
    ),
    "flags": (
        (
            "feature flags via OpenFeature: ops/flags.json registry (owner, expiry; `eos check` enforces) +"
            " Python/Node providers with env overrides, stable % rollout, trace events"
        ),
        [
            ("flags/flags.json", "ops/flags.json"),
            ("flags/flags.py", "{{PY_DIR}}/{{PY_PKG}}/flags.py"),
            ("flags/test_flags.py.tmpl", "{{PY_DIR}}/tests/test_flags.py"),
            ("flags/flags.ts", "{{NODE_DIR}}/{{NODE_SRC}}lib/flags.ts"),
        ],
        "root",
    ),
    "mobile": (
        (
            "mobile: MASVS Semgrep rules (RN/Expo, Flutter, Kotlin, Swift), Maestro smoke + offline flows, Android"
            " emulator E2E workflow (pinned Maestro, checksum), low-end performance budget doc"
        ),
        [
            ("mobile/semgrep-mobile.yml", "@.semgrep/eos-mobile.yml"),
            ("mobile/smoke.yaml", ".maestro/smoke.yaml"),
            ("mobile/offline-sync.yaml", ".maestro/offline-sync.yaml"),
            ("mobile/mobile-e2e.yml", "@.github/workflows/mobile-e2e.yml"),
            ("mobile/performance-budget.md", "@docs/mobile/performance-budget.md"),
        ],
        "root",
    ),
    "llm-evals": (
        (
            "LLM features: versioned prompt file example, eval cases + code-graded runner, gate thresholds"
            " (`eos llm gate`), CI workflow (prompt check, capped eval run, gate), Semgrep LLM rules"
        ),
        [
            ("llm/support-answer.prompt.md.tmpl", "@prompts/support-answer.prompt.md"),
            ("llm/cases.jsonl", "@evals/llm/cases.jsonl"),
            ("llm/run_evals.py", "@evals/llm/run_evals.py"),
            ("llm/gate.json", "@evals/llm/gate.json"),
            ("llm/README.md", "@evals/llm/README.md"),
            ("llm/llm-evals.yml", "@.github/workflows/llm-evals.yml"),
            ("llm/semgrep-llm.yml", "@.semgrep/eos-llm.yml"),
        ],
        "root",
    ),
    "analytics": (
        (
            "Analytics on dbt + DuckDB: seeds, staging and mart models with data tests, a unit test, an enforced"
            " contract and a reconciliation test; an ODCS data contract (`eos data check`); CI workflow (dbt build"
            " offline, contract check vs the PR base); Semgrep rules for personal data in analytics events"
        ),
        [
            ("analytics/dbt_project.yml", "@analytics/dbt_project.yml"),
            ("analytics/profiles.yml", "@analytics/profiles.yml"),
            ("analytics/gitignore", "@analytics/.gitignore"),
            ("analytics/README.md", "@analytics/README.md"),
            ("analytics/seeds/raw_payments.csv", "@analytics/seeds/raw_payments.csv"),
            ("analytics/seeds/raw_merchants.csv", "@analytics/seeds/raw_merchants.csv"),
            ("analytics/models/staging/stg_payments.sql", "@analytics/models/staging/stg_payments.sql"),
            ("analytics/models/staging/stg_merchants.sql", "@analytics/models/staging/stg_merchants.sql"),
            ("analytics/models/staging/_staging.yml", "@analytics/models/staging/_staging.yml"),
            ("analytics/models/marts/fct_daily_payments.sql", "@analytics/models/marts/fct_daily_payments.sql"),
            ("analytics/models/marts/dim_merchants.sql", "@analytics/models/marts/dim_merchants.sql"),
            ("analytics/models/marts/_marts.yml", "@analytics/models/marts/_marts.yml"),
            ("analytics/tests/assert_daily_totals_reconcile.sql", "@analytics/tests/assert_daily_totals_reconcile.sql"),
            ("analytics/payments-daily.odcs.yaml", "@contracts/payments-daily.odcs.yaml"),
            ("analytics/analytics.yml", "@.github/workflows/analytics.yml"),
            ("analytics/semgrep-analytics.yml", "@.semgrep/eos-analytics.yml"),
        ],
        "root",
    ),
    "ml": (
        (
            "Classic ML hygiene docs: split and leakage checklist (with `eos data split` and the nbstripout hook),"
            " model card and datasheet templates"
        ),
        [
            ("ml/split-leakage-checklist.md", "@docs/ml/split-leakage-checklist.md"),
            ("ml/model-card.md", "@docs/ml/model-card.md"),
            ("ml/datasheet.md", "@docs/ml/datasheet.md"),
        ],
        "root",
    ),
    "llm-otel": (
        (
            "GenAI tracing with OpenTelemetry semantic conventions: Python + TS helpers for model, tool and agent"
            " spans, token usage, opt-in content capture, cost from a dated price table you fill; pytest contract"
        ),
        [
            ("llm-otel/genai_otel.py", "{{PY_DIR}}/{{PY_PKG}}/genai_otel.py"),
            ("llm-otel/test_genai_otel.py.tmpl", "{{PY_DIR}}/tests/test_genai_otel.py"),
            ("llm-otel/genai-otel.ts", "{{NODE_DIR}}/{{NODE_SRC}}lib/genai-otel.ts"),
        ],
        "root",
    ),
    "iac": (
        (
            "IaC gates (plan-only, never apply): OpenTofu fmt/validate + checkov scan workflow, .checkov.yaml,"
            " state-safe .gitignore"
        ),
        [
            ("iac/iac.yml", ".github/workflows/iac.yml"),
            ("iac/checkov.yaml", ".checkov.yaml"),
            ("iac/gitignore", "{{IAC_DIR}}/.gitignore"),
        ],
        "root",
    ),
}


def _stack_dir(manifest: dict, home: Path | None, ci: str) -> str | None:
    if not home:
        return None
    _, stacks = load_home_packs(home)
    return next(
        (
            primary_dir(d)
            for sid, d in manifest.get("stacks", {}).items()
            if sid in stacks and stacks[sid].meta.get("ci") == ci
        ),
        None,
    )


def scaffold_vars(root: Path, manifest: dict, home: Path | None, args: argparse.Namespace) -> dict[str, str]:
    pm = manifest.get("pm", "pnpm")
    info = PM_INFO.get(pm, PM_INFO["pnpm"])
    py_dir, node_dir = _stack_dir(manifest, home, "python"), _stack_dir(manifest, home, "node")
    pyv = (
        read(root / (py_dir or ".") / ".python-version").strip()
        if (root / (py_dir or ".") / ".python-version").exists()
        else ""
    )
    stacks = manifest.get("stacks", {})
    fastapi = "python-fastapi" in stacks
    pkg = (
        "src" if (root / (py_dir or ".") / "src").is_dir() and not (root / (py_dir or ".") / "app").is_dir() else "app"
    )
    langs = []
    if py_dir:
        langs.append("python")
    if node_dir:
        langs.append("javascript-typescript")
    ver = read_versions(home) if home else {}
    release_type = "node" if node_dir and not py_dir else "python" if py_dir and not node_dir else "simple"
    mise, feats, post = [], [], []
    if py_dir:
        pv = ".".join(pyv.split(".")[:2]) if pyv else ver.get("python", "3.14")
        mise += [f'python = "{pv}"', f'uv = "{ver.get("uv", "latest")}"']
        feats.append(f'    "ghcr.io/devcontainers/features/python:1": {{ "version": "{pv}" }}')
        post.append(
            f"python3 -m pip install --user uv=={ver.get('uv', '0.12.24')} && cd {py_dir} && ~/.local/bin/uv sync"
        )
    if node_dir:
        mise.append(f'node = "{ver.get("node", "24")}"')
        if pm in ("pnpm", "bun") and ver.get(pm):
            mise.append(f'{pm} = "{ver[pm]}"')
        feats.append(f'    "ghcr.io/devcontainers/features/node:1": {{ "version": "{ver.get("node", "24")}" }}')
        post.append(f"corepack enable && cd {node_dir} && {info['install']}")
    if "flutter" in stacks:
        mise.append(
            f"# flutter: pin with FVM (.fvmrc) or here if your mise registry supports it ({ver.get('flutter', '')})"
        )
    ind = " " * 10
    if py_dir:
        serve = (
            "uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"
            if fastapi
            else 'uv run flask --app "app:create_app()" run --host 127.0.0.1 --port 8000'
        )
        start = [
            *([f"cd {py_dir}"] if py_dir != "." else []),
            "uv sync --frozen",
            f'nohup {serve} > "$RUNNER_TEMP/api.log" 2>&1 &',
        ]
        fuzz_setup = ""
    elif node_dir:
        start = [
            *([f"cd {node_dir}"] if node_dir != "." else []),
            info["install"],
            f"{pm} run build",
            f'PORT=8000 nohup {pm} run start > "$RUNNER_TEMP/api.log" 2>&1 &',
        ]
        fuzz_setup = info["setup"].format(d=node_dir)
    else:
        start = ['echo "set the command that starts your API on port 8000 here"', "exit 1"]
        fuzz_setup = ""
    return {
        "{{PROJECT_NAME}}": manifest.get("project_name", root.name),
        "{{MISE_TOOLS}}": "\n".join(mise) or '# add tools, e.g. node = "24"',
        "{{DC_FEATURES}}": ",\n".join(feats),
        "{{POST_CREATE}}": " && ".join(f"({c})" for c in post) or "echo ready",
        "{{OWNER}}": getattr(args, "owner", None) or "",
        "{{SPEC}}": getattr(args, "spec", None) or "openapi.json",
        "{{RELEASE_TYPE}}": release_type,
        "{{CODEQL_LANGS}}": '", "'.join(langs or ["actions"]),  # inside ["..."] in the template
        "{{PG_TAG}}": ver.get("postgres", "18"),
        "{{SQUAWK_VERSION}}": ver.get("squawk-cli", "2.68.0"),
        "{{SPECTRAL_VERSION}}": ver.get("spectral-cli", "6.17.0"),
        "{{SCHEMATHESIS_VERSION}}": ver.get("schemathesis", "4.30.1"),
        "{{K6_VERSION}}": ver.get("k6", "2.3.0"),
        "{{MUTMUT_VERSION}}": ver.get("mutmut", "3.8.0"),
        "{{PM_EXEC}}": info["exec"],
        "{{NODE_SETUP}}": info["setup"].format(d=node_dir) if node_dir else "",
        "{{NODE_MAJOR}}": ver.get("node", "24"),
        "{{API_START}}": "\n".join(ind + c for c in start),
        "{{FUZZ_SETUP}}": fuzz_setup,
        "{{REDIS_TAG}}": ver.get("redis", "8"),
        "{{PY_TAG}}": (".".join(pyv.split(".")[:2]) if pyv else ver.get("python", "3.14")) + "-slim",
        "{{UV_TAG}}": ver.get("uv", "0.12.24"),
        "{{PY_CMD}}": (
            '"uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"'
            if fastapi
            else '"gunicorn", "--bind", "0.0.0.0:8000", "app:create_app()"'
        ),
        "{{PY_PKG}}": pkg,
        "{{NODE_TAG}}": ver.get("node", "24") + "-slim",
        "{{PM}}": pm,
        "{{PM_INSTALL}}": info["install"],
        "{{LOCKFILE}}": info["lock"],
        "{{DIR}}": ".",
        "{{TODAY}}": _today().isoformat(),
        "{{TODAY_PLUS_30}}": (_today() + dt.timedelta(days=30)).isoformat(),
        "{{PROMETHEUS_VERSION}}": ver.get("prometheus", "3.15.0"),
        "{{OPENAI_PY_VERSION}}": ver.get("openai-python", "3.28.0"),
        "{{DBT_CORE_VERSION}}": ver.get("dbt-core", "1.12.5"),
        "{{DBT_DUCKDB_VERSION}}": ver.get("dbt-duckdb", "1.11.0"),
        "{{OTEL_SDK_VERSION}}": ver.get("opentelemetry-sdk", "1.45.1"),
        "{{PROMETHEUS_SHA256}}": ver.get("prometheus-sha256", ""),
        "{{HADOLINT_VERSION}}": ver.get("hadolint", "2.15.1"),
        "{{HADOLINT_SHA256}}": ver.get("hadolint-sha256", ""),
        "{{OPENTOFU_VERSION}}": ver.get("opentofu", "1.13.1"),
        "{{OPENTOFU_SHA256}}": ver.get("opentofu-sha256", ""),
        "{{CHECKOV_VERSION}}": ver.get("checkov", "3.3.26"),
        "{{LHCI_VERSION}}": ver.get("@lhci/cli", "0.15.1"),
        "{{SD_VERSION}}": ver.get("style-dictionary", "5.6.1"),
        "{{IAC_DIR}}": _iac_dir(root),
        "{{PY_DIR}}": py_dir or ".",
        "{{NODE_SRC}}": (
            "src/" if node_dir and any((root / node_dir / "src" / d).is_dir() for d in ("app", "pages")) else ""
        ),
        "{{FLAGS_REL}}": os.path.relpath("ops/flags.json", node_dir or "."),
        **mobile_scaffold_vars(root, manifest, ver, pm),
    }


def _mobile_app(root: Path, manifest: dict) -> tuple[str, str]:
    """(kind, folder) of the mobile app: expo | flutter | android | "" (none found)."""
    stacks = manifest.get("stacks", {})
    for sid, kind in (("react-native-expo", "expo"), ("flutter", "flutter")):
        if sid in stacks:
            dirs = as_dirs(stacks[sid])
            return kind, (dirs[0] if dirs else ".")
    for d in [".", *[x for v in stacks.values() for x in as_dirs(v)]]:
        base = root / d
        if (base / "pubspec.yaml").is_file():
            return "flutter", d
        try:
            if '"expo"' in read(base / "app.json"):
                return "expo", d
        except OSError:
            pass
        if any((base / f).is_file() for f in ("settings.gradle", "settings.gradle.kts")):
            return "android", d
    return "", "."


def _android_app_id(root: Path, kind: str, d: str) -> str:
    base = root / d
    try:
        if kind == "expo":
            pkg = json.loads(read(base / "app.json")).get("expo", {}).get("android", {}).get("package")
            if pkg:
                return str(pkg)
    except (OSError, ValueError, AttributeError):
        pass
    for g in ("android/app/build.gradle.kts", "android/app/build.gradle", "app/build.gradle.kts", "app/build.gradle"):
        try:
            m = re.search(r"""applicationId\s*=?\s*["']([\w.]+)["']""", read(base / g))
        except OSError:
            continue
        if m:
            return m.group(1)
    return "com.example.app"


def mobile_scaffold_vars(root: Path, manifest: dict, ver: dict, pm: str) -> dict[str, str]:
    """Build steps for the Maestro workflow, chosen from the detected app (Expo, Flutter or native Android)."""
    kind, d = _mobile_app(root, manifest)
    ind = " " * 10
    cd = [f"cd {d}"] if d not in (".", "") else []
    pre = "" if d in (".", "") else d.rstrip("/") + "/"
    info = PM_INFO.get(pm, PM_INFO["pnpm"])
    if kind == "expo":
        setup = info["setup"].format(d=d or ".").rstrip("\n")
        build = [*cd, info["install"], "npx expo prebuild --platform android --no-install",
                 "cd android && ./gradlew assembleRelease --no-daemon"]  # fmt: skip
        apk = f"{pre}android/app/build/outputs/apk/release/app-release.apk"
    elif kind == "flutter":
        fa = "subosito/flutter-action"
        setup = (
            f"      - uses: {fa}@{ACTION_PINS[fa][0]} # {ACTION_PINS[fa][1]}\n        with:\n          channel: stable\n"
            f"          flutter-version: {ver['flutter']}\n          cache: true"
        )  # fmt: skip
        build = [*cd, "flutter pub get", "flutter build apk --debug"]
        apk = f"{pre}build/app/outputs/flutter-apk/app-debug.apk"
    elif kind == "android":
        setup = ""
        build = [*cd, "./gradlew assembleDebug --no-daemon"]
        apk = f"{pre}app/build/outputs/apk/debug/app-debug.apk"
    else:
        setup = ""
        build = ['echo "set the command that builds a test APK here (see the comments in this file)"', "exit 1"]
        apk = "path/to/app.apk"
    return {
        "{{APP_ID}}": _android_app_id(root, kind, d) if kind else "com.example.app",
        "{{MOBILE_SETUP}}": setup or "      # (no extra toolchain detected)",
        "{{MOBILE_BUILD}}": "\n".join(ind + c for c in build),
        "{{APK_PATH}}": apk,
        "{{MAESTRO_VERSION}}": ver.get("maestro", "2.11.0"),
        "{{MAESTRO_SHA256}}": ver.get("maestro-sha256", ""),
    }


def _iac_dir(root: Path) -> str:
    """Where the Terraform/OpenTofu code lives: the first conventional folder that has .tf files, else infra."""
    for d in ("infra", "terraform", "iac", "deploy", "ops/terraform"):
        if (root / d).is_dir() and any((root / d).rglob("*.tf")):
            return d
    return "infra"


def cmd_scaffold(args: argparse.Namespace) -> int:
    """Opt-in starter files. Written once (never overwritten); afterwards they are yours."""
    home = find_eos_home()
    if not home:
        eprint("needs the engineering-os repo (set EOS_HOME)")
        return 2
    if args.kind == "list":
        for k, (what, _f, scope) in SCAFFOLDS.items():
            print(f"  {k:<14} {what}" + ("" if scope == "root" else f"  [{scope} stack]"))
        return 0
    root = Path(args.dir).resolve()
    manifest = load_manifest(root)
    if not manifest:
        eprint(f"{root} has no .eos/manifest.json: run `eos init` first")
        return 2
    what, files, scope = SCAFFOLDS[args.kind]
    if args.kind == "boundaries":
        return scaffold_boundaries(root, manifest, args)
    if args.kind == "codeowners" and not args.owner:
        eprint("codeowners needs --owner @your-handle (or @org/team)")
        return 2
    base = "."
    if scope != "root":
        d = _stack_dir(manifest, home, scope)
        if d is None:
            eprint(f"no {scope} stack in this project (stacks: {', '.join(manifest.get('stacks', {})) or 'none'})")
            return 2
        base = d
    v = scaffold_vars(root, manifest, home, args)
    v["{{DIR}}"] = base
    w = Writer(root, manifest, args.dry_run, False)
    node_dir = _stack_dir(manifest, home, "node")
    py_dir = _stack_dir(manifest, home, "python")
    for src, dest in files:
        if "{{NODE_DIR}}" in dest:  # a file for the Node app inside a root scaffold: only when there is one
            if node_dir is None:
                continue
            dest = dest.replace("{{NODE_DIR}}", node_dir)
        if "{{PY_DIR}}" in dest and py_dir is None:  # likewise for the Python app
            continue
        for k in ("{{PY_DIR}}", "{{PY_PKG}}", "{{NODE_SRC}}", "{{IAC_DIR}}"):
            dest = dest.replace(k, v[k])
        rel = dest[1:] if dest.startswith("@") else str(Path(base) / dest)
        body = read(home / "core/scaffold" / src)
        for k, val in v.items():
            body = body.replace(k, val)
        w.seed(os.path.normpath(rel), body)
    done = manifest.setdefault("scaffolded", [])
    if args.kind not in done:
        done.append(args.kind)
    if not args.dry_run:
        save_manifest(root, manifest)
    if args.kind == "ops" and not args.dry_run:  # generate the burn-rate rules the promtool tests exercise
        cfg = ops_cfg(root)
        out = root / (cfg["generated_rules"] or "ops/alerts/slo-burn-rate.rules.yml")
        try:
            data = json.loads(read(root / cfg["slo_file"]))
        except (OSError, ValueError):
            data = None
        if data is not None and not out.exists() and not slo_problems(root, data, cfg)[0]:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(slo_alert_rules(data, cfg), encoding="utf-8", newline="\n")
            w.report.append(("created", cfg["generated_rules"]))
    print(f"eos scaffold {args.kind}: {what}{' (DRY RUN)' if args.dry_run else ''}")
    for status, rel in w.report:
        print(f"  {status:<8} {rel}")
    nxt = {
        "release": "use conventional commits (`eos update` adds the commit-msg check); merge the release PR to tag a release",
        "security": "delete the dependency-review/CodeQL jobs if the repo is private without Code Security;"
        " triage Semgrep hits (fix, or `nosemgrep: <id>` with a reason)",
        "security-tests": "have a human review webhook_verify.py; wire the fixtures in tests/security/test_authz_matrix.py",
        "api-contract": f"commit the spec at {v['{{SPEC}}']} and regenerate it in every API-changing PR;"
        " edit 'Start the API' in api-fuzz.yml (disposable DB only); triage Spectral warnings",
        "codeowners": "enable 'Require review from Code Owners' in branch protection",
        "compose": "cp .env.example .env && docker compose up -d --wait",
        "docker-python": "include the health router in your app; docker build -t app .",
        "docker-node": 'set output: "standalone" in next.config; docker build -t web .',
        "tests-python": 'uv add --dev pytest pytest-cov "testcontainers[postgres]"',
        "reproducible": "mise install && mise lock; commit mise.toml + mise.lock; CI: jdx/mise-action@"
        + ACTION_PINS["jdx/mise-action"][0]
        + " # "
        + ACTION_PINS["jdx/mise-action"][1],
        "db-safety": "set pg_version in .squawk.toml to production's; run psql -f scripts/db/schema_lint.sql"
        " on a migrated DB; set MIGRATE in db-safety.yml if auto-detect misses",
        "e2e-node": f'{v["{{PM}}"]} add -D @playwright/test @axe-core/playwright; add script "test:e2e": "playwright test"',
        "lighthouse": f"edit the URLs in lighthouserc.json (key pages; they must render without login); try locally:"
        f" {v['{{PM}}']} run build && npx @lhci/cli@{v['{{LHCI_VERSION}}']} autorun; review the budgets with the team",
        "eslint-next": f"{v['{{PM}}']} add -D eslint@^9 eslint-config-next eslint-plugin-jsx-a11y (jsx-a11y does not"
        " support eslint 10 yet); merge by hand if you already had an eslint config; axe runs in e2e-node",
        "web-security": "a human reviews csp.ts/proxy.ts; deploy with CSP_REPORT_ONLY=1 first and watch violations;"
        " nonces make pages dynamic; set poweredByHeader: false in next.config; run e2e/security-headers.spec.ts",
        "i18n": 'set "frontend": {"i18n": {"dir": "messages", "default_locale": "fr"}} in .eos/config.json (or keep'
        " auto-detect); wire a library (next-intl: setRequestLocale, timeZone 'Africa/Douala'); `eos i18n check`",
        "design-tokens": "replace the sample values with docs/design/direction.md (`eos new design`), then `eos design"
        f' check`; {v["{{PM}}"]} add -D style-dictionary@{v["{{SD_VERSION}}"]} and add script "tokens": "node design/build-tokens.mjs";'
        " import design/build/tokens.css and tokens.dark.css after tailwindcss in your global CSS",
        "quarantine": "eos quarantine add <test id> --reason ... --owner @you --issue <url>; pytest (tests-python"
        " conftest) and Playwright (e2e-node config) honour it; `eos check` fails on expired entries",
        "property-python": "uv add --dev hypothesis; replace the toy functions with your code; nightly:"
        " pytest --hypothesis-profile=nightly",
        "property-node": f"{v['{{PM}}']} add -D fast-check vitest; replace the toy functions with your code",
        "load-k6": "k6 run -e BASE_URL=http://127.0.0.1:8000 load/smoke.js; set repo variable LOAD_BASE_URL"
        " (staging) for the weekly smoke; tune thresholds to your SLOs",
        "mutation": "Node: add -D @stryker-mutator/core @stryker-mutator/vitest-runner; Python: mutmut runs via"
        " uv (add [tool.mutmut] source_paths if autodetect fails); label a PR lane:risky to mutate all changed files",
        "ops": "set owners and objectives in ops/slo.json (policy: agree them), then `eos ops alerts` after each"
        " edit; `eos ops runbook <name>` for every new alert; `eos ops budget` shows allowed downtime",
        "otel-python": "uv add opentelemetry-sdk opentelemetry-exporter-otlp-proto-http"
        " opentelemetry-instrumentation-fastapi (or -flask); call setup_telemetry(app) at startup;"
        " set OTEL_SERVICE_NAME and OTEL_EXPORTER_OTLP_ENDPOINT",
        "otel-node": f"{v['{{PM}}']} add @opentelemetry/api @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http"
        " @opentelemetry/exporter-metrics-otlp-http @opentelemetry/sdk-metrics; set OTEL_SERVICE_NAME and"
        " OTEL_EXPORTER_OTLP_ENDPOINT",
        "flags": "uv add openfeature-sdk / add @openfeature/server-sdk; read flags with flag_enabled()/flagEnabled();"
        " `eos check` fails on expired or unregistered flags; copy ops/flags.json into images (or set FLAGS_FILE)",
        "mobile": "replace the ids in .maestro/*.yaml with your screens' testIDs/labels; `maestro test .maestro/`"
        " locally; label a PR `e2e` to run the emulator job; triage Semgrep hits (`semgrep scan --config .semgrep/`);"
        " `eos mobile check` and `eos mobile size --update` after a reviewed release build; fill docs/mobile/"
        "performance-budget.md on a low-end phone",
        "llm-evals": "rename/replace prompts/support-answer.prompt.md with your prompt; write 30+ real cases"
        " (FR and EN, safety) in evals/llm/cases.jsonl; `python evals/llm/run_evals.py --fake` to try the pipeline;"
        " add the OPENAI_API_KEY repo secret (or edit call_model for your provider); after a reviewed passing run:"
        " `eos llm gate --update`; triage Semgrep hits; `eos llm check` runs in `eos check` and verify",
        "analytics": "cd analytics && uv run --no-project --with dbt-core --with dbt-duckdb dbt build --profiles-dir ."
        " (all tests should pass on the synthetic seeds); replace seeds with real loads (dlt, Airbyte or COPY);"
        " keep contracts/*.odcs.yaml in step with the marts; `eos data check` runs in `eos check` and verify;"
        " triage Semgrep hits (`semgrep scan --config .semgrep/`)",
        "ml": "fill docs/ml/split-leakage-checklist.md before trusting offline metrics; run `eos data split --train"
        " … --test … --id … --time …` on exported splits; keep a model card per released model; add nbstripout"
        " to pre-commit if notebooks are committed",
        "llm-otel": f"uv add opentelemetry-sdk=={v['{{OTEL_SDK_VERSION}}']} (Python) / add @opentelemetry/api"
        " (Node); wrap each model call in llm_span()/withLlmSpan() and record usage; keep content capture off"
        " unless redacted; fill PRICES with dated prices from the provider pages if you want cost estimates",
        "iac": f"keep modules under {v['{{IAC_DIR}}']}/; commit .terraform.lock.hcl; add a plan job with OIDC when"
        " ready; apply stays a human-approved step",
    }[args.kind]
    print(f"  next: {nxt}")
    return 0


IMPORTLINTER_TPL = """# Module boundaries (import-linter). Generated by `eos scaffold boundaries`; yours to edit.
# Run: lint-imports   (install: uv add --dev import-linter). Docs: https://import-linter.readthedocs.io/
[importlinter]
root_package = {root_pkg}

[importlinter:contract:modules-public-api]
name = Modules use each other only through their public API
type = independence
modules =
    {pkg}.*
ignore_imports =
    {pkg}.** -> {pkg}.*.api
    {pkg}.** -> {pkg}.*
unmatched_ignore_imports_alerting = none
broken_contract_guidance =
    Import another module only through its public API: {pkg}.<module>.api (or the package itself).
    Move shared code into the module that owns it and expose it from that module's api.
"""

DEPCRUISE_TPL = """// Module boundaries (dependency-cruiser). Generated by `eos scaffold boundaries`; yours to edit.
// Run: npx depcruise {src} --config .dependency-cruiser.cjs
// Old violations: npx depcruise {src} --config .dependency-cruiser.cjs --baseline, then add --ignore-known.
/** @type {{import('dependency-cruiser').IConfiguration}} */
module.exports = {{
  forbidden: [
    {{
      name: "module-public-api-only",
      severity: "error",
      comment:
        "Import another module only through its public entry ({mr}/<module>/index.ts). " +
        "Move shared code into the module that owns it and export it from that module's index.",
      from: {{ path: "^{mr_re}/([^/]+)/" }},
      to: {{
        path: "^{mr_re}/[^/]+/",
        pathNot: ["^{mr_re}/$1/", "^{mr_re}/[^/]+/index\\\\.(ts|tsx|js|mjs)$"],
      }},
    }},
    {{
      name: "no-circular",
      severity: "error",
      comment: "Circular dependencies make modules impossible to separate; extract the shared part.",
      from: {{}},
      to: {{ circular: true }},
    }},
  ],
  options: {{
    doNotFollow: {{ path: "node_modules" }},
    tsPreCompilationDeps: true,
  }},
}};
"""


def scaffold_boundaries(root: Path, manifest: dict, args: argparse.Namespace) -> int:
    det = manifest.get("topology_details") or {}
    mr = det.get("module_root") or ""
    if not mr:
        eprint(
            "no module folder detected (modules/, domains/, contexts/ with 2+ subfolders). "
            "Create modules with `eos new module <name>` first, or set topology with `eos topology set modular-monolith`."
        )
        return 2
    stacks = manifest.get("stacks", {})
    py = [d for s, v in stacks.items() if s == "python" for d in as_dirs(v) if _within(mr, d)]
    ts = [d for s, v in stacks.items() if s == "typescript" for d in as_dirs(v) if _within(mr, d)]
    w = Writer(root, manifest, args.dry_run, False)
    lines = []
    if py:
        d = py[0]
        rel = Path(mr).relative_to(d) if d not in (".", "") else Path(mr)
        parts = [p for p in rel.parts if p != "src"]
        pkg = ".".join(parts)
        cfg_rel = os.path.normpath(f"{d}/.importlinter")
        w.seed(cfg_rel, IMPORTLINTER_TPL.format(root_pkg=parts[0], pkg=pkg))
        lines.append(f"python: `uv add --dev import-linter` then `lint-imports` in {d} (root package {parts[0]})")
    if ts:
        d = ts[0]
        rel = Path(mr).relative_to(d).as_posix() if d not in (".", "") else mr
        cfg_rel = os.path.normpath(f"{d}/.dependency-cruiser.cjs")
        w.seed(cfg_rel, DEPCRUISE_TPL.format(mr=rel, mr_re=re.escape(rel).replace("\\", "\\\\"), src=rel.split("/")[0]))
        lines.append(f"ts: `npx depcruise {rel.split('/')[0]} --config .dependency-cruiser.cjs` in {d}")
    if not py and not ts:
        eprint(f"modules in {mr} are not inside a Python or TypeScript stack dir; see .eos/packs/ref/topologies.md")
        return 2
    done = manifest.setdefault("scaffolded", [])
    if "boundaries" not in done:
        done.append("boundaries")
    if not args.dry_run:
        save_manifest(root, manifest)
    print(f"eos scaffold boundaries: modules in {mr}/{' (DRY RUN)' if args.dry_run else ''}")
    for status, rel in w.report:
        print(f"  {status:<8} {rel}")
    for ln in lines:
        print(f"  next: {ln}")
    print('  then: `eos ratchet add boundaries "<command>"` (old violations baselined) or add it to CI')
    return 0


def _strip_eos_hooks(obj):
    if isinstance(obj, dict):
        return {k: _strip_eos_hooks(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_eos_hooks(x) for x in obj if HOOK_MARK not in json.dumps(x)]
    return obj


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove what eos generated. Files you edited, memory, ADRs, stories and docs are kept."""
    root = Path(args.dir).resolve()
    manifest = load_manifest(root)
    if not manifest:
        eprint("no .eos/manifest.json here: nothing to uninstall")
        return 2
    removed, kept = [], []
    for rel, h in sorted(manifest.get("files", {}).items()):
        p = root / rel
        if not p.exists():
            continue
        if sha(read(p)) == h or args.force:
            removed.append(rel)
            if not args.dry_run:
                p.unlink()
        else:
            kept.append(rel)
    for rel in (".cursor/hooks.json", ".claude/settings.json"):
        p = root / rel
        if p.exists():
            try:
                cur = json.loads(read(p))
            except ValueError:
                kept.append(rel)
                continue
            new = _strip_eos_hooks(cur)
            if new != cur:
                removed.append(f"{rel} (eos hook entries)")
                if not args.dry_run:
                    write(p, json.dumps(new, indent=2) + "\n")
    ag = root / "AGENTS.md"
    if ag.exists():
        txt = read(ag)
        new = re.sub(r"<!-- eos:(\w+):begin -->.*?<!-- eos:\1:end -->\n*", "", txt, flags=re.DOTALL)
        if new != txt:
            removed.append("AGENTS.md (eos blocks; your sections kept)")
            if not args.dry_run:
                write(ag, new)
    if not args.dry_run:
        for d in sorted({(root / r).parent for r in manifest.get("files", {})}, key=lambda x: -len(x.parts)):
            while d != root and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
        if not kept or args.force:
            shutil.rmtree(root / ".eos", ignore_errors=True)
    print(f"eos uninstall {root}{' (DRY RUN)' if args.dry_run else ''}: removed {len(removed)}, kept {len(kept)}")
    for r in kept:
        print(f"  kept (you edited it): {r}   (--force removes it too)")
    print("  kept on purpose: memory/, docs/ (ADRs, lessons, stories), .github templates, .gitignore lines, scaffolds.")
    if kept and not args.force:
        print("  .eos/ kept because edited files remain; re-run with --force to remove everything eos generated.")
    return 0


# ----------------------------------------------------------------------------- ratchet (brownfield gates)
# Old violations are recorded once (baseline); a check fails only on violations that are new. When the count
# goes down, `eos ratchet update` (or `check --tighten`) lowers the baseline so it can never go back up.
# Same idea as ESLint bulk suppressions, PHPStan baselines, Betterer and dependency-cruiser --baseline.
RATCHET_FILE = ".eos/ratchet.json"
BASELINE_DIR = ".eos/baseline"
LINE_PATTERNS = (
    re.compile(r"^(?P<file>[^\s:()]+\.\w+)\((?P<line>\d+),\d+\):\s*(?P<msg>.+)$"),  # tsc
    re.compile(
        r"^(?P<file>[^\s:()]+?\.\w+):(?P<line>\d+)(?::\d+)?:?\s*(?P<msg>.+)$"
    ),  # ruff, mypy, flake8, eslint unix
)


def _norm_msg(msg: str) -> str:
    return re.sub(r"\d+", "#", msg.strip())[:200]


def ratchet_parse(out: str, parser: str, pattern: str | None = None) -> list[str]:
    """Fingerprints (file + message, line numbers dropped) so moving code up or down is not 'new'."""
    fps: list[str] = []
    if parser == "eslint-json":
        try:
            data = json.loads(out[out.find("[") :]) if "[" in out else []
        except ValueError:
            data = []
        for f in data:
            path = (
                os.path.relpath(f.get("filePath", "?")) if os.path.isabs(f.get("filePath", "")) else f.get("filePath")
            )
            for msg in f.get("messages", []):
                fps.append(f"{path}::{msg.get('ruleId') or _norm_msg(msg.get('message', ''))}")
        return fps
    if parser == "count":
        return ["line::" + _norm_msg(ln) for ln in out.splitlines() if ln.strip()]
    rxs = [re.compile(pattern)] if pattern else list(LINE_PATTERNS)
    for ln in out.splitlines():
        ln = re.sub(r"\x1b\[[0-9;]*m", "", ln).strip()
        for rx in rxs:
            m = rx.search(ln)
            if m:
                g = m.groupdict()
                fps.append(f"{g.get('file', '?')}::{_norm_msg(g.get('msg') or ln)}")
                break
    return fps


def load_ratchet(root: Path) -> dict:
    p = root / RATCHET_FILE
    try:
        return json.loads(read(p)) if p.exists() else {"checks": []}
    except ValueError:
        raise SystemExit(f"{RATCHET_FILE} is not valid JSON") from None


def _counter(fps: list[str]) -> dict[str, int]:
    c: dict[str, int] = {}
    for f in fps:
        c[f] = c.get(f, 0) + 1
    return c


def ratchet_run(root: Path, chk: dict, timeout: int = 900) -> tuple[str, list[str], str]:
    """(status, fingerprints, note). status: ok | skipped."""
    cmd = chk["cmd"]
    exe = split_cmd(cmd)[0] if cmd.strip() else ""
    if exe and not shutil.which(exe) and not (root / chk.get("cwd", ".") / exe).exists():
        return "skipped", [], f"not installed: {exe}"
    cwd = root / chk.get("cwd", ".")
    if "npx --no-install" in cmd and not ((cwd / "node_modules").is_dir() or (root / "node_modules").is_dir()):
        return "skipped", [], "node_modules missing: run your package install first"
    shell = ["cmd", "/c", cmd] if IS_WINDOWS else ["sh", "-c", cmd]
    code, out = run(shell, cwd=cwd, timeout=timeout)
    if code == 124:
        return "skipped", [], f"timeout after {timeout}s"
    if code == 127:
        return "skipped", [], "command not found"
    fps = ratchet_parse(out, chk.get("parser", "lines"), chk.get("pattern"))
    if code != 0 and not fps:  # a crash is not "zero violations": never baseline or pass on it
        first = next((ln for ln in out.splitlines() if ln.strip()), "")[:120]
        return "skipped", [], f"command failed (exit {code}) without findings: {first}"
    fps = [x for x in fps if not x.startswith((".eos/", "_bmad/", "_bmad-output/"))]  # eos/BMAD's own files
    if chk.get("cwd", ".") not in (".", ""):
        fps = [f"{chk['cwd'].rstrip('/')}/{f}" if not f.startswith("line::") else f for f in fps]
    return "ok", fps, ""


def suggest_ratchet_checks(root: Path, stacks: dict) -> list[dict]:
    """Checks that already exist in the project's own toolchain (nothing new is installed)."""
    out: list[dict] = []
    ruff = "ruff" if shutil.which("ruff") else ("uvx ruff" if shutil.which("uvx") else "")
    for sid, v in stacks.items():
        for d in as_dirs(v):
            dp = root / d
            sfx = "" if d in (".", "") else "-" + dir_slug(d)
            if sid == "python":
                if ruff:
                    out.append(
                        {
                            "name": f"ruff{sfx}",
                            "cmd": f"{ruff} check --output-format=concise --no-fix --extend-exclude .eos,_bmad,_bmad-output .",
                            "cwd": d,
                        }
                    )
                pyp = read(dp / "pyproject.toml") if (dp / "pyproject.toml").exists() else ""
                if "[tool.mypy]" in pyp or (dp / "mypy.ini").exists():
                    pre = "uv run " if (dp / "uv.lock").exists() else ""
                    out.append(
                        {"name": f"mypy{sfx}", "cmd": f"{pre}mypy --no-error-summary --hide-error-context .", "cwd": d}
                    )
                if (dp / ".importlinter").exists():
                    pre = "uv run " if (dp / "uv.lock").exists() else ""
                    out.append(
                        {
                            "name": f"boundaries{sfx}",
                            "cmd": f"{pre}lint-imports",
                            "cwd": d,
                            "parser": "regex",
                            "pattern": r"^-\s+(?P<file>\S+) -> (?P<msg>\S+)",
                        }
                    )
            if sid == "typescript":
                if any(dp.glob("eslint.config.*")) or any(dp.glob(".eslintrc*")):
                    out.append(
                        {
                            "name": f"eslint{sfx}",
                            "cmd": "npx --no-install eslint -f json .",
                            "cwd": d,
                            "parser": "eslint-json",
                        }
                    )
                if (dp / "tsconfig.json").exists():
                    out.append(
                        {
                            "name": f"tsc{sfx}",
                            "cmd": "npx --no-install tsc --noEmit --pretty false",
                            "cwd": d,
                        }
                    )
                if any(dp.glob(".dependency-cruiser.*")):
                    out.append(
                        {
                            "name": f"boundaries{sfx}",
                            "cmd": "npx --no-install depcruise . --output-type err",
                            "cwd": d,
                            "parser": "regex",
                            "pattern": r"(?:error|warn)\s+\S+:\s+(?P<file>\S+)\s+(?:→|->)\s+(?P<msg>\S+)",
                        }
                    )
    return out


def _baseline_path(root: Path, name: str) -> Path:
    return root / BASELINE_DIR / f"{name}.json"


def ratchet_baseline(root: Path, checks: list[dict], names: list[str] | None = None) -> list[tuple[str, str]]:
    rep = []
    for chk in checks:
        if names and chk["name"] not in names:
            continue
        status, fps, note = ratchet_run(root, chk)
        if status != "ok":
            rep.append((chk["name"], f"skipped ({note})"))
            continue
        data = {
            "cmd": chk["cmd"],
            "cwd": chk.get("cwd", "."),
            "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "count": len(fps),
            "fingerprints": dict(sorted(_counter(fps).items())),
        }
        write(_baseline_path(root, chk["name"]), json.dumps(data, indent=1) + "\n")
        rep.append((chk["name"], f"baseline {len(fps)} existing violation(s)"))
    return rep


def ratchet_check(root: Path, tighten: bool = False, strict: bool = False) -> tuple[int, list[str], dict]:
    """Compare every check with its baseline. Returns (exit code, report lines, state for eos status)."""
    cfg = load_ratchet(root)
    lines, state, failed = [], {"checks": {}, "time": time.time()}, False
    for chk in cfg.get("checks", []):
        name = chk["name"]
        bp = _baseline_path(root, name)
        if not bp.exists():
            lines.append(f"  {name:<18} no baseline yet -> `eos ratchet update {name}` once the tool runs here")
            state["checks"][name] = {"status": "no-baseline"}
            failed = failed or strict
            continue
        base = json.loads(read(bp))
        status, fps, note = ratchet_run(root, chk)
        if status != "ok":
            lines.append(f"  {name:<18} skipped ({note})")
            state["checks"][name] = {"status": "skipped", "note": note}
            failed = failed or strict
            continue
        cur, old = _counter(fps), base.get("fingerprints", {})
        new = {k: n - old.get(k, 0) for k, n in cur.items() if n > old.get(k, 0)}
        n_new, total, before = sum(new.values()), len(fps), base.get("count", 0)
        state["checks"][name] = {"status": "new" if n_new else "ok", "count": total, "baseline": before, "new": n_new}
        if n_new:
            failed = True
            lines.append(f"  {name:<18} FAIL: {n_new} new violation(s) (now {total}, baseline {before})")
            for k in list(new)[:15]:
                f, _, msg = k.partition("::")
                lines.append(f"      new: {f}: {msg}")
            if len(new) > 15:
                lines.append(f"      ... {len(new) - 15} more")
        elif total < before:
            if tighten:
                base.update(count=total, fingerprints=dict(sorted(cur.items())))
                base["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                write(bp, json.dumps(base, indent=1) + "\n")
                lines.append(f"  {name:<18} ok, tightened: {before} -> {total}")
            else:
                lines.append(f"  {name:<18} ok, improved {before} -> {total}: lock it in with `eos ratchet update`")
        else:
            lines.append(f"  {name:<18} ok ({total} old violation(s), none new)")
    try:
        write(root / ".eos/state/ratchet.json", json.dumps(state) + "\n")
    except OSError:
        pass
    return (1 if failed else 0), lines, state


def cmd_ratchet(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = load_ratchet(root)
    if args.action == "init":
        m = load_manifest(root)
        if not cfg.get("checks"):
            cfg["checks"] = suggest_ratchet_checks(root, m.get("stacks", {}))
            if not args.dry_run:
                write(root / RATCHET_FILE, json.dumps(cfg, indent=2) + "\n")
        if not cfg["checks"]:
            print("eos ratchet: no lint/type/boundary tools found to baseline. Add one:")
            print('  eos ratchet add <name> "<command that prints file:line: message>"')
            return 0
        print(f"eos ratchet init: {len(cfg['checks'])} check(s) -> {RATCHET_FILE}")
        for name, msg in [] if args.dry_run else ratchet_baseline(root, cfg["checks"]):
            print(f"  {name:<18} {msg}")
        print("  commit .eos/ratchet.json and .eos/baseline/. New violations now fail; old ones are tracked.")
        return 0
    if args.action == "add":
        if not args.name or not args.cmd:
            eprint('usage: eos ratchet add <name> "<command>" [--parser lines|eslint-json|count|regex] [--cwd DIR]')
            return 2
        cfg["checks"] = [c for c in cfg.get("checks", []) if c["name"] != args.name]
        chk = {"name": args.name, "cmd": args.cmd, "cwd": args.cwd or ".", "parser": args.parser}
        if args.pattern:
            chk["pattern"], chk["parser"] = args.pattern, "regex"
        cfg["checks"].append(chk)
        write(root / RATCHET_FILE, json.dumps(cfg, indent=2) + "\n")
        for name, msg in ratchet_baseline(root, cfg["checks"], [args.name]):
            print(f"  {name:<18} {msg}")
        return 0
    if args.action == "update":
        names = [args.name] if args.name else None
        for name, msg in ratchet_baseline(root, cfg.get("checks", []), names):
            print(f"  {name:<18} {msg}")
        print("  baseline rewritten: review the diff of .eos/baseline/ (it should only go down).")
        return 0
    if not cfg.get("checks"):
        print("eos ratchet: no checks configured (eos ratchet init)")
        return 0
    rc, lines, _ = ratchet_check(root, tighten=args.tighten, strict=args.strict)
    print(f"eos ratchet check: {'OK' if rc == 0 else 'FAILED'}")
    print("\n".join(lines))
    if rc:
        print("  fix the new violations (only those). If a file moved, `eos ratchet update` in the same PR.")
    return rc


# ----------------------------------------------------------------------------- adopt (existing projects)
AGENT_RULE_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".clinerules",
    ".windsurfrules",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".junie/guidelines.md",
    "CONVENTIONS.md",
)
LINT_CONFIGS = (
    "ruff.toml",
    ".ruff.toml",
    ".flake8",
    "setup.cfg",
    "tox.ini",
    "mypy.ini",
    ".pylintrc",
    ".editorconfig",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    "prettier.config.js",
    "biome.json",
    "biome.jsonc",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.ts",
    ".golangci.yml",
    ".rubocop.yml",
    "analysis_options.yaml",
    ".stylelintrc.json",
    ".pre-commit-config.yaml",
    ".husky",
    "lefthook.yml",
)
COVERAGE_CONFIGS = (
    ".coveragerc",
    "codecov.yml",
    ".codecov.yml",
    ".nycrc",
    ".nycrc.json",
    "jest.config.js",
    "vitest.config.ts",
)
LOCKFILES = {
    "python": ("uv.lock", "poetry.lock", "Pipfile.lock", "pdm.lock", "requirements.txt"),
    "typescript": ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb"),
    "flutter": ("pubspec.lock",),
}
FRAMEWORK_DEPS = {
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "nuxt": "Nuxt",
    "svelte": "Svelte",
    "@angular/core": "Angular",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "fastify": "Fastify",
    "react-native": "React Native",
    "expo": "Expo",
    "prisma": "Prisma",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "celery": "Celery",
    "sqlalchemy": "SQLAlchemy",
    "pandas": "pandas",
    "pytest": "pytest",
    "jest": "Jest",
    "vitest": "Vitest",
    "@playwright/test": "Playwright",
    "cypress": "Cypress",
}


def _deps(d: Path) -> dict[str, str]:
    deps: dict[str, str] = {}
    try:
        pj = json.loads(read(d / "package.json"))
        for k in ("dependencies", "devDependencies"):
            deps.update(pj.get(k, {}) or {})
    except (OSError, ValueError):
        pass
    for f in ("pyproject.toml", "requirements.txt"):
        if (d / f).exists():
            for m in re.finditer(
                r"""["']?([A-Za-z][\w.-]*)(\[[^\]]*\])?\s*((?:[<>=!~^]=?|@)\s*[^"',\s]+)?["']?""", read(d / f)
            ):
                name = m.group(1).lower()
                if name in FRAMEWORK_DEPS or f == "requirements.txt":
                    deps.setdefault(name, (m.group(3) or "").strip())
    return deps


def _commands(d: Path) -> list[str]:
    out = []
    try:
        scripts = json.loads(read(d / "package.json")).get("scripts", {})
        out += [
            f"npm-script:{k}"
            for k in scripts
            if k in ("dev", "build", "test", "lint", "typecheck", "format", "e2e", "start")
        ]
    except (OSError, ValueError):
        pass
    if (d / "Makefile").exists():
        targets = re.findall(r"(?m)^([A-Za-z][\w-]*):", read(d / "Makefile"))
        out += [f"make {x}" for x in targets[:8]]
    if (d / "justfile").exists():
        out += [f"just {x}" for x in re.findall(r"(?m)^([A-Za-z][\w-]*)\s*:", read(d / "justfile"))[:8]]
    if (d / "Taskfile.yml").exists():
        out.append("task (Taskfile.yml)")
    pyp = read(d / "pyproject.toml") if (d / "pyproject.toml").exists() else ""
    if (
        "pytest" in pyp
        or (d / "pytest.ini").exists()
        or (d / "tests").is_dir()
        and any((d / "tests").glob("test_*.py"))
    ):
        out.append("pytest")
    if (d / "tox.ini").exists():
        out.append("tox")
    if (d / "noxfile.py").exists():
        out.append("nox")
    return out


def _coverage_pct(root: Path) -> str:
    for rel in ("coverage.xml", "coverage/cobertura-coverage.xml"):
        p = root / rel
        if p.exists():
            m = re.search(r'line-rate="([\d.]+)"', read(p)[:4000])
            if m:
                return f"{float(m.group(1)) * 100:.0f}% ({rel})"
    for rel in ("coverage/lcov.info", "lcov.info"):
        p = root / rel
        if p.exists():
            txt = read(p)
            lf = sum(int(x) for x in re.findall(r"^LF:(\d+)", txt, re.MULTILINE))
            lh = sum(int(x) for x in re.findall(r"^LH:(\d+)", txt, re.MULTILINE))
            if lf:
                return f"{lh * 100 / lf:.0f}% ({rel})"
    return ""


def scan_repo(root: Path, stacks: dict) -> dict:
    """Offline, read-only scan for `eos adopt`: what is here, how it is built and tested, what is risky."""
    f = repo_facts(root)
    stack_dirs = {sid: as_dirs(v) for sid, v in stacks.items()}
    units = sorted({d for v in stack_dirs.values() for d in v}) or ["."]
    frameworks, deps_n, unpinned, commands, lock = set(), 0, 0, {}, {}
    for d in units:
        deps = _deps(root / d)
        deps_n += len(deps)
        unpinned += sum(1 for v in deps.values() if v in ("", "*", "latest") or v.startswith(">="))
        frameworks |= {FRAMEWORK_DEPS[k] for k in deps if k in FRAMEWORK_DEPS}
        commands[d] = _commands(root / d)
    for sid, dirs in stack_dirs.items():
        for d in dirs:
            names = LOCKFILES.get(sid, ())
            if names:
                hit = next((n for n in names if (root / d / n).exists() or (root / n).exists()), "")
                lock[f"{sid}@{d}"] = hit
    agent_rules = []
    for rel in AGENT_RULE_FILES:
        p = root / rel
        if p.is_file():
            txt = read(p)
            eos_owned = "<!-- eos:" in txt or "eos-managed" in txt
            agent_rules.append({"path": rel, "lines": len(txt.splitlines()), "tokens": tokens(txt), "eos": eos_owned})
        elif p.is_dir():
            agent_rules.append({"path": rel + "/", "lines": len(list(p.iterdir())), "tokens": 0, "eos": False})
    for p in sorted((root / ".cursor/rules").glob("*.mdc")) if (root / ".cursor/rules").is_dir() else []:
        if not p.name.startswith("eos-"):
            agent_rules.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "lines": len(read(p).splitlines()),
                    "tokens": tokens(read(p)),
                    "eos": False,
                }
            )
    lint = sorted(
        {rel.as_posix() for rel in iter_files(root, 2) if rel.name in LINT_CONFIGS}
        | {x for x in LINT_CONFIGS if (root / x).is_dir()}
    )
    cov_cfg = sorted(rel.as_posix() for rel in iter_files(root, 2) if rel.name in COVERAGE_CONFIGS)
    pyps = [rel for rel in iter_files(root, 2) if rel.name == "pyproject.toml"]
    if any("[tool.coverage" in read(root / r) for r in pyps):
        cov_cfg.append("pyproject [tool.coverage]")
    top: dict[str, int] = {}
    for rel in iter_files(root, 6):
        if rel.suffix in CODE_EXT:
            k = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            top[k] = top.get(k, 0) + 1
    churn: dict[str, int] = {}
    contributors, last = 0, ""
    if f["git"]:
        log = git_out(root, "log", "--since=12.months", "--name-only", "--format=", timeout=60)
        for ln in log.splitlines():
            if ln.strip() and Path(ln).suffix in CODE_EXT and not TEST_RX.search(ln) and (root / ln).exists():
                churn[ln] = churn.get(ln, 0) + 1
        contributors = len(git_out(root, "shortlog", "-sn", "HEAD").splitlines())
        last = git_out(root, "log", "-1", "--format=%cs")
    tracked = git_out(root, "ls-files").splitlines() if f["git"] else []
    secrets = [x for x in tracked if is_secret_path(x)][:10]
    big = []
    for x in tracked[:20000]:
        try:
            if (root / x).stat().st_size > 1_000_000:
                big.append(x)
        except OSError:
            pass
    todo = 0
    for rel in list(iter_files(root, 6))[:5000]:
        if rel.suffix in CODE_EXT:
            try:
                todo += len(
                    re.findall(r"\b(TODO|FIXME|HACK|XXX)\b", (root / rel).read_text(errors="ignore", encoding="utf-8"))
                )
            except OSError:
                pass
    deps_bot = [x for x in (".github/renovate.json", "renovate.json", ".github/dependabot.yml") if (root / x).exists()]
    return {
        "facts": f,
        "stacks": stack_dirs,
        "frameworks": sorted(frameworks),
        "commands": commands,
        "lockfiles": lock,
        "deps": {"count": deps_n, "unpinned": unpinned, "update_bot": deps_bot},
        "agent_rules": agent_rules,
        "lint_configs": lint,
        "coverage": {"configs": cov_cfg, "measured": _coverage_pct(root)},
        "folders": dict(sorted(top.items(), key=lambda kv: -kv[1])[:12]),
        "churn": sorted(churn.items(), key=lambda kv: -kv[1])[:10],
        "contributors": contributors,
        "last_commit": last,
        "tracked_secrets": secrets,
        "big_files": big[:5],
        "todo": todo,
        "docs": {
            "readme": any((root / x).exists() for x in ("README.md", "README.rst", "README")),
            "adr": (root / "docs/adr").is_dir() or (root / "doc/adr").is_dir(),
            "architecture": any((root / x).exists() for x in ("ARCHITECTURE.md", "docs/architecture")),
        },
    }


def render_project_map(scan: dict, cfg: dict) -> str:
    """Agent-facing map: read on demand (linked from AGENTS.md), so it stays short and factual."""
    lines = [
        f"# Project map: {cfg.get('project_name', '')}",
        "",
        f"*Generated by `eos adopt` on {dt.datetime.now().astimezone().date().isoformat()}; refresh with `eos adopt --report-only`. Facts only.*",
        "",
        f"- **Mode / topology:** {cfg.get('mode')} / {cfg.get('topology')}",
        f"- **Languages (files):** {', '.join(f'{k} {v}' for k, v in list(scan['facts']['by_ext'].items())[:6]) or 'none'}",
        f"- **Frameworks:** {', '.join(scan['frameworks']) or 'none detected'}",
        "",
        "## Where things are",
        "| Folder | Source files |",
        "|---|---|",
    ]
    lines += [f"| `{k}` | {v} |" for k, v in scan["folders"].items()]
    lines += ["", "## Build and test commands (from the project's own files)", "| Dir | Commands found |", "|---|---|"]
    lines += [f"| `{d}` | {', '.join(c) or 'none found'} |" for d, c in scan["commands"].items()]
    lines += ["", "## Quality tooling already here"]
    lines.append(f"- Lint/format configs: {', '.join(scan['lint_configs']) or 'none'}")
    lines.append(f"- CI: {', '.join(scan['facts']['ci']) or 'none'}")
    lines.append(
        f"- Tests: {scan['facts']['test_files']} test files for {scan['facts']['code_files']} source files"
        + (f"; coverage {scan['coverage']['measured']}" if scan["coverage"]["measured"] else "")
    )
    rules = [r for r in scan["agent_rules"] if not r["eos"]]
    if rules:
        lines += ["", "## Existing agent instructions (kept; eos adds to them)"]
        lines += [f"- `{r['path']}` ({r['lines']} lines)" for r in rules]
    if scan["churn"]:
        lines += ["", "## Hot spots (most changed in 12 months: test these first)"]
        lines += [f"- `{p}` ({n} commits)" for p, n in scan["churn"][:8]]
    return "\n".join(lines) + "\n"


def improvement_items(scan: dict, cfg: dict) -> list[tuple[str, str, str, str]]:
    """(priority, item, why, how). P0 = safety, P1 = safety net and gates, P2 = structure and hygiene."""
    f, items = scan["facts"], []
    if scan["tracked_secrets"]:
        items.append(
            (
                "P0",
                f"Remove tracked secret-like files ({len(scan['tracked_secrets'])}) and rotate what they held",
                "anything committed is readable by everyone with repo access, forever (history)",
                "git rm --cached <file>; add to .gitignore; rotate the credential; ask a human",
            )
        )
    missing_lock = [k for k, v in scan["lockfiles"].items() if not v]
    if missing_lock:
        items.append(
            (
                "P0",
                f"Commit a lockfile for {', '.join(missing_lock)}",
                "without one, two installs can get different code: builds are not reproducible",
                "uv lock / pnpm install / flutter pub get, then commit the lockfile",
            )
        )
    if not f["ci"]:
        items.append(
            (
                "P0",
                "Add CI that runs tests and the ratchet on every PR",
                "checks that only run on laptops are skipped under pressure",
                "eos update (stack CI workflows) or add `python3 .eos/bin/eos.py ratchet check` to your CI",
            )
        )
    else:
        items.append(
            (
                "P1",
                "Run `eos ratchet check` in your existing CI after dependencies install",
                "the baseline only protects you if every PR is compared with it",
                "add a step: python3 .eos/bin/eos.py ratchet check",
            )
        )
    ratio = f["test_files"] / max(1, f["code_files"] - f["test_files"])
    if f["test_files"] == 0 or ratio < 0.2:
        hot = ", ".join(p for p, _ in scan["churn"][:3]) or "the most-changed files"
        items.append(
            (
                "P1",
                f"Characterization tests for the hot spots ({hot})",
                "you can't change code safely without a net; start where change happens most",
                'agent prompt: "Write characterization tests that pin the current behaviour of <file> (migration pack)"',
            )
        )
    if not scan["coverage"]["configs"] and f["test_files"]:
        items.append(
            (
                "P2",
                "Measure coverage and ratchet it (never goes down)",
                "a number that only goes up stops quality sliding without blocking today's work",
                "pytest --cov / vitest --coverage; then eos ratchet add coverage <command>",
            )
        )
    rules = [r for r in scan["agent_rules"] if not r["eos"]]
    heavy = [r for r in rules if r["tokens"] > 1500]
    if heavy or len(rules) > 2:
        items.append(
            (
                "P1",
                "Consolidate agent instructions into AGENTS.md 'Project specifics'",
                "several or long rule files cost tokens every request and contradict each other",
                "move durable facts into AGENTS.md, delete duplicates; BMAD: bmad-project-context (audit)",
            )
        )
    if (
        (cfg.get("tools") and "cline" in cfg["tools"])
        and any(r["path"] == ".clinerules/" for r in rules) is False
        and any(r["path"] == ".clinerules" for r in rules)
    ):
        items.append(
            (
                "P1",
                "Turn the .clinerules file into a folder so eos rules can sit next to yours",
                "Cline reads a .clinerules folder; eos skipped its Cline rules to avoid touching your file",
                "mkdir .clinerules.d && git mv .clinerules .clinerules.d/project.md && git mv .clinerules.d .clinerules",
            )
        )
    if not scan["deps"]["update_bot"]:
        items.append(
            (
                "P1",
                "Turn on dependency updates (Renovate config was seeded by eos)",
                "old dependencies accumulate known vulnerabilities and get harder to upgrade",
                "enable the Renovate GitHub app (or Dependabot) for this repo",
            )
        )
    if cfg.get("topology") in ("modular-monolith", "microservices") or len(scan["folders"]) >= 4:
        items.append(
            (
                "P2",
                "Write down and enforce module/service boundaries",
                "boundaries that aren't checked erode with every change, faster with AI",
                "eos scaffold boundaries (modules) / service catalog docs/architecture/services.md",
            )
        )
    if not scan["docs"]["architecture"]:
        items.append(
            (
                "P2",
                "One-page architecture overview + first ADRs for decisions already made",
                "agents and new people guess the design otherwise",
                'agent prompt: "Read the code and draft docs/architecture/overview.md (architecture pack); ask before guessing"',
            )
        )
    if scan["todo"] > 50:
        items.append(
            (
                "P2",
                f"Triage {scan['todo']} TODO/FIXME comments into docs/plans/tech-debt.md",
                "untracked debt is invisible debt",
                'agent prompt: "List TODO/FIXME by area, propose the top 10 for tech-debt.md (maintenance pack)"',
            )
        )
    if scan["big_files"]:
        items.append(
            (
                "P2",
                f"Review large tracked files ({len(scan['big_files'])})",
                "big binaries slow every clone and CI run",
                "move to releases/LFS/object storage if not needed in git",
            )
        )
    return sorted(items, key=lambda it: it[0])


def render_baseline_report(scan: dict, cfg: dict, ratchet_rep: list[tuple[str, str]]) -> str:
    f = scan["facts"]
    lines = [
        f"# Baseline report: {cfg.get('project_name', '')}",
        "",
        (
            f"*`eos adopt` on {dt.datetime.now().astimezone().date().isoformat()}. Re-run `eos adopt --report-only` to compare. "
            "Numbers come from files and git only (offline; nothing was installed or built).*"
        ),
        "",
        "| Signal | Value |",
        "|---|---|",
        f"| Source files / test files | {f['code_files']} / {f['test_files']} |",
        f"| Measured coverage | {scan['coverage']['measured'] or 'not found'} |",
        f"| Commits / contributors / tags | {f['commits']} / {scan['contributors']} / {f['tags']} |",
        f"| Last commit | {scan['last_commit'] or '-'} |",
        f"| CI | {', '.join(f['ci']) or 'none'} |",
        "| Lockfiles | " + (", ".join(k + ": " + (v or "MISSING") for k, v in scan["lockfiles"].items()) or "-") + " |",
        f"| Dependencies (declared / unpinned-looking) | {scan['deps']['count']} / {scan['deps']['unpinned']} |",
        f"| Dependency update bot | {', '.join(scan['deps']['update_bot']) or 'none'} |",
        f"| TODO/FIXME/HACK | {scan['todo']} |",
        f"| Tracked secret-like files | {len(scan['tracked_secrets'])} (names in eos output only, never contents) |",
        f"| Agent instruction files | {', '.join(r['path'] for r in scan['agent_rules']) or 'none'} |",
        "",
        "## Ratchet baselines (old violations recorded; only new ones fail)",
    ]
    lines += [f"- {n}: {m}" for n, m in ratchet_rep] or [
        "- none (no lint/type tools found; add one with `eos ratchet add`)"
    ]
    lines += ["", "Detailed plan: `docs/plans/improvement-plan.md`. Map for agents: `docs/eos/project-map.md`."]
    return "\n".join(lines) + "\n"


def render_improvement_plan(items: list[tuple[str, str, str, str]], cfg: dict) -> str:
    lines = [
        f"# Improvement plan: {cfg.get('project_name', '')}",
        "",
        f"*Seeded by `eos adopt` on {dt.datetime.now().astimezone().date().isoformat()}; yours to edit. Work top-down, one item per PR.*",
        "*`eos next` picks the first unchecked item. P0 = safety, P1 = safety net and gates, P2 = structure.*",
        "",
    ]
    for i, (pri, item, why, how) in enumerate(items, 1):
        lines += [f"- [ ] **{pri} · {item}**", f"  - Why: {why}", f"  - How: {how}"]
    if not items:
        lines.append("- [ ] Nothing urgent found. Next: pick the riskiest area and add characterization tests.")
    return "\n".join(lines) + "\n"


def cmd_adopt(args: argparse.Namespace) -> int:
    """Bring an existing project under eos without breaking anything: scan, report, merge, ratchet, plan."""
    home = find_eos_home()
    if not home:
        eprint("engineering-os repo not found (set EOS_HOME)")
        return 2
    root = Path(args.dir).resolve()
    if not root.is_dir():
        eprint(f"{root} is not a folder")
        return 2
    _, stacks = load_home_packs(home)
    m = load_manifest(root)
    if not m and (looks_like_workspace(root) or (root / WS_FILE).exists()):
        eprint(
            f"{root} is a multi-repo workspace: run `eos adopt <repo>` per repo, then `eos workspace init|sync` here."
        )
        return 2
    sd = m.get("stacks") or detect_stacks(root, stacks)[0]
    scan = scan_repo(root, sd)
    mode, mev = detect_mode(root, scan["facts"])
    if mode == "greenfield" and not args.mode:
        print("eos adopt: this folder has little or no code. For a new product run `eos start` or `eos init`.")
    topo, tev, _ = detect_topology(root, sd)
    preview = {
        "project_name": args.name or root.name,
        "mode": norm_mode(args.mode) or m.get("mode") or ("brownfield" if mode == "greenfield" else mode),
        "topology": args.topology or m.get("topology") or topo,
        "tools": parse_tools(args.tools) if args.tools else None,
    }
    print(f"eos adopt -> {root}{' (SCAN ONLY)' if args.scan_only else ''}")
    print(
        f"  found : {', '.join(f'{k} {v}' for k, v in list(scan['facts']['by_ext'].items())[:5]) or 'no source files'}"
    )
    print(f"  stacks: {', '.join(k + '@' + '+'.join(as_dirs(v)) for k, v in sd.items()) or '(none with a pack)'}")
    pm_, pt_ = preview["mode"], preview["topology"]
    print(f"  mode  : {pm_} ({MODE_PLAIN.get(pm_, '-')}; {'; '.join(mev)})")
    print(
        f"  shape : {pt_} ({TOPOLOGY_PLAIN.get(pt_, 'how the code is laid out')}"
        + (f"; {'; '.join(tev)})" if tev else ")")
    )
    rules = [r["path"] for r in scan["agent_rules"] if not r["eos"]]
    print(f"  agent rules already here: {', '.join(rules) or 'none'} (kept; eos only adds marked blocks)")
    print(f"  lint/format configs kept as they are: {', '.join(scan['lint_configs']) or 'none'}")
    items = improvement_items(scan, preview)
    if args.scan_only:
        print("  top improvements:")
        for pri, item, *_ in items[:5]:
            print(f"    {pri}  {item}")
        print("  nothing was written. Run `eos adopt` to install (non-destructive) or `--report-only` for the reports.")
        return 0
    rc = 0
    if not args.report_only:
        ns = argparse.Namespace(**vars(args))
        ns.adopt, ns.mode, ns._from_adopt = True, preview["mode"], True
        ns.stacks = getattr(args, "stacks", "auto") or "auto"
        ns.no_ci = args.no_ci or bool(scan["facts"]["ci"])  # their CI stays theirs; eos-core is added below
        rc = cmd_init(ns, update=bool(m))
        m = load_manifest(root)
        if scan["facts"]["ci"] and not args.no_ci and not args.dry_run:
            w = Writer(root, m, False, False, adopt=True)
            w.managed(".github/workflows/eos-core.yml", read(home / "core/ci/eos-core.yml"))
            save_manifest(root, m)
    ratchet_rep: list[tuple[str, str]] = []
    reconf = getattr(args, "reconfigure", False)  # new answers don't change what your code does today
    if not args.dry_run and not args.report_only and not args.no_baseline and not reconf:
        cfg = load_ratchet(root)
        if not cfg.get("checks"):
            cfg["checks"] = suggest_ratchet_checks(root, m.get("stacks", sd))
            write(root / RATCHET_FILE, json.dumps(cfg, indent=2) + "\n")
        if cfg["checks"]:
            print(
                f"  ratchet (old problems allowed, new ones blocked): recording today's results of"
                f" {len(cfg['checks'])} check(s) (runs your linters once; may take a minute)"
            )
        else:
            print(
                "  ratchet (old problems allowed, new ones blocked): no lint or type-check tool found to record yet;"
                " `eos next` will guide you"
            )
        ratchet_rep = ratchet_baseline(root, cfg["checks"])
        for n, msg in ratchet_rep:
            print(f"    {n:<18} {msg}")
            hint = ratchet_skip_hint(msg, next((c for c in cfg["checks"] if c["name"] == n), {}))
            if hint:
                print(f"    {'':<18} -> {hint}")
    if not args.dry_run:
        cfg = {**preview, **{k: m.get(k) for k in ("mode", "topology", "tools") if m.get(k)}}
        write(root / "docs/eos/project-map.md", render_project_map(scan, cfg))
        write(root / "docs/eos/baseline-report.md", render_baseline_report(scan, cfg, ratchet_rep))
        plan = root / "docs/plans/improvement-plan.md"
        if not plan.exists():
            write(plan, render_improvement_plan(items, cfg))
        write(
            root / ".eos/state/scan.json",
            json.dumps({k: v for k, v in scan.items() if k != "facts"} | {"facts": scan["facts"]}, default=str) + "\n",
        )
        if m:
            m["project_map"] = "docs/eos/project-map.md"
            save_manifest(root, m)
            _resync(root)
        print("  wrote : docs/eos/project-map.md, docs/eos/baseline-report.md, docs/plans/improvement-plan.md")
        print(f"          (secret-like tracked files: {', '.join(scan['tracked_secrets']) or 'none'})")
    print(
        "  next  : `eos next` (it reads the plan). Review the diff before committing: nothing of yours was overwritten."
    )
    if not args.dry_run and not args.report_only:
        mm = load_manifest(root)
        print()
        print(
            plain_summary(
                describe_project(scan["facts"], project_frameworks(root, scan["frameworks"]), preview["topology"]),
                mm.get("tools") or [],
                hooks=not args.no_precommit,
                ci=not args.no_ci,
                ratchet=mm.get("gates") == "ratchet",
                docs=[
                    ("docs/eos/project-map.md", "what is where"),
                    ("docs/eos/baseline-report.md", "the health of the code today"),
                    ("docs/plans/improvement-plan.md", "what to fix first"),
                ],
            )
        )
    return rc


def ratchet_skip_hint(msg: str, chk: dict) -> str:
    """Plain words for a ratchet check that could not run: why, and what to do about it."""
    if "node_modules missing" in msg:
        return f"install the project's packages first (e.g. `npm install` in {chk.get('cwd', '.')}), then `eos ratchet update`"
    if "not installed" in msg or "command not found" in msg:
        return "that tool isn't installed on this computer; install it, then `eos ratchet update`"
    if "timeout" in msg:
        return "it took too long; try again with `eos ratchet update`, or remove the check from .eos/ratchet.json"
    if "without findings" in msg:
        cmd = chk.get("cmd", "")
        why = "the tool stopped with an error instead of listing problems"
        if "eslint" in cmd or "eslint" in msg.lower():
            return (
                f"{why}. Often ESLint is scanning built files (dist/, .next/, build/) or its config fails to load:"
                " add those folders to ESLint's ignore list, run the command once yourself to see the error, then"
                " `eos ratchet update`"
            )
        return f"{why}. Run `{cmd}` yourself to see the error, fix it, then `eos ratchet update`"
    return ""


# ----------------------------------------------------------------------------- navigator (status / next / explain)
# A small state machine (core/lifecycle.json): per mode, ordered phases with declarative exit criteria. The
# current phase is the first one not yet done. `eos next` = blockers first, then work in progress, then the first
# unmet exit criterion. Offline and cheap (no linters are run; gate results come from the last check).
def load_lifecycle(root: Path) -> dict:
    for p in (root / ".eos/lifecycle.json", (find_eos_home() or root) / "core/lifecycle.json"):
        if p.exists():
            try:
                return json.loads(read(p))
            except ValueError:
                eprint(f"{p} is not valid JSON; using defaults")
    return {"modes": {}, "phases": {}}


def _globs(root: Path, pattern: str) -> list[Path]:
    return sorted(p for p in root.glob(pattern) if p.is_file() and ".eos-new" not in p.name)


def _section(text: str, heading: str) -> str:
    m = re.search(rf"(?ms)^#+\s*{re.escape(heading)}[^\n]*\n(.*?)(?=^#+\s|\Z)", text)
    return m.group(1) if m else ""


def _table_status(text: str) -> list[str]:
    rows = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(rows) < 3:
        return []
    head = [c.strip().lower() for c in rows[0].strip("|").split("|")]
    if "status" not in head:
        return []
    i = head.index("status")
    out = []
    for r in rows[2:]:
        cells = [c.strip().lower() for c in r.strip().strip("|").split("|")]
        if len(cells) > i:
            out.append(cells[i])
    return out


def plan_items(root: Path) -> list[dict]:
    p = root / "docs/plans/improvement-plan.md"
    if not p.exists():
        return []
    items, cur = [], None
    for ln in read(p).splitlines():
        m = re.match(r"^- \[( |x|X)\] \*\*(P\d)\s*·\s*(.+?)\*\*", ln)
        if m:
            cur = {"done": m.group(1) != " ", "priority": m.group(2), "title": m.group(3).strip(), "how": "", "why": ""}
            items.append(cur)
            continue
        m = re.match(r"^\s+- (Why|How): (.+)$", ln)
        if m and cur:
            cur[m.group(1).lower()] = m.group(2).strip()
    return items


def nav_facts(root: Path, m: dict) -> dict:
    stories = []
    for p in _globs(root, "docs/stories/[0-9]*.md"):
        sm = re.search(r"\*\*Status:\*\*\s*([^\n]+)", read(p))
        st = (sm.group(1).strip().lower() if sm else "draft").split("|")[0].strip()
        title = read(p).splitlines()[0].lstrip("# ").strip() if read(p) else p.stem
        stories.append({"path": p.relative_to(root).as_posix(), "status": st, "title": title})
    plans = []
    for p in _globs(root, "docs/plans/[0-9]*.md"):
        sm = re.search(r"(?m)^Status:\s*(\w+)", read(p))
        if sm and sm.group(1).lower() == "active":
            plans.append({"path": p.relative_to(root).as_posix(), "title": read(p).splitlines()[0].lstrip("# ")})
    gates = {}
    for name in ("last-gates", "ratchet"):
        sp = root / f".eos/state/{name}.json"
        try:
            gates[name] = json.loads(read(sp)) if sp.exists() else None
        except ValueError:
            gates[name] = None
    eos_new = [p.relative_to(root).as_posix() for p in root.rglob("*.eos-new") if ".git" not in p.parts][:5]
    hand = root / "memory/handoff.md"
    handoff = bool(hand.exists() and re.search(r"(?m)^- \*\*(Goal|Next step):\*\*[ \t]*\S", read(hand)))
    branch, dirty, setup_only = "", 0, False
    if (root / ".git").exists():
        branch = git_out(root, "symbolic-ref", "--short", "-q", "HEAD")
        status = git_out(root, "status", "--porcelain", "-uall").splitlines()
        changed = [ln.split(maxsplit=1)[-1].strip('"') for ln in status if ln.strip()]
        dirty = len(changed)
        eos_paths = set(m.get("files", {})) | {"AGENTS.md", "CLAUDE.md", ".gitignore", ".pre-commit-config.yaml"}
        prefixes = (".eos/", "memory/", "docs/adr/", "docs/ai/", "docs/eos/", "docs/plans/", ".github/")
        prefixes += ("docs/architecture/services.md", "docs/architecture/modules.md", ".claude/", ".cursor/", ".cline/")
        setup_only = bool(changed) and all(c in eos_paths or c.startswith(prefixes) for c in changed)
    try:
        cfgj = json.loads(read(root / ".eos/config.json")) if (root / ".eos/config.json").exists() else {}
    except ValueError:
        cfgj = {}
    prot = cfgj.get("protected_branches", ["main", "master", "develop", "trunk", "release/*", "production"])
    f = repo_facts(root)
    return {
        "stories": stories,
        "plans": plans,
        "plan_items": plan_items(root),
        "gates": gates,
        "eos_new": eos_new,
        "handoff": handoff,
        "branch": branch,
        "dirty": dirty,
        "protected": bool(branch) and any(fnmatch.fnmatch(branch, g) for g in prot),
        "setup_only": setup_only,
        "facts": f,
        "bmad": (root / "_bmad").is_dir(),
    }


def eval_check(root: Path, c: dict, nf: dict) -> bool:
    if "any" in c:
        return any(eval_check(root, x, nf) for x in c["any"])
    if "exists" in c:
        return (
            bool(_globs(root, c["exists"])) if any(ch in c["exists"] for ch in "*?[") else (root / c["exists"]).exists()
        )
    if "glob_min" in c:
        return len(_globs(root, c["glob_min"])) >= int(c.get("n", 1))
    if "filled" in c:
        files = _globs(root, c["filled"])
        return bool(files) and all(c["placeholder"] not in read(p) for p in files)
    if "checked" in c:
        files = _globs(root, c["checked"])
        if not files:
            return False
        for p in files:
            sec = _section(read(p), c["heading"])
            if not re.search(r"(?m)^\s*- \[[xX]\]", sec) or re.search(r"(?m)^\s*- \[ \]", sec):
                return False
        return True
    if "tables" in c:  # each heading has a table with at least one data row (header + separator + row)
        files = _globs(root, c["tables"])
        return bool(files) and all(
            len([ln for ln in _section(read(p), h).splitlines() if ln.strip().startswith("|")]) >= 3
            for p in files
            for h in c["headings"]
        )
    if "table_status" in c:
        files = _globs(root, c["table_status"])
        sts = [s for p in files for s in _table_status(_section(read(p), c["heading"]))]
        return bool(sts) and all(any(s.startswith(v) for v in c["all_in"]) for s in sts)
    st = c.get("state", "")
    f = nf["facts"]
    if st == "stories_open_zero":
        return bool(nf["stories"]) and all(s["status"] == "done" for s in nf["stories"])
    if st == "tags_min_1":
        return f["tags"] >= 1
    if st.startswith("test_ratio_min_"):
        return f["test_files"] / max(1, f["code_files"] - f["test_files"]) >= float(st.rsplit("_", 1)[1])
    if st == "plan_p0_p1_done":
        items = nf["plan_items"]
        return all(i["done"] for i in items if i["priority"] in ("P0", "P1"))
    if st == "plan_all_done":
        return all(i["done"] for i in nf["plan_items"])
    return False


def gate_problems(nf: dict) -> list[str]:
    out = []
    lg = nf["gates"].get("last-gates")
    if lg and not lg.get("ok", True):
        out.append(f"`eos check` failed ({lg.get('summary', 'see output')})")
    ra = nf["gates"].get("ratchet")
    if ra:
        bad = [n for n, v in ra.get("checks", {}).items() if v.get("status") == "new"]
        if bad:
            out.append(f"ratchet found new violations in {', '.join(bad)}")
    return out


def nav_status(root: Path, m: dict) -> dict:
    lc = load_lifecycle(root)
    mode = m.get("mode") or detect_mode(root)[0]
    nf = nav_facts(root, m)
    skips = set(m.get("nav_skip") or [])
    nf["plan_items"] = [i for i in nf["plan_items"] if i["title"] not in skips]
    phases, current = [], None
    for pid in lc.get("modes", {}).get(mode, []):
        ph = lc["phases"].get(pid)
        if not ph:
            continue
        if m.get("profile") in ph.get("skip_profiles", []):
            phases.append({"id": pid, "title": ph["title"], "state": "skipped", "missing": []})
            continue
        missing = [c for c in ph.get("exit", []) if c.get("label") not in skips and not eval_check(root, c, nf)]
        state = "done" if not missing else ("current" if current is None else "todo")
        if state == "current":
            current = pid
        phases.append({"id": pid, "title": ph["title"], "state": state, "missing": missing})
    blockers = []
    for g in gate_problems(nf):
        blockers.append(
            {
                "say": f"Fix the failing gate: {g}",
                "why": "red gates first: everything else builds on them",
                "cmd": "eos check && eos ratchet check",
            }
        )
    notes = []
    if nf["eos_new"]:  # a note, not a blocker: an eos update must never stop your work
        notes.append(
            {
                "say": f"Merge {len(nf['eos_new'])} eos update(s) waiting next to your files ({nf['eos_new'][0]})",
                "why": "you edited a file eos manages; the new version is parked as <file>.eos-new",
                "cmd": "diff <file> <file>.eos-new; merge by hand; delete the .eos-new; eos sync",
            }
        )
    if nf["handoff"]:
        blockers.append(
            {
                "say": "Resume the unfinished work in memory/handoff.md",
                "why": "an agent stopped mid-task and left notes; finish or close it before starting something new",
                "prompt": "Read memory/handoff.md and continue from 'Next step'. Delete the handoff when resolved.",
            }
        )
    if nf["dirty"] and (nf["facts"]["commits"] == 0 or (nf["protected"] and nf["setup_only"])):
        first = nf["facts"]["commits"] == 0
        blockers.append(
            {
                "say": "Commit the eos setup" + ("" if first else " on a branch"),
                "why": "a clean starting point you can always come back to"
                + ("" if first else "; protected branches only change through reviewed PRs"),
                "cmd": ("" if first else "git switch -c chore/add-eos && ")
                + 'git add -A && git commit -m "chore: add engineering-os"',
            }
        )
    elif nf["protected"] and nf["dirty"]:
        blockers.append(
            {
                "say": f"Move your {nf['dirty']} uncommitted change(s) off '{nf['branch']}' to a branch",
                "why": "protected branches only change through reviewed PRs",
                "cmd": "git switch -c feat/<short-name>",
            }
        )
    wip = []
    for s in nf["stories"]:
        if s["status"] in ("in progress", "review"):
            wip.append(
                {
                    "say": f"Continue story {s['title']} ({s['status']})",
                    "why": "finish what is started before starting more (limits work in progress)",
                    "prompt": f"Continue {s['path']}: implement the remaining acceptance criteria as tests, then the full check.",
                }
            )
    for pl in nf["plans"]:
        wip.append(
            {
                "say": f"Continue plan: {pl['title']}",
                "why": "an active multi-session plan",
                "prompt": f"Read {pl['path']} and do the next unchecked step.",
            }
        )
    step = None
    cur = lc["phases"].get(current or "", {})
    for c in next((p["missing"] for p in phases if p["id"] == current), []):
        if c.get("from_plan"):
            todo = [i for i in nf["plan_items"] if not i["done"]]
            if todo:
                i = todo[0]
                how = i["how"]
                kind = "prompt" if how.startswith("agent prompt:") else ("cmd" if how.startswith("eos ") else "how")
                step = {
                    "say": f"{i['priority']}: {i['title']}",
                    "_label": i["title"],
                    "why": i["why"],
                    kind: how.removeprefix("agent prompt: ").strip('"'),
                }
                break
            continue
        if c.get("state") == "stories_open_zero" and not nf["stories"]:
            continue
        if c.get("state") == "stories_open_zero":
            open_s = [s for s in nf["stories"] if s["status"] != "done"]
            if open_s:
                s = open_s[0]
                step = {
                    "say": f"Next story: {s['title']} ({s['status']})",
                    "why": "small stories with acceptance criteria keep every change verifiable",
                    "prompt": f"Implement {s['path']}: acceptance criteria as tests first, then code; full check before done.",
                }
                break
        step = {k: c[k] for k in ("cmd", "prompt") if k in c} | ({"_explain": c["explain"]} if c.get("explain") else {})
        step.update(say=c.get("do", c.get("label", "")), why=c.get("why") or cur.get("why", ""), _label=c.get("label"))
        if c.get("bmad") and nf["bmad"]:
            step["bmad"] = c["bmad"]
        break
    if step is None and current is None:
        last = lc["phases"].get((lc.get("modes", {}).get(mode) or [""])[-1], {})
        step = {
            "say": last.get("then", "All phases done for this mode."),
            "why": "the exit criteria of every phase are met",
        }
    if step is None:
        step = {"say": f"Work on: {cur.get('goal', '')}", "why": cur.get("why", "")}
    nxt = (blockers or wip or [step])[0]
    if current and nxt is step:
        nxt.setdefault("pack", cur.get("pack"))
        nxt.setdefault("explain", nxt.pop("_explain", None) or cur.get("explain"))
    return {
        "mode": mode,
        "topology": m.get("topology"),
        "gates_mode": m.get("gates") or "strict",
        "teaching": m.get("teaching") or "off",
        "tools": list(m.get("tools") or []),
        "phase": current,
        "phase_title": cur.get("title") if current else "complete",
        "phase_goal": cur.get("goal", ""),
        "phases": [
            {k: v for k, v in p.items() if k != "missing"} | {"missing": [c.get("label", "") for c in p["missing"]]}
            for p in phases
        ],
        "blockers": blockers,
        "notes": notes,
        "skipped": sorted(skips),
        "in_progress": wip,
        "next": nxt,
        "git": {"branch": nf["branch"], "dirty": nf["dirty"]},
        "stories": {
            "open": sum(1 for s in nf["stories"] if s["status"] != "done"),
            "done": sum(1 for s in nf["stories"] if s["status"] == "done"),
        },
        "plan": {
            "open": sum(1 for i in nf["plan_items"] if not i["done"]),
            "done": sum(1 for i in nf["plan_items"] if i["done"]),
        },
        "gates": gate_problems(nf),
        "memory": (root / "memory/active-context.md").exists(),
    }


def _action(n: dict) -> str:
    if n.get("cmd"):
        return f"run `{n['cmd']}`"
    if n.get("prompt"):
        return f'ask your agent: "{n["prompt"]}"'
    return n.get("how", "")


def render_next(st: dict, brief: bool = False) -> str:
    n = st["next"]
    act = _action(n)
    if brief:
        why = re.split(r"[.;:]", n.get("why") or "")[0].strip()
        why = (why[:1].lower() + why[1:]) if why else ""
        return f"Next: {n['say']}" + (f" — {why}" if why else "") + f" → {act or 'see eos status'}"
    teach = st["teaching"] == "on"
    seen: set[str] = set()

    def g(t: str) -> str:  # teaching: a plain gloss after the first use of each jargon term
        return gloss(t, seen) if teach else t

    mode = st["mode"]
    lines = [
        g(
            f"You are here: {mode}{' (' + MODE_PLAIN[mode] + ')' if teach and mode in MODE_PLAIN else ''}"
            f" · phase {st['phase_title']}"
        )
        + (
            f" ({sum(p['state'] == 'done' for p in st['phases'])}/{len(st['phases'])} phases done)"
            if st["phases"]
            else ""
        ),
        f"Next: {g(n['say'])}",
    ]
    if n.get("why"):
        lines.append(f"Why: {g(n['why'])}")
    tools = st.get("tools") or []
    chat = "Cline or Cursor" if "cline" in tools else "your AI chat (Cursor, Claude Code...)"
    if teach and n.get("prompt"):
        lines += [f"How: paste this sentence into {chat}:", f'  "{n["prompt"]}"']
    elif teach and n.get("cmd"):
        parts = [x.strip() for x in n["cmd"].split("&&")]
        lines.append(
            "How: type this in the terminal and press Enter:"
            if len(parts) == 1
            else "How: type these in the terminal, one at a time (Enter after each):"
        )
        lines += [f"  {x}" for x in parts]
        lines.append(f"  (or ask {chat} to run it for you)")
    elif act:
        lines.append(f"How: {act}")
    if n.get("bmad"):
        lines.append(f"  or with BMAD: run the `{n['bmad']}` skill (`bmad-help` shows BMAD's own next step)")
    if teach:
        if n.get("pack"):
            lines.append(f"Guide: your agent follows eos's '{n['pack']}' instructions (a pack) for this step.")
        if n.get("explain"):
            lines.append(f"Learn the idea: `eos explain {n['explain']}`")
    for nt in st.get("notes", []):
        lines.append(f"Note: {nt['say']} (when convenient: {nt['cmd']})")
    more = len(st["blockers"]) + len(st["in_progress"]) - 1
    if more > 0:
        lines.append(f"(+{more} more item(s) waiting: `eos status`)")
    return "\n".join(lines)


def render_status(st: dict) -> str:
    sym = {"done": "✓", "current": "▶", "todo": "·", "skipped": "–"}
    lines = [
        (
            f"Mode: {st['mode']}   shape: {st['topology'] or '-'}   gates: {st['gates_mode']}   teaching: {st['teaching']}"
            if st["teaching"] != "on"
            else f"Mode: {st['mode']} ({MODE_PLAIN.get(st['mode'], '-')})   shape: {st['topology'] or '-'}"
            f" ({TOPOLOGY_PLAIN.get(st['topology'] or '', 'how the code is laid out')})   gates: {st['gates_mode']}"
            f" ({GATES_PLAIN.get(st['gates_mode'], '-')})   teaching: on"
        ),
        (
            f"Git: {st['git']['branch'] or '-'} ({st['git']['dirty']} uncommitted)   stories: {st['stories']['open']} open / "
            f"{st['stories']['done']} done   improvement plan: {st['plan']['open']} open / {st['plan']['done']} done"
        ),
        "",
        "Phases:",
    ]
    for p in st["phases"]:
        miss = f"  missing: {', '.join(p['missing'])}" if p["state"] in ("current", "todo") and p["missing"] else ""
        lines.append(f"  {sym.get(p['state'], '?')} {p['title']:<34}{miss if p['state'] == 'current' else ''}")
    if st["gates"]:
        lines += ["", "Gates: " + "; ".join(st["gates"])]
    if st["blockers"]:
        lines += ["", "Blockers:"] + [f"  - {b['say']}" for b in st["blockers"]]
    if st["in_progress"]:
        lines += ["", "In progress:"] + [f"  - {w['say']}" for w in st["in_progress"]]
    lines += ["", render_next(st)]
    return "\n".join(lines)


def _nav_root(args: argparse.Namespace) -> tuple[Path, dict] | None:
    root = Path(args.dir).resolve()
    m = load_manifest(root)
    if not m:
        print(
            "Not set up yet. New product: `eos start`. Existing code: `eos adopt`. (Run `eos explain phases` to learn more.)"
        )
        return None
    return root, m


def cmd_status(args: argparse.Namespace) -> int:
    r = _nav_root(args)
    if not r:
        return 2 if args.strict else 0
    st = nav_status(*r)
    print(json.dumps(st, indent=2, default=str) if args.json else render_status(st))
    return 1 if args.strict and (st["blockers"] or st["phase"]) else 0


def cmd_next(args: argparse.Namespace) -> int:
    r = _nav_root(args)
    if not r:
        return 0
    root, m = r
    if args.unskip:
        m.pop("nav_skip", None)
        save_manifest(root, m)
        print("all skipped steps are back")
    st = nav_status(root, m)
    if args.skip:
        label = st["next"].get("_label")
        if not label:
            print("only a phase step can be skipped (blockers and work in progress can't): " + st["next"]["say"])
            return 1
        m["nav_skip"] = sorted(set(m.get("nav_skip") or []) | {label})
        save_manifest(root, m)
        log_event(root, "nav-skip", step=label)
        print(f"skipped: {label} (`eos next --unskip` brings it back)")
        st = nav_status(root, m)
    st["next"].pop("_label", None)
    if args.json:
        print(json.dumps({k: st[k] for k in ("mode", "phase", "next", "blockers")}, indent=2, default=str))
    else:
        print(render_next(st, brief=args.brief))
    return 0


def load_concepts(home: Path | None, root: Path) -> dict[str, str]:
    for p in (root / ".eos/concepts.md", (home or root) / "core/concepts.md"):
        if p.exists():
            out: dict[str, str] = {}
            for block in re.split(r"(?m)^## ", read(p))[1:]:
                head, _, body = block.partition("\n")
                for key in head.split("|"):
                    out[key.strip().lower()] = f"## {head.split('|')[0].strip()}\n{body.strip()}"
            return out
    return {}


def cmd_explain(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    home = find_eos_home()
    concepts = load_concepts(home, root)
    topic = (args.topic or "").lower().strip()
    if not topic or topic not in concepts:
        if topic:  # a pack? show its intent instead
            packs = load_project_packs(root)[0] if load_manifest(root) else (load_home_packs(home)[0] if home else {})
            pk = packs.get(topic)
            if pk:
                print(f"## {pk.meta.get('title', topic)}\n{pk.description}\nUse it when: {pk.meta.get('when', '-')}")
                print(f"Full text: .eos/packs/phases/{topic}.md")
                return 0
            print(f"No explanation for '{topic}'.")
        print("Topics: " + ", ".join(sorted({v.splitlines()[0][3:] for v in concepts.values()})))
        return 1 if topic else 0
    print(concepts[topic])
    return 0


# ----------------------------------------------------------------------------- multi-repo workspace
# A parent folder with several git repos side by side. Each repo keeps its own eos install, rules and checks;
# the workspace adds a map (AGENTS.md), contracts, owners, an editor workspace file and cross-repo change plans.
WS_FILE = "eos-workspace.json"
WS_CORE = """## How to work in this workspace
- This folder holds separate git repos (table below). Inside `<repo>/`, that repo's `AGENTS.md`, rules and checks apply: read it first, run its checks there, commit and branch per repo.
- Repos couple only through the contracts listed below. Never import another repo's internals or copy code across repos without a plan.
- A change that spans repos: `python3 .eos/bin/eos.py workspace change "<title>"` writes a plan in `docs/changes/` (repos, merge order, contract version). Contracts change provider-first and additive; the same branch name in every repo; PRs link each other.
- Where things stand across repos: `python3 .eos/bin/eos.py workspace status`."""


def find_child_repos(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / ".git").exists() and not p.name.startswith("."))


def looks_like_workspace(root: Path) -> bool:
    return not (root / ".git").exists() and len(find_child_repos(root)) >= 2


def load_ws(root: Path) -> dict:
    p = root / WS_FILE
    try:
        return json.loads(read(p)) if p.exists() else {}
    except ValueError:
        raise SystemExit(f"{WS_FILE} is not valid JSON") from None


def find_ws_root(start: Path) -> Path | None:
    for d in [start, *start.parents][:4]:
        if (d / WS_FILE).exists():
            return d
    return None


def guess_role(repo: Path, stacks: dict, contracts: list[str]) -> str:
    ids = set(stacks)
    name = repo.name.lower()
    code = [r for r in iter_files(repo, 4) if r.suffix in CODE_EXT]
    if contracts and len(code) <= 2 or any(k in name for k in ("contract", "proto", "schema", "api-spec")):
        return "contracts"
    if any(k in name for k in ("infra", "terraform", "deploy", "ops", "platform")) or any(repo.glob("*.tf")):
        return "infrastructure"
    if ids & {"react-native-expo", "flutter"}:
        return "mobile app"
    if "nextjs" in ids or any(k in name for k in ("web", "frontend", "ui", "site")):
        return "web frontend"
    if any(k in name for k in ("lib", "shared", "common", "sdk", "kit")):
        return "shared library"
    if (
        ids & {"python-fastapi", "python-flask"}
        or contracts
        or any(k in name for k in ("api", "service", "svc", "backend"))
    ):
        return "API service"
    return "application"


def _consumers(root: Path, provider: str, repos: list[str]) -> list[str]:
    """Cheap guess: which sibling repos mention the provider's name in their config/compose/env files."""
    out = []
    names = (
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        ".env.example",
        "docker-compose.yml",
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "pubspec.yaml",
    )
    rx = re.compile(rf"(?<![\w-]){re.escape(provider)}(?![\w-])", re.IGNORECASE)
    for r in repos:
        if r == provider:
            continue
        for rel in iter_files(root / r, 2):
            if rel.name in names and rx.search(read(root / r / rel)):
                out.append(r)
                break
    return out


def ws_scan(home: Path | None, root: Path, ws: dict) -> dict:
    packs = load_home_packs(home)[1] if home else {}
    known = {r["name"]: r for r in ws.get("repos", [])}
    names = sorted(set(find_child_repos(root)) | {n for n, r in known.items() if (root / r.get("path", n)).is_dir()})
    repos = []
    for n in names:
        r = dict(known.get(n, {}))
        path = root / r.get("path", n)
        m = load_manifest(path)
        stacks = m.get("stacks") or (detect_stacks(path, packs)[0] if packs else {})
        contracts = find_contracts(path)
        r.setdefault("name", n)
        r.setdefault("path", n)
        r["stacks"] = sorted(stacks)
        r["contracts"] = contracts
        r.setdefault("role", guess_role(path, stacks, contracts))
        r.setdefault("owner", "<owner>")
        r["eos"] = bool(m)
        remote = git_out(path, "remote", "get-url", "origin")
        if remote:
            r["remote"] = re.sub(r"://[^/@]+@", "://", remote)  # never store credentials embedded in URLs
        repos.append(r)
    for r in repos:
        if r["contracts"] and "consumers" not in r:
            r["consumers"] = _consumers(root, r["name"], [x["name"] for x in repos])
    return {
        "name": ws.get("name") or root.name,
        "version": 1,
        "repos": repos,
        "created": ws.get("created") or dt.datetime.now().astimezone().date().isoformat(),
    }


def ws_blocks(ws: dict) -> dict[str, str]:
    rows = []
    for r in ws["repos"]:
        on = "yes" if r.get("eos") else "no: `eos adopt " + r["name"] + "`"
        rows.append(
            f"| `{r['name']}/` | {r['role']} | {', '.join(r['stacks']) or '-'} | {r.get('owner', '-')} | {on} |"
        )
    repos = "## Repos\n| Repo | Role | Stacks | Owner | eos |\n|---|---|---|---|---|\n" + "\n".join(rows)
    lines = ["## Contracts (the only allowed coupling)"]
    for r in ws["repos"]:
        for c in r["contracts"]:
            cons = ", ".join(r.get("consumers", [])) or "<consumers?>"
            lines.append(f"- `{r['name']}/{c}`: provided by {r['name']}; used by {cons}")
    if len(lines) == 1:
        lines.append("- none found (OpenAPI / AsyncAPI / .proto). Add them, or list how repos talk to each other.")
    return {"ws-core": WS_CORE, "ws-repos": repos, "ws-contracts": "\n".join(lines)}


def ws_code_workspace(ws: dict) -> str:
    """Workspace folder first: Cline loads rules/skills only from the first folder; Cursor/VS Code show all."""
    folders = [{"name": f"{ws['name']} (workspace)", "path": "."}] + [{"path": r["path"]} for r in ws["repos"]]
    return json.dumps({"folders": folders, "settings": {}}, indent=2) + "\n"


def ws_cline_rules(root: Path, ws: dict) -> dict[str, str]:
    """Cline reads .clinerules only from the primary folder, so each repo gets a path-scoped pointer here, plus
    its own path rules re-prefixed with the repo dir (activated only when files in that repo are in play)."""
    out = {}
    for r in ws["repos"]:
        p = r["path"].rstrip("/")
        out[f".clinerules/ws-{dir_slug(r['name'])}.md"] = (
            f'---\npaths:\n  - "{p}/**"\n---\n# Working in `{p}/` ({r["role"]})\n'
            f"Read `{p}/AGENTS.md` first: its rules and checks apply to every file under `{p}/`. "
            f"Run commands from `{p}/`.\n"
        )
        for f in sorted((root / p / ".clinerules").glob("eos-*.md")) if (root / p / ".clinerules").is_dir() else []:
            txt = read(f)
            fm = re.match(r"(?s)^---\n(.*?)\n---\n", txt)
            if not fm:
                continue
            globs = re.findall(r'(?m)^\s+-\s+"([^"]+)"', fm.group(1))
            if not globs:
                continue
            body = txt[fm.end() :]
            pref = "\n".join(f'  - "{p}/{g}"' for g in globs)
            out[f".clinerules/{dir_slug(r['name'])}-{f.name}"] = f"---\npaths:\n{pref}\n---\n" + body
    return out


def ws_sync(home: Path | None, root: Path, dry: bool = False, quiet: bool = False) -> dict:
    ws = ws_scan(home, root, load_ws(root))
    mp = root / ".eos/workspace-files.json"  # not .eos/manifest.json: the workspace folder is not a project
    try:
        m = json.loads(read(mp)) if mp.exists() else {"files": {}}
    except ValueError:
        m = {"files": {}}
    w = Writer(root, m, dry, False)
    if not dry:
        write(root / WS_FILE, json.dumps(ws, indent=2) + "\n")
    tpl = (
        read(home / "core/templates/workspace/AGENTS.md").replace("{{NAME}}", ws["name"])
        if home
        else f"# {ws['name']} workspace\n"
    )
    w.blocks("AGENTS.md", ws_blocks(ws), tpl)
    w.blocks("CLAUDE.md", {"claude-import": "@AGENTS.md"}, "")
    w.managed(f"{dir_slug(ws['name'])}.code-workspace", ws_code_workspace(ws))
    write_project_cli(w)
    want = ws_cline_rules(root, ws)
    for rel, txt in want.items():
        w.managed(rel, txt)
    for rel in [k for k in list(w.files) if k.startswith(".clinerules/") and k not in want]:
        p = root / rel
        if p.exists() and sha(read(p)) == w.files[rel] and not dry:
            p.unlink()
            del w.files[rel]
            w._log("removed", rel)
    if home:
        w.seed("docs/changes/0000-template.md", read(home / "core/templates/workspace/change.md"))
    w.append_lines(".gitignore", ["# engineering-os workspace", ".eos/state/", "*.eos-new"])
    if not dry:
        write(mp, json.dumps(m, indent=2, sort_keys=True) + "\n")
    linked = []
    for r in ws["repos"]:
        rp_ = root / r["path"]
        rm = load_manifest(rp_)
        if not rm:
            continue
        block = {
            "self": r["name"],
            "name": ws["name"],
            "role": r["role"],
            "repos": [{"name": x["name"], "role": x["role"]} for x in ws["repos"]],
        }
        if rm.get("workspace") != block and not dry:
            rm["workspace"] = block
            save_manifest(rp_, rm)
            _resync(rp_)
        linked.append(r["name"])
    if not quiet:
        for s, rel in w.report:
            if s not in ("unchanged", "kept"):
                print(f"  {s:<14} {rel}")
        print(f"  repos : {', '.join(r['name'] + ' (' + r['role'] + ')' for r in ws['repos'])}")
        print(f"  linked: {', '.join(linked) or 'none'} (their AGENTS.md now has a workspace block)")
        todo = [r["name"] for r in ws["repos"] if not r.get("eos")]
        if todo:
            print(f"  not on eos yet: {', '.join(todo)} -> `eos adopt <repo>` for each, then `eos workspace sync`")
    return ws


def ws_status(root: Path, ws: dict, prs: bool = False) -> list[str]:
    lines = [
        f"Workspace {ws['name']}: {len(ws['repos'])} repos",
        f"  {'repo':<16}{'branch':<22}{'dirty':>6}  {'↑/↓':<7} eos",
    ]
    gh = shutil.which("gh") if prs else None
    for r in ws["repos"]:
        p = root / r["path"]
        br = git_out(p, "symbolic-ref", "--short", "-q", "HEAD") or "(detached)"
        dirty = len([ln for ln in git_out(p, "status", "--porcelain").splitlines() if ln.strip()])
        ab = git_out(p, "rev-list", "--left-right", "--count", "HEAD...@{u}").split()
        abs_ = f"{ab[0]}/{ab[1]}" if len(ab) == 2 else "-"
        m = load_manifest(p)
        eos_s = "not installed"
        if m:
            st = nav_status(p, m)
            eos_s = f"{st['mode']} · {st['phase_title']}" + (" · BLOCKED" if st["blockers"] else "")
        lines.append(f"  {r['name']:<16}{br[:21]:<22}{dirty:>6}  {abs_:<7} {eos_s}")
        if gh:
            code, out = run(
                [gh, "pr", "list", "--author", "@me", "--json", "number,title,headRefName", "--limit", "5"],
                cwd=p,
                timeout=30,
            )
            if code == 0:
                try:
                    for pr in json.loads(out or "[]"):
                        lines.append(f"      PR #{pr['number']} {pr['headRefName']}: {pr['title'][:60]}")
                except ValueError:
                    pass
    if prs and not gh:
        lines.append("  (--prs needs the GitHub CLI `gh`, logged in)")
    changes = [p for p in _globs(root, "docs/changes/[0-9]*.md") if not p.name.startswith("0000")]
    open_c = [p for p in changes if not re.search(r"\*\*Status:\*\*\s*(merged|rolled back)", read(p))]
    if open_c:
        lines.append("  open cross-repo changes: " + ", ".join(p.stem for p in open_c[:5]))
    return lines


def cmd_workspace(args: argparse.Namespace) -> int:
    home = find_eos_home()
    root = Path(args.dir).resolve()
    act = args.action
    if act in ("init", "sync", "add") and not home:
        eprint("needs the engineering-os repo (set EOS_HOME)")
        return 2
    if act == "init":
        if (root / ".git").exists() and not args.force:
            eprint(
                f"{root} is a git repo. A workspace is the parent folder of several repos (use --force if this repo is the workspace itself)."
            )
            return 2
        if not find_child_repos(root):
            print("  no git repos found in this folder yet: add them with `eos workspace add <path-or-git-url>`")
        if args.name and not (root / WS_FILE).exists() and not args.dry_run:
            write(root / WS_FILE, json.dumps({"name": args.name, "repos": []}) + "\n")
        print(f"eos workspace init -> {root}{' (DRY RUN)' if args.dry_run else ''}")
        ws = ws_sync(home, root, args.dry_run)
        print(f"  open the folder (or {dir_slug(ws['name'])}.code-workspace) in your editor so agents see both levels.")
        print(
            "  next: fill 'Workspace specifics' in AGENTS.md and owners/roles in eos-workspace.json, then `eos workspace sync`."
        )
        return 0
    if act == "add":
        if not args.target:
            eprint("usage: eos workspace add <path-or-git-url> [--role ROLE] [--owner OWNER]")
            return 2
        tgt = args.target
        if re.match(r"^(https?://|git@|ssh://)", tgt):
            dest = root / re.sub(r"\.git$", "", tgt.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1])
            if not dest.exists():
                code, out = run(["git", "clone", tgt, str(dest)], cwd=root, timeout=600)
                if code:
                    eprint(out[-500:])
                    return 1
        else:
            dest = (root / tgt).resolve()
        if not (dest / ".git").exists():
            eprint(f"{dest} is not a git repo")
            return 2
        try:
            rel = dest.relative_to(root).as_posix()
        except ValueError:
            eprint("the repo must be inside the workspace folder (move or clone it there)")
            return 2
        ws = load_ws(root) or {"name": root.name, "repos": []}
        ws["repos"] = [r for r in ws.get("repos", []) if r["name"] != dest.name]
        entry = {"name": dest.name, "path": rel}
        if args.role:
            entry["role"] = args.role
        if args.owner:
            entry["owner"] = args.owner
        ws["repos"].append(entry)
        write(root / WS_FILE, json.dumps(ws, indent=2) + "\n")
        ws_sync(home, root)
        return 0
    if act == "sync":
        ws_sync(home, root, args.dry_run)
        return 0
    ws = load_ws(root)
    if not ws:
        wr = find_ws_root(root.parent)
        if wr:
            root, ws = wr, load_ws(wr)
        else:
            eprint(f"no {WS_FILE} here: run `eos workspace init` in the parent folder of your repos")
            return 2
    if act == "status":
        print("\n".join(ws_status(root, ws, args.prs)))
        return 0
    if act == "change":
        if not args.target:
            eprint('usage: eos workspace change "<title>" [--repos a,b,c]')
            return 2
        folder = root / "docs/changes"
        n = _next_number(folder)
        slug = _slug(args.target)
        picked = [r for r in ws["repos"] if not args.repos or r["name"] in args.repos.split(",")]
        picked.sort(key=lambda r: (0 if r["role"] == "contracts" else 1 if r.get("contracts") else 2, r["name"]))
        rows = "\n".join(f"| {i} | {r['name']} | | | planned |" for i, r in enumerate(picked, 1))
        tpl = home / "core/templates/workspace/change.md" if home else folder / "0000-template.md"
        body = read(tpl).replace("NNNN", f"{n:04d}").replace("<title>", args.target).replace("<rows>", rows)
        body = body.replace("<branch>", f"change/{n:04d}-{slug}").replace(
            "YYYY-MM-DD", dt.datetime.now().astimezone().date().isoformat()
        )
        dest = folder / f"{n:04d}-{slug}.md"
        if not args.dry_run:
            write(dest, body)
        print(
            f"created {dest.relative_to(root).as_posix()}: same branch `change/{n:04d}-{slug}` in {', '.join(r['name'] for r in picked)}"
        )
        print("  merge order = table order (contracts/providers first). Each PR links this plan and the other PRs.")
        return 0
    return 2


# ----------------------------------------------------------------------------- start (first-time wizard)
START_CHOICES = [
    ("greenfield", "A new product or idea (little or no code yet)"),
    ("brownfield", "Existing code I'm taking over or improving"),
    ("rewrite", "Replacing or re-platforming an existing system (refonte)"),
    ("maintain", "A live, mature product I keep running"),
    ("workspace", "Several repos that belong together (multi-repo workspace)"),
]


def _ask(ask, q: str, default: str, choices: list[str] | None = None) -> str:
    while True:
        raw = ask(f"{q} [{default}]: ").strip()
        if not raw:
            return default
        if not choices:
            return raw
        if raw.isdigit() and 0 < int(raw) <= len(choices):
            return choices[int(raw) - 1]
        hit = [c for c in choices if c.startswith(raw.lower())]
        if len(hit) == 1:
            return hit[0]
        print(f"  choose 1-{len(choices)} or one of: {', '.join(choices)}")


def cmd_start(args: argparse.Namespace, ask=input) -> int:
    """Guided first run: what are you doing? -> the right command (init / adopt / migration / workspace) -> next."""
    home = find_eos_home()
    if not home:
        eprint("needs the engineering-os repo (set EOS_HOME)")
        return 2
    root = Path(args.dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if load_manifest(root):
        print(
            "eos is already set up here. To change the project questions (type, money, personal data...):"
            " `eos update --reconfigure`.\nWhere you are and what to do next:\n"
        )
        return cmd_next(argparse.Namespace(dir=str(root), json=False, brief=False))
    if looks_like_workspace(root) or (root / WS_FILE).exists():
        guess, why = "workspace", f"this folder holds several git repos ({', '.join(find_child_repos(root)[:4])})"
    else:
        guess, ev = detect_mode(root)
        why = "; ".join(ev)
    interactive = not args.yes and sys.stdin.isatty()
    print("Welcome to engineering-os. A few questions; Enter keeps the suggestion in brackets.\n")
    print(f"What are you working on?  (suggested from the folder: {why})")
    keys = [k for k, _ in START_CHOICES]
    for i, (k, label) in enumerate(START_CHOICES, 1):
        print(f"  {i}. {label}")
    choice = args.kind or (_ask(ask, "Choice", guess, keys) if interactive else guess)
    choice = norm_mode(choice) if choice != "workspace" else choice
    name = args.name or (_ask(ask, "Project name", root.name) if interactive else root.name)
    tools_default = ",".join(load_global_state().get("tools", DEFAULT_TOOLS))
    tools = args.tools or (
        _ask(ask, "Your AI tools (cursor, cline, claude, codex)", tools_default) if interactive else tools_default
    )
    teach = args.teach or "on"  # a default, not a question: `eos teach off` any time
    print()
    explain_topic = {
        "greenfield": "phases",
        "brownfield": "brownfield",
        "rewrite": "strangler-fig",
        "maintain": "slo",
        "workspace": "workspace",
    }[choice]
    if choice == "workspace":
        print("-> eos workspace init: a map of your repos for agents; each repo keeps its own rules.")
        rc = cmd_workspace(
            argparse.Namespace(
                dir=str(root),
                action="init",
                target=None,
                name=name,
                role=None,
                owner=None,
                repos=None,
                prs=False,
                force=False,
                dry_run=False,
            )
        )
        print(
            f"\nLearn the idea: `eos explain {explain_topic}`. Next: `eos adopt <repo>` in each repo that isn't on eos yet."
        )
        return rc
    common = {
        "dir": str(root),
        "dry_run": False,
        "force": False,
        "verbose": False,
        "no_ci": False,
        "no_precommit": False,
        "bmad": False,
        "strict": False,
        "tools": tools,
        "stacks": "auto",
        "name": name,
        "pm": None,
        "python": None,
        "profile": args.profile,
        "answers": None,
        "interactive": interactive,
        "yes": not interactive,
        "mode": choice,
        "topology": None,
        "teach": teach,
    }
    if choice in ("brownfield", "maintain") and repo_facts(root)["code_files"] >= 5:
        print("-> eos adopt: scan, report and install without overwriting anything of yours.")
        rc = cmd_adopt(argparse.Namespace(**common, scan_only=False, report_only=False, no_baseline=args.no_baseline))
    else:
        print(f"-> eos init (mode {choice})")
        rc = cmd_init(argparse.Namespace(**common, adopt=False))
        if choice == "rewrite" and rc == 0:
            title = args.migration or (
                _ask(ask, "Name of the migration (e.g. 'Move billing to the new API')", "main migration")
                if interactive
                else "main migration"
            )
            new_migration(
                argparse.Namespace(title=title, dry_run=False),
                home,
                root,
                dt.datetime.now().astimezone().date().isoformat(),
            )
    if rc == 0:
        print("\n" + "-" * 60)
        print(render_next(nav_status(root, load_manifest(root))))
        print(
            f"\nNew to this? `eos explain {explain_topic}` · Any time: `eos status`, `eos next`, `eos explain <topic>`."
        )
    return rc


# ----------------------------------------------------------------------------- lanes (ceremony scaled to risk)
# One question decides how much process a change needs: how bad is it if this is wrong, and can it be undone?
# `eos lane` answers it from the diff (paths, size, content) and branch name; `eos verify` runs the matching checks.
LANES = ("trivial", "standard", "risky", "one-way-door")
LANE_RULES = {
    "trivial": "no plan, no new tests; changed-file hooks only; self-merge after CI",
    "standard": "act, then `eos verify` (changed-file hooks + related tests + quarantine expiry); plan only for "
    "multi-session work",
    "risky": "5-line plan (approved first if money, auth or security behaviour changes); `eos verify` runs the full "
    "check + changed-line coverage; CI mutation-tests money/auth code; a human reviews the flagged files line by line",
    "one-way-door": "as risky, plus a human approves the written plan before merge, an ADR, and a rollback or "
    "forward-fix plan",
    "spike": "throwaway: no tests, plans or memory; secrets and force-push guards stay on; never merged "
    "(CI rejects spike/* PRs)",
    "hotfix": "fix + regression test, `eos verify`, PR labelled hotfix, merge on green CI; review happens after "
    "(`eos hotfix done` writes the note)",
}
TRIVIAL_GLOBS = (
    "**/*.md",
    "**/*.mdx",
    "**/*.txt",
    "**/*.rst",
    "docs/**",
    "**/locales/**",
    "**/locale/**",
    "**/i18n/**",
    "**/*.po",
    "**/*.svg",
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg",
    "**/*.webp",
    "**/*.ico",
    "LICENSE*",
    "memory/**",
)
NOT_TRIVIAL_RX = _lazy_rx(  # agent instructions and product prompts change behaviour even though they are Markdown
    r"(^|/)(AGENTS\.md|CLAUDE\.md|\.eos/|\.cursor/|\.clinerules|\.claude/|\.agents/|\.cline/|prompts/)|\.prompt\.md$"
)
RISK_WORDS = {
    "pay", "payment", "payments", "payout", "payouts", "billing", "invoice", "invoices", "checkout", "wallet",
    "ledger", "money", "refund", "refunds", "subscription", "subscriptions", "stripe", "momo", "mpesa", "auth",
    "authn", "authz", "login", "logout", "signup", "session", "sessions", "password", "passwords", "oauth", "oidc",
    "saml", "jwt", "otp", "mfa", "permission", "permissions", "rbac", "acl", "crypto", "secret", "secrets", "kms",
    "security",
}  # fmt: skip
RISK_PATH_RX = _lazy_rx(
    r"(^|/)(migrations?|alembic|terraform|infra|k8s|kubernetes|helm|charts)/|\.(tf|sql)$|(^|/)Dockerfile[^/]*$|"
    r"(^|/)(docker-)?compose[^/]*\.ya?ml$|(^|/)\.github/workflows/|(^|/)\.gitlab-ci\.yml$|(^|/)prisma/schema\.prisma$|"
    r"(^|/)\.pre-commit-config\.yaml$|(^|/)\.eos/(protected\.txt|config\.json)$|"
    r"(^|/)packs/vendor/|"  # vendored third-party text is read by agents: a human reviews every change
    r"(^|/)src/main/AndroidManifest\.xml$|(^|/)res/xml/network_security_config\.xml$"  # exported parts, cleartext
)
CONTRACT_RX = _lazy_rx(
    r"(^|/)(openapi|swagger|asyncapi)[^/]*\.(ya?ml|json)$|\.(proto|graphql|graphqls)$|\.odcs\.(ya?ml|json)$"
)
MIGRATION_RX = _lazy_rx(r"(^|/)(migrations?|alembic/versions)/|\.sql$")
ONE_WAY_RX = _lazy_rx(
    r"(?i)\bDROP\s+(TABLE|COLUMN|SCHEMA|DATABASE|TYPE)\b|\bRENAME\s+(COLUMN|TO)\b|\bALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE\b|"
    r"\bTRUNCATE\b|\b(op\.)?drop_(column|table)\b|\brename_(column|table)\b|\b(removeColumn|dropTable|renameColumn)\b"
)
LARGE = {"files": 20, "lines": 400}


def _path_words(rel: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", rel)
    return {w.lower() for w in re.split(r"[^A-Za-z0-9]+", spaced) if w}


def lane_base(root: Path, base: str | None = None) -> tuple[str, str]:
    """(ref the change is measured from, its name). Feature branch: merge-base with main. On main: HEAD."""
    cands = [base] if base else ["origin/main", "origin/master", "main", "master"]
    head = git_out(root, "rev-parse", "HEAD")
    for c in cands:
        if c and run(["git", "rev-parse", "-q", "--verify", c + "^{commit}"], cwd=root, timeout=5)[0] == 0:
            mb = git_out(root, "merge-base", c, "HEAD")
            if mb:
                return mb, c
    return (head, "HEAD") if head else ("", "")


def current_branch(root: Path) -> str:
    return git_out(root, "symbolic-ref", "--short", "-q", "HEAD")


def change_diff(root: Path, base: str) -> tuple[dict, dict, list[str]]:
    """Added/removed lines per file from base to the working tree (committed + staged + unstaged + untracked)."""
    if base:
        _, diff = run(["git", "diff", "--no-color", "-U0", "--no-ext-diff", "-M", base], cwd=root, timeout=60)
    else:
        diff = ""
    added, removed, deleted = parse_unified_diff(diff)
    _, untracked = run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, timeout=20)
    for f in untracked.splitlines():
        try:
            added.setdefault(f, []).extend(read(root / f).splitlines())
        except (OSError, UnicodeDecodeError, ValueError):
            added.setdefault(f, [])
        removed.setdefault(f, [])
    return added, removed, deleted


def classify_change(root: Path, base: str | None = None, cfg: dict | None = None, labels: str = "") -> dict:
    cfg = cfg if cfg is not None else _load_cfg(root)
    lc = cfg.get("lanes", {}) if isinstance(cfg.get("lanes"), dict) else {}
    trivial_globs = list(TRIVIAL_GLOBS) + list(lc.get("trivial", []))
    risky_globs = list(lc.get("risky", []))
    words = RISK_WORDS | set(lc.get("risk_words", []))
    large = {**LARGE, **{k: int(v) for k, v in lc.get("large", {}).items()}}
    ref, ref_name = lane_base(root, base)
    added, removed, deleted = change_diff(root, ref)
    files = sorted(set(added) | set(deleted))
    # eos's own generated files (rules, skills, refs), byte-identical to what eos wrote: their names contain
    # words like "security" or "payments", but they are not your money/auth code. Without this every
    # `eos update` or adoption PR was "risky" and listed dozens of eos files for line-by-line review
    # (v0.7.1 evaluation). Gate configs (CI, pre-commit, .eos/config.json) still match RISK_PATH_RX.
    mf = (load_manifest(root) or {}).get("files", {})
    gen = {f for f in files if f in mf and f not in deleted and (root / f).is_file() and sha(read(root / f)) == mf[f]}
    counted = [f for f in files if f not in gen]
    lines = sum(len(added.get(f, [])) + len(removed.get(f, [])) for f in counted)
    reasons: list[str] = []
    review: list[str] = []
    one_way: list[str] = []
    for f in files:
        mine = f not in gen and (words & _path_words(f) or any(re.match(glob_to_regex(g), f) for g in risky_globs))
        if RISK_PATH_RX.search(f) or mine:
            review.append(f)
        if MIGRATION_RX.search(f) and (f in deleted or any(ONE_WAY_RX.search(ln) for ln in added.get(f, []))):
            one_way.append(f"{f}: drops/renames data or deletes a migration")
        if CONTRACT_RX.search(f) and (f in deleted or any(ln.strip() for ln in removed.get(f, []))):
            one_way.append(
                f"{f}: removes lines from a public contract (check with oasdiff/buf breaking/eos data check)"
            )
    trivial = bool(files) and all(
        any(re.match(glob_to_regex(g), f) for g in trivial_globs) and not NOT_TRIVIAL_RX.search(f) for f in files
    )
    # The exemption trusts the manifest's hashes, so a changed manifest is itself reviewed (an agent could otherwise
    # edit a generated file and its hash together).
    mrel = manifest_path(root).relative_to(root).as_posix()
    if gen and mrel in files and mrel not in review:
        review.append(mrel)
    if not files:
        lane, reasons = "trivial", ["no changes"]
    elif one_way:
        lane, reasons = "one-way-door", one_way
    elif review:
        lane = "risky"
        reasons = [f"sensitive paths ({len(review)}): " + ", ".join(review[:5]) + (" …" if len(review) > 5 else "")]
    elif len(counted) > large["files"] or lines > large["lines"]:
        lane, reasons = (
            "risky",
            [f"large change ({len(counted)} files, {lines} lines): split it or review it carefully"],
        )
    elif trivial:
        lane, reasons = "trivial", ["docs, copy or assets only"]
    else:
        lane, reasons = "standard", [f"{len(counted)} file(s), {lines} line(s), no sensitive paths"]
    if gen:
        reasons.append(
            f"{len(gen)} eos-generated file(s) unchanged since eos wrote them (not counted as sensitive or large)"
        )
    detected = lane
    override = ""
    want = os.environ.get("EOS_LANE", "")
    for lb in [x.strip() for x in (labels or os.environ.get("EOS_LABELS", "")).split(",")]:
        if lb.startswith("lane:"):
            want = lb.removeprefix("lane:")
    if want in LANES and want != lane:
        override, lane = f"override: detected {detected}, using {want}", want
    branch = current_branch(root)
    mode = next((k for k in ("spike", "hotfix") if branch.startswith(k + "/")), "")
    return {
        "lane": mode or lane,
        "risk": lane,
        "detected": detected,
        "override": override,
        "reasons": reasons,
        "review": review,
        "files": files,
        "deleted": deleted,
        "lines": lines,
        "base": ref_name,
        "branch": branch,
    }


def render_lane(c: dict) -> str:
    out = [f"Lane: {c['lane']}" + (f" (risk: {c['risk']})" if c["lane"] != c["risk"] else "")]
    out.append("Why: " + "; ".join(c["reasons"]) + (f"  [vs {c['base']}]" if c["base"] else ""))
    out.append("Do: " + LANE_RULES[c["lane"]])
    if c["lane"] in ("spike", "hotfix") and c["risk"] in ("risky", "one-way-door"):
        out.append("Also: " + LANE_RULES[c["risk"]])
    if c["review"]:
        out.append("Human review (line by line): " + ", ".join(c["review"][:10]))
    if c["override"]:
        out.append(c["override"] + " (logged in eos stats)")
    return "\n".join(out)


def cmd_lane(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    c = classify_change(root, args.base, labels=args.labels or "")
    if c["override"]:
        log_event(root, "override", lane=c["lane"], detected=c["detected"])
    if args.json:
        print(json.dumps(c, indent=2))
        return 0
    print(render_lane(c))
    if args.ci:  # CI annotation only; it never blocks except a spike PR (throwaway code must not merge)
        summ = os.environ.get("GITHUB_STEP_SUMMARY")
        if summ:
            with open(summ, "a", encoding="utf-8") as fh:
                fh.write("### eos lane\n\n```\n" + render_lane(c) + "\n```\n")
        head = os.environ.get("GITHUB_HEAD_REF", "") or c["branch"]
        if head.startswith("spike/"):
            print(
                "eos: spike branches are throwaway; rebuild the idea on a normal branch (eos spike done keeps notes)."
            )
            return 1
    return 0


# ----------------------------------------------------------------------------- verify (the one check command)
def _related_py_tests(root: Path, d: str, changed: list[str]) -> list[str]:
    base = root / d if d not in (".", "") else root
    tests: list[str] = []
    stems = set()
    for f in changed:
        p = Path(f)
        if p.suffix != ".py" or not (root / f).exists():
            continue
        if p.name.startswith("test_") or p.stem.endswith("_test"):
            tests.append(f)
        else:
            stems.add(p.stem)
    if stems:
        for t in base.rglob("test_*.py"):
            if any(part in IGNORE_DIRS for part in t.parts):
                continue
            if t.stem.removeprefix("test_") in stems:
                tests.append(t.relative_to(root).as_posix())
    return sorted(set(tests))


IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".eos"}


def _rel_to(d: str, files: list[str]) -> list[str]:
    pre = "" if d in (".", "") else d.rstrip("/") + "/"
    return [f[len(pre) :] for f in files if f.startswith(pre)]


def verify_plan(root: Path, m: dict, c: dict, full: bool) -> list[tuple[str, str, list[str]]]:
    """[(label, cwd, argv)] for this change. Formatters run first (sequentially); the rest run in parallel."""
    plan: list[tuple[str, str, list[str]]] = []
    files = [f for f in c["files"] if (root / f).is_file()]
    if c["lane"] == "spike" and not full:
        return plan
    if files and (root / ".pre-commit-config.yaml").exists() and shutil.which("pre-commit"):
        plan.append(
            (
                f"hooks on {len(files)} changed file(s)",
                ".",
                ["pre-commit", "run", "--color", "never", "--files", *files],
            )
        )
    heavy = full or c["risk"] in ("risky", "one-way-door")
    if c["risk"] == "trivial" and not full:
        return plan
    home_packs = load_project_packs(root)[1]
    pm = m.get("pm", "pnpm")
    full_dirs: set[str] = set()

    def has_full(sid: str) -> bool:
        pk = home_packs.get(sid)
        return bool(pk and pk.meta.get("full_check"))

    stack_items = sorted((m.get("stacks") or {}).items(), key=lambda kv: not has_full(kv[0]))
    for sid, v in stack_items:
        pk = home_packs.get(sid)
        for d in as_dirs(v):
            mine = [f for f in files if _within(f, d)]
            if (not mine and not full) or d in full_dirs:
                continue
            if heavy and pk and pk.meta.get("full_check"):
                full_dirs.add(d)
                cmd = pk.meta["full_check"].replace("{pm}", pm)
                plan.append((f"full check {sid} [{d}]", d, ["cmd", "/c", cmd] if IS_WINDOWS else ["sh", "-c", cmd]))
                continue
            if sid.startswith("python"):
                tests = _rel_to(d, _related_py_tests(root, d, mine))
                if tests:
                    use_uv = shutil.which("uv") and ((root / d / "uv.lock").exists() or (root / "uv.lock").exists())
                    pre = ["uv", "run", "pytest"] if use_uv else [sys.executable, "-m", "pytest"]
                    plan.append((f"related tests {sid} [{d}] ({len(tests)})", d, [*pre, "-q", *tests]))
            elif sid in ("typescript", "nextjs", "react-native-expo"):
                try:
                    pkg = json.loads(read(root / d / "package.json"))
                except (OSError, ValueError):
                    pkg = {}
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                srcs = [f for f in _rel_to(d, mine) if re.search(r"\.(m|c)?[jt]sx?$", f)]
                ex = PM_INFO.get(pm, PM_INFO["pnpm"])["exec"].split()
                if srcs and "vitest" in deps:
                    plan.append((f"related tests {sid} [{d}]", d, [*ex, "vitest", "related", "--run", *srcs]))
                elif srcs and "jest" in deps:
                    plan.append(
                        (
                            f"related tests {sid} [{d}]",
                            d,
                            [*ex, "jest", "--findRelatedTests", "--passWithNoTests", *srcs],
                        )
                    )
    seen, out = set(), []
    for p in plan:  # one stack can be listed under two pack ids (python + python-fastapi): run once
        key = (p[1], tuple(p[2]))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _run_step(root: Path, step: tuple[str, str, list[str]], timeout: int) -> tuple[str, int, str, float]:
    label, d, argv = step
    t = time.time()
    env = dict(os.environ, SKIP="no-commit-to-branch", NO_COLOR="1")
    rc, out = run(argv, cwd=root / d if d not in (".", "") else root, timeout=timeout, env=env)
    if rc != 0 and argv[:2] == ["pre-commit", "run"]:  # formatters fix files and fail once: confirm
        rc, out = run(argv, cwd=root, timeout=timeout, env=env)
    return label, rc, re.sub(r"\x1b\[[0-9;]*m", "", out), time.time() - t


def cmd_verify(args: argparse.Namespace) -> int:
    from concurrent.futures import ThreadPoolExecutor

    root = Path(args.dir).resolve()
    m = load_manifest(root)
    if not m:
        eprint("not an eos project (run `eos start`)")
        return 2
    cfg = _load_cfg(root)
    c = classify_change(root, args.base, cfg)
    print(f"lane: {c['lane']} ({'; '.join(c['reasons'])})")
    plan = verify_plan(root, m, c, args.full)
    if args.dry_run:
        for label, d, argv in plan:
            print(f"  would run [{d}]: {' '.join(argv[:8])}{' …' if len(argv) > 8 else ''}   # {label}")
        return 0
    timeout = int(cfg.get("verify_timeout", 900))
    t0, results = time.time(), []
    first = [p for p in plan if p[2][:2] == ["pre-commit", "run"]]
    rest = [p for p in plan if p not in first]
    for p in first:
        results.append(_run_step(root, p, timeout))
    if rest:
        with ThreadPoolExecutor(max_workers=min(4, len(rest))) as ex:
            results += list(ex.map(lambda p: _run_step(root, p, timeout), rest))
    extra, notes = testing_extras(root, m, c, args.full, args.base)
    results += extra
    extra, ops_notes = ops_extras(root, m, c, args.full)
    results += extra
    notes += ops_notes
    extra, fe_notes = frontend_extras(root, m, c, args.full)
    results += extra
    notes += fe_notes
    extra, de_notes = design_extras(root, m, c, args.full)
    results += extra
    notes += de_notes
    extra, mo_notes = mobile_extras(root, m, c, args.full)
    results += extra
    notes += mo_notes
    extra, llm_notes = llm_extras(root, m, c, args.full, args.base)
    results += extra
    notes += llm_notes
    extra, data_notes = data_extras(root, m, c, args.full, args.base)
    results += extra
    notes += data_notes
    if c["risk"] in ("risky", "one-way-door") or args.full:
        ref, _ = lane_base(root, args.base)
        added, removed, deleted = change_diff(root, ref)
        fs = integrity_findings(added, removed, deleted)
        results.append(("test integrity", 1 if fs else 0, "\n".join(fs), 0.0))
    if not results:
        print("  nothing to run for this lane" + (" (spike)" if c["lane"] == "spike" else ""))
    ok = True
    for label, rc, out, secs in results:
        mark = "pass" if rc == 0 else ("timeout" if rc == 124 else "FAIL")
        print(f"  {label} → {mark} ({secs:.1f}s)")
        if rc not in (0, 124):
            ok = False
            print("    " + cap_output(root, out).replace("\n", "\n    "))
    if c["risk"] == "standard" and not any(lb.startswith(("related", "full")) for lb, *_ in results):
        print("  (no related tests found for the changed files; the full suite runs at push and in CI)")
    for n in notes:
        print("  " + n)
    if c["review"] and c["lane"] != "spike":
        print("  human review needed (line by line): " + ", ".join(c["review"][:10]))
    log_event(root, "verify", lane=c["lane"], ok=ok, ms=int((time.time() - t0) * 1000), steps=len(results))
    print(f"eos verify: {'OK' if ok else 'FAILED'} in {time.time() - t0:.1f}s")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- escape hatches: spike, hotfix
def _git_switch_new(root: Path, branch: str, start: str | None = None) -> tuple[int, str]:
    if run(["git", "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], cwd=root, timeout=5)[0] == 0:
        return run(["git", "switch", branch], cwd=root, timeout=20)
    return run(["git", "switch", "-c", branch, *([start] if start else [])], cwd=root, timeout=20)


def _branch_note(root: Path, kind: str, name: str, base: str) -> str:
    _, log = run(
        ["git", "log", "--reverse", "--format=- %h %ad %s", "--date=format:%H:%M", f"{base}..HEAD"],
        cwd=root,
        timeout=10,
    )
    _, stat = run(["git", "diff", "--stat", base, "HEAD"], cwd=root, timeout=10)
    today = dt.datetime.now().astimezone().date().isoformat()
    if kind == "spike":
        return (
            f"# Spike: {name} ({today})\n\nBranch `spike/{name}` (kept, never merged).\n\n"
            "- Question:\n- Answer:\n- Keep (what to rebuild properly):\n- Throw away:\n\n"
            f"## Commits\n{log.strip() or '- (none)'}\n\n## Files\n```\n{stat.strip()}\n```\n"
        )
    return (
        f"# Hotfix: {name} ({today})\n\nBranch `hotfix/{name}`. Post-hoc review within one working day.\n\n"
        "- [ ] Impact (who, how long):\n- [ ] Root cause:\n- [ ] Regression test added:\n"
        "- [ ] Second person reviewed the diff (required if money, auth or data were touched)\n"
        "- [ ] Follow-ups filed (docs/plans/tech-debt.md or issues):\n\n"
        f"## Timeline (from git)\n{log.strip() or '- (none)'}\n\n## Files\n```\n{stat.strip()}\n```\n"
    )


def cmd_spike_hotfix(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    kind = args.kind
    branch = current_branch(root)
    if args.name == "done":
        if not branch.startswith(kind + "/"):
            eprint(f"not on a {kind}/* branch (current: {branch or 'detached'})")
            return 2
        name = branch.split("/", 1)[1]
        base_ref, _ = lane_base(root)
        folder = "docs/spikes" if kind == "spike" else "docs/incidents"
        today = dt.datetime.now().astimezone().date().isoformat()
        rel = f"{folder}/{today}-{_slug(name)}.md"
        note = _branch_note(root, kind, name, base_ref or "HEAD")
        if not args.dry_run:
            write(root / rel, note)
        log_event(root, kind, action="done", name=name)
        print(f"wrote {rel} (fill the blanks; 2 minutes)")
        if kind == "spike":
            print(
                "Next: switch back (`git switch -`) and rebuild what you keep on a normal branch; the spike branch stays as a reference."
            )
        else:
            print(
                "Next: commit the note on main (or with the PR); ask a second person to review the diff if money, auth or data were touched."
            )
        return 0
    name = _slug(args.name)
    if not name:
        eprint(f"usage: eos {kind} <short-name>   |   eos {kind} done")
        return 2
    start = None
    if kind == "hotfix":
        if not args.no_fetch:  # flaky network: a short timeout, then continue from what we have
            run(["git", "fetch", "-q", "origin"], cwd=root, timeout=int(_load_cfg(root).get("fetch_timeout", 15)))
        start = next(
            (r for r in ("origin/main", "origin/master", "main", "master")
             if run(["git", "rev-parse", "-q", "--verify", r + "^{commit}"], cwd=root, timeout=5)[0] == 0),
            None,
        )  # fmt: skip
    target = f"{kind}/{name}"
    if args.dry_run:
        print(f"would create {target}" + (f" from {start}" if start else ""))
        return 0
    rc, out = _git_switch_new(root, target, start)
    if rc != 0:
        eprint(out.strip())
        eprint("(uncommitted changes? `git stash` first, or commit them)")
        return 1
    log_event(root, kind, action="start", name=name)
    print(f"on {target}" + (f" (from {start})" if start else ""))
    print("Rules: " + LANE_RULES[kind])
    if kind == "spike":
        print(
            "Agents: the stop check is off on spike/* branches; secrets, protected paths and force-push guards stay on."
        )
        print("When done: `eos spike done` writes a short note of what you learned.")
    else:
        print(
            "Steps: fix + regression test → `eos verify` → push → PR with label `hotfix` → merge on green CI → `eos hotfix done`."
        )
    return 0


# ----------------------------------------------------------------------------- self-metrics (eos stats)
EVENTS = ".eos/state/events.jsonl"


def log_event(root: Path, kind: str, **data) -> None:
    """Local, gitignored, append-only. Never fails the caller. Rotates at ~1 MB (keeps the newest half)."""
    try:
        p = root / EVENTS
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": round(time.time(), 1), "k": kind, **data}, separators=(",", ":")) + "\n")
        if p.stat().st_size > 1_000_000:
            lines = p.read_text(encoding="utf-8").splitlines()
            p.write_text("\n".join(lines[len(lines) // 2 :]) + "\n", encoding="utf-8", newline="\n")
    except OSError:
        pass


def _pct(xs: list[float], q: float) -> int:
    if not xs:
        return 0
    xs = sorted(xs)
    return int(xs[min(len(xs) - 1, round(q * (len(xs) - 1)))])


def load_events(root: Path, days: int) -> list[dict]:
    cut = time.time() - days * 86400
    out = []
    try:
        for ln in read(root / EVENTS).splitlines():
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if e.get("t", 0) >= cut:
                out.append(e)
    except OSError:
        pass
    return out


def git_flow_stats(root: Path, days: int) -> dict:
    """Lead time from a branch's first commit to its merge (merge commits only; squash merges can't be seen)."""
    _, merges = run(["git", "log", "--merges", f"--since={days} days ago", "--format=%H %ct %P"], cwd=root, timeout=20)
    leads = []
    for ln in merges.splitlines():
        parts = ln.split()
        if len(parts) < 4:
            continue
        _, ct, p1, p2 = parts[0], int(parts[1]), parts[2], parts[3]
        _, first = run(["git", "log", "--reverse", "--format=%ct", f"{p1}..{p2}"], cwd=root, timeout=10)
        if first.strip():
            leads.append((ct - int(first.split()[0])) / 3600)
    _, commits = run(["git", "log", f"--since={days} days ago", "--no-merges", "--format=%ct"], cwd=root, timeout=20)
    return {"merges": len(leads), "lead_h_median": _pct(leads, 0.5), "lead_h_p90": _pct(leads, 0.9),
            "commits": len(commits.split())}  # fmt: skip


def stats_summary(root: Path, days: int) -> dict:
    ev = load_events(root, days)

    def of(k: str) -> list[dict]:
        return [e for e in ev if e.get("k") == k]

    guard = of("guard")
    asks = [e for e in guard if e.get("d") in ("ask", "deny")]
    reasons: dict[str, int] = {}
    for e in asks:
        r = re.sub(r"^eos guard( blocked)?: ", "", e.get("r", ""))[:70]
        reasons[r] = reasons.get(r, 0) + 1
    stops = of("stop")
    ver = of("verify")
    hooks: dict[str, list[float]] = {}
    for e in of("hook"):
        hooks.setdefault(e.get("id", "?"), []).append(e.get("ms", 0))
    return {
        "days": days,
        "guard": {
            "calls": len(guard),
            "median_ms": _pct([e.get("ms", 0) for e in guard], 0.5),
            "p90_ms": _pct([e.get("ms", 0) for e in guard], 0.9),
            "asks": sum(1 for e in asks if e.get("d") == "ask"),
            "denies": sum(1 for e in asks if e.get("d") == "deny"),
            "top_reasons": sorted(reasons.items(), key=lambda x: -x[1])[:5],
        },
        "stop": {
            "runs": len(stops),
            "blocked": sum(1 for e in stops if not e.get("ok")),
            "gave_up": sum(1 for e in stops if e.get("gave_up")),
            "median_ms": _pct([e.get("ms", 0) for e in stops], 0.5),
            "p90_ms": _pct([e.get("ms", 0) for e in stops], 0.9),
        },
        "verify": {
            lane: {
                "runs": len(xs),
                "failed": sum(1 for e in xs if not e.get("ok")),
                "median_ms": _pct([e.get("ms", 0) for e in xs], 0.5),
            }
            for lane in sorted({e.get("lane", "?") for e in ver})
            for xs in [[e for e in ver if e.get("lane") == lane]]
        },
        "hooks": {k: {"runs": len(v), "median_ms": _pct(v, 0.5), "p90_ms": _pct(v, 0.9)} for k, v in hooks.items()},
        "escapes": {
            "spikes": sum(1 for e in of("spike") if e.get("action") == "start"),
            "hotfixes": sum(1 for e in of("hotfix") if e.get("action") == "start"),
            "hotfix_notes": sum(1 for e in of("hotfix") if e.get("action") == "done"),
            "lane_overrides": len(of("override")),
            "nav_skips": len(of("nav-skip")),
        },
        "git": git_flow_stats(root, days),
    }


def render_stats(s: dict) -> str:
    g, st, esc, gi = s["guard"], s["stop"], s["escapes"], s["git"]
    out = [f"eos stats (last {s['days']} days; local log {EVENTS})", ""]
    out.append(
        f"Agent hooks : {g['calls']} calls, median {g['median_ms']} ms, p90 {g['p90_ms']} ms; "
        f"{g['asks']} approval prompts, {g['denies']} blocks"
    )
    for r, n in g["top_reasons"]:
        out.append(f"   {n:>4} × {r}")
    if st["runs"]:
        out.append(
            f"Stop check  : {st['runs']} runs, median {st['median_ms'] / 1000:.1f}s, p90 {st['p90_ms'] / 1000:.1f}s; "
            f"sent work back {st['blocked']}×, gave up {st['gave_up']}×"
        )
    for lane, v in s["verify"].items():
        out.append(f"Verify {lane:<13}: {v['runs']} runs, {v['failed']} failed, median {v['median_ms'] / 1000:.1f}s")
    for k, v in s["hooks"].items():
        out.append(
            f"Git hook {k:<11}: {v['runs']} runs, median {v['median_ms'] / 1000:.1f}s, p90 {v['p90_ms'] / 1000:.1f}s"
        )
    out.append(
        f"Escapes     : {esc['spikes']} spikes, {esc['hotfixes']} hotfixes ({esc['hotfix_notes']} review notes), "
        f"{esc['lane_overrides']} lane overrides, {esc['nav_skips']} navigator skips"
    )
    lead = (
        f"median lead time {gi['lead_h_median']} h (p90 {gi['lead_h_p90']} h) over {gi['merges']} merges"
        if gi["merges"]
        else "lead time n/a (no merge commits; squash merges hide it; use your forge's insights)"
    )
    out.append(f"Git         : {gi['commits']} commits; {lead}")
    tips = []
    if g["calls"] and g["asks"] / max(1, g["calls"]) > 0.05:
        tips.append(
            "more than 5% of agent tool calls ask you: check the top reasons; widen push_policy or protected paths if they are noise"
        )
    if st["runs"] and st["p90_ms"] > 60000:
        tips.append("stop check p90 > 60 s: set stop_check to a faster command in .eos/config.json")
    if st["runs"] and st["gave_up"]:
        tips.append(
            "the stop check gave up at least once: read memory/handoff.md; a recurring failure deserves a fix or a lesson"
        )
    for k, v in s["hooks"].items():
        if v["p90_ms"] > 120000:
            tips.append(f"git hook {k} p90 > 2 min: move it to CI or run only affected tests")
    if esc["hotfixes"] > esc["hotfix_notes"]:
        tips.append("a hotfix has no review note yet: `eos hotfix done` on its branch")
    if tips:
        out += ["", "Tune:"] + [f"  - {t}" for t in tips]
    return "\n".join(out)


def cmd_stats(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    s = stats_summary(root, args.days)
    print(json.dumps(s, indent=2) if args.json else render_stats(s))
    return 0


# ----------------------------------------------------------------------------- small hook helpers (pre-commit)
CONVENTIONAL_RX = _lazy_rx(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w./-]+\))?!?: \S|^(Merge|Revert|fixup!|squash!) "
)


def cmd_commit_msg(args: argparse.Namespace) -> int:
    """Conventional commits only when something consumes them (release-please, or conventional_commits: true)."""
    root = Path.cwd()
    cfg = _load_cfg(root)
    want = cfg.get("conventional_commits")
    if want is None:
        want = (root / "release-please-config.json").exists() or (root / ".release-please-manifest.json").exists()
    if not want:
        return 0
    try:
        first = next((ln for ln in read(Path(args.file)).splitlines() if ln.strip() and not ln.startswith("#")), "")
    except OSError:
        return 0
    if CONVENTIONAL_RX.search(first):
        return 0
    eprint(f"commit message must look like 'fix: short summary' (release notes are built from it). Got: {first[:80]!r}")
    return 1


def cmd_hook_run(args: argparse.Namespace) -> int:
    """Run a command inside a dir with the files pre-commit passed (repo-relative -> dir-relative); time it."""
    argv = list(args.cmd)
    if argv and argv[0] == "--":
        argv = argv[1:]
    d = args.cd or "."
    if args.script:  # package.json contract: `<script>:files` lints just the given files when the repo defines it
        files = _rel_to(d, [a for a in argv if a != "--"])
        try:
            scripts = json.loads(read(Path.cwd() / d / "package.json")).get("scripts", {})
        except (OSError, ValueError):
            scripts = {}
        pm = args.pm or "pnpm"
        if f"{args.script}:files" in scripts:
            if not files:
                return 0
            argv = [pm, "run", f"{args.script}:files", *files]
        else:
            argv = [pm, "run", args.script]
    elif args.files_after and "--" in argv:
        i = argv.index("--")
        cmd, files = argv[:i], _rel_to(d, argv[i + 1 :])
        if not files:
            return 0
        argv = cmd + files
    root = Path.cwd()
    t = time.time()
    try:
        rc = subprocess.call(resolve_argv(argv), cwd=root / d if d not in (".", "") else root)
    except FileNotFoundError:
        eprint(f"eos hook: not found: {argv[0] if argv else '?'}")
        rc = 127
    log_event(root, "hook", id=args.id or (argv[0] if argv else "?"), ms=int((time.time() - t) * 1000), rc=rc)
    return rc


# ----------------------------------------------------------------------------- knowledge library (deep refs + vendor)
# Layer 2 of the library: deep reference files in packs/ref/<area>/<topic>.md, read only when the agent does that
# work (a pack's "## Deep references" section points to them; nothing is always-on). Layer 3: vendored third-party
# files in packs/vendor/<source>/ with packs/vendor/PROVENANCE.json. docs/LIBRARY.md explains the design.
LIB_BUDGET = {"ref_max": 3000, "ref_target": 2500}  # tokens per ref file (4 chars/token estimate)
REF_KEYS = ("id", "title", "area", "read_when", "verified", "revisit_days", "sources")
REF_SECTIONS = ("## Decision guide", "## Anti-patterns", "## Checks", "## Sources")
VENDOR_SCAN_EXT = (".md", ".txt", ".mdc", ".json", ".yaml", ".yml", ".py", ".sh", ".js", ".ts", ".csv", ".tsv")
VENDOR_KINDS = ("knowledge", "code")  # code: never agent context or pointed to; runs only via `eos studio run`
VENDOR_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"}
INJECTION_RULES = (
    (
        "override",
        (
            r"(?i)\b(ignore|disregard|forget)\b[^\n]{0,30}\b(previous|prior|above|earlier|system|all)\b[^\n]{0,20}"
            r"\b(instructions?|rules?|prompts?|guidelines)\b"
        ),
    ),
    ("persona", r"(?i)\byou are now\b|\bdeveloper mode\b|\bjailbreak"),
    ("remote-exec", r"(?i)\b(curl|wget|iwr|irm)\b[^\n|]{0,200}\|\s*(sudo\s+)?(ba|z|da)?sh\b|\biex\s*\("),
    (
        "exfiltration",
        (
            r"(?i)\b(send|post|upload|exfiltrat\w*|transmit|forward)\b[^\n]{0,60}"
            r"\b(secrets?|tokens?|api[ _-]?keys?|passwords?|credentials?|\.env|ssh keys?)\b[^\n]{0,40}\b(to|https?://)"
        ),
    ),
    ("hidden-chars", "[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]"),
    ("hidden-comment", r"(?is)<!--(?:(?!-->).){0,500}?\b(ignore|must|always|never|run|execute|you)\b(?:(?!-->).)*-->"),
    ("base64-blob", r"[A-Za-z0-9+/]{160,}={0,2}"),
    ("remote-script", r"(?i)https?://[^\s)\"'`]+/[^\s)\"'`/]+\.(sh|ps1|bash)(?=[\s)\"'`]|$)"),
    # Instructions loaded at run time from an unpinned URL bypass review: what was approved is not what runs
    # (seen in a third-party skill: "Fetch fresh guidelines before each review", stage 7).
    (
        "remote-instructions",
        (
            r"(?i)\b(fetch|retrieve|download|load|pull|get)\b[^\n]{0,30}\b(fresh|latest|current|updated|newest|live)\b"
            r"[^\n]{0,30}\b(guidelines?|instructions?|rules?|prompts?)\b"
        ),
    ),
)


def scan_injection(text: str) -> list[str]:
    """Patterns that have no business in reference text an agent will read. A hit blocks until a human looks."""
    out = []
    for name, rx in INJECTION_RULES:
        for m in re.finditer(rx, text):
            line = text.count("\n", 0, m.start()) + 1
            snippet = m.group(0).replace("\n", " ")[:80]
            out.append(f"{name} (line {line}): {snippet!r}")
    return out


REF_ID_RX = _lazy_rx(r"`((?:vendor:[a-z0-9-]+/[^`\s]+)|(?:[a-z0-9-]+/[a-z0-9-]+))`")


def deep_refs_of(pk: Pack) -> list[str]:
    """Ref ids a pack points to: the backticked ids in its '## Deep references' section (one place, no frontmatter
    copy, so a pointer costs ~5 tokens). Example: `architecture/caching` -> .eos/packs/ref/architecture/caching.md."""
    sec = re.search(r"(?ms)^## Deep references[^\n]*\n(.*?)(?=^## |\Z)", pk.body)
    out: list[str] = []
    for rid in REF_ID_RX.findall(sec.group(1) if sec else ""):
        if rid not in out:
            out.append(rid)
    return out


def _ref_section(body: str, head: str) -> str:
    m = re.search(rf"(?ms)^{re.escape(head)}[^\n]*\n(.*?)(?=^## |\Z)", body)
    return m.group(1) if m else ""


def _lint_attribution(src: str, meta: dict, body: str) -> list[str]:
    """Refs that adapt licensed text (e.g. CC BY 4.0 guidelines) list it in `adapted_from` and credit it in
    `## Attribution`: every adapted URL, a licence link, and a 'Changes:' note (CC BY requires all three)."""
    adapted = meta.get("adapted_from")
    if adapted is None:
        return []
    if not isinstance(adapted, list) or not adapted:
        return [f"{src}: adapted_from must be a non-empty list of https URLs"]
    out: list[str] = []
    att = _ref_section(body, "## Attribution")
    if not att.strip():
        return [f"{src}: adapted_from is set but there is no '## Attribution' section"]
    srcs = meta.get("sources", [])
    for u in adapted:
        if not str(u).startswith("https://"):
            out.append(f"{src}: adapted_from {u!r} must be an https URL")
        elif u not in srcs:
            out.append(f"{src}: adapted_from {u} must also be in sources")
        elif str(u) not in att:
            out.append(f"{src}: adapted source {u} is not credited under '## Attribution'")
    if not re.search(r"https://creativecommons\.org/licenses/|https://opensource\.org/licenses?/", att):
        out.append(f"{src}: '## Attribution' needs a link to the licence")
    if "Changes:" not in att:
        out.append(f"{src}: '## Attribution' must say what was changed ('Changes: ...')")
    return out


def lint_library(home: Path, today: dt.date | None = None, strict: bool = False) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for every ref file and every pack pointer. Offline; runs in eos's own CI."""
    today = today or dt.datetime.now().astimezone().date()
    errs: list[str] = []
    warns: list[str] = []
    refs: dict[str, Path] = {}
    for p in sorted((home / "packs/ref").rglob("*.md")):
        rel = p.relative_to(home / "packs/ref").as_posix()
        if "/" not in rel:  # pre-v0.7 top-level refs: kept as they are, linted for size and injection only
            text = read(p)
            refs[rel[:-3]] = p
            if tokens(text) > LIB_BUDGET["ref_max"] + 1000:
                warns.append(f"packs/ref/{rel}: ~{tokens(text)} tokens (legacy ref; split when next edited)")
            errs += [f"packs/ref/{rel}: {h}" for h in scan_injection(text)]
            continue
        src = f"packs/ref/{rel}"
        text = read(p)
        try:
            meta, body = parse_frontmatter(text)
        except ValueError as exc:
            errs.append(f"{src}: invalid frontmatter: {exc}")
            continue
        rid = rel[:-3]
        refs[rid] = p
        for k in REF_KEYS:
            if k not in meta:
                errs.append(f"{src}: missing frontmatter key '{k}'")
        if meta.get("id") and meta["id"] != rid:
            errs.append(f"{src}: id '{meta['id']}' must be '{rid}' (its path)")
        if meta.get("area") and meta["area"] != rid.split("/")[0]:
            errs.append(f"{src}: area '{meta['area']}' must match its folder '{rid.split('/')[0]}'")
        t = tokens(text)
        if t > LIB_BUDGET["ref_max"]:
            errs.append(f"{src}: ~{t} tokens > {LIB_BUDGET['ref_max']} (split it; target ≤ {LIB_BUDGET['ref_target']})")
        for s in REF_SECTIONS:
            if not re.search(rf"(?m)^{re.escape(s)}", body):
                errs.append(f"{src}: missing section '{s}…'")
        srcs = meta.get("sources", [])
        if not isinstance(srcs, list) or len(srcs) < 2:
            errs.append(f"{src}: needs at least 2 sources")
        else:
            listed = _ref_section(body, "## Sources")
            for u in srcs:
                if not str(u).startswith("https://"):
                    errs.append(f"{src}: source {u!r} must be an https URL")
                elif str(u) not in listed:
                    errs.append(f"{src}: source {u} is not listed under '## Sources'")
        errs += _lint_attribution(src, meta, body)
        try:
            ver = dt.date.fromisoformat(str(meta.get("verified", "")))
            age = (today - ver).days
            if age < 0:
                errs.append(f"{src}: verified date {ver} is in the future")
            elif age > int(meta.get("revisit_days", 180)):
                (errs if strict else warns).append(f"{src}: verified {age} days ago (> revisit_days): re-verify")
        except ValueError:
            errs.append(f"{src}: verified must be an ISO date (YYYY-MM-DD)")
        errs += [f"{src}: {h}" for h in scan_injection(body)]
    phases, stacks = load_home_packs(home)
    pointed: set[str] = set()
    for pk in list(phases.values()) + list(stacks.values()):
        for rid in deep_refs_of(pk):
            pointed.add(rid)
            if rid.startswith("vendor:"):
                sid = rid[7:].split("/", 1)[0]
                vsrcs = _vendor_lock(home)["sources"]
                if sid not in vsrcs:
                    errs.append(f"{pk.src}: '{rid}' points to an unvendored source '{sid}'")
                elif vsrcs[sid].get("kind") == "code":
                    errs.append(f"{pk.src}: '{rid}' points to code source '{sid}': code runs only via `eos studio run`")
                elif vendor_pending(vsrcs[sid]):
                    errs.append(f"{pk.src}: '{rid}' points to '{sid}', which is pending human sign-off")
                elif not (home / "packs/vendor" / rid[7:]).is_file():
                    errs.append(f"{pk.src}: '{rid}' has no file packs/vendor/{rid[7:]}")
            elif rid not in refs:
                errs.append(f"{pk.src}: deep reference '{rid}' has no file packs/ref/{rid}.md")
    for rid in refs:
        if "/" in rid and rid not in pointed:
            errs.append(f"packs/ref/{rid}.md: no pack points to it (add it to a pack's refs, or delete it)")
    return errs, warns


def library_index(home: Path) -> str:
    lines = ["# Deep reference index (read one line, then only the file you need)", ""]
    for p in sorted((home / "packs/ref").rglob("*/*.md")):
        try:
            meta, _ = parse_frontmatter(read(p))
        except ValueError:
            continue
        rid = p.relative_to(home / "packs/ref").as_posix()[:-3]
        lines.append(f"- `{rid}`: {meta.get('read_when', '')} → `.eos/packs/ref/{rid}.md`")
    return "\n".join(lines) + "\n"


def library_index_for(home: Path, packs: list[Pack]) -> str:
    """The index, cut down to the refs the project's selected packs point to (the only ones installed)."""
    want = {r for pk in packs for r in deep_refs_of(pk) if not r.startswith("vendor:")}
    lines = [ln for ln in library_index(home).splitlines() if not ln.startswith("- `") or ln.split("`")[1] in want]
    return "\n".join(lines) + "\n"


def refs_to_install(home: Path, packs: list[Pack]) -> dict[str, Path]:
    """{project path: source}. Legacy top-level refs always; area refs and vendored files only when a selected
    pack points to them (keeps projects lean). A vendored file travels with its source's licence file."""
    out = {f".eos/packs/ref/{p.name}": p for p in sorted((home / "packs/ref").glob("*.md"))}
    lock = None
    for r in sorted({r for pk in packs for r in deep_refs_of(pk)}):
        if r.startswith("vendor:"):
            lock = lock or _vendor_lock(home)
            sid = r[7:].split("/", 1)[0]
            s = lock["sources"].get(sid)
            if s and vendor_pending(s):
                continue
            for rel in (r[7:], f"{sid}/{(s or {}).get('license_file', 'LICENSE')}"):
                if s and (home / "packs/vendor" / rel).is_file():
                    out[f".eos/packs/vendor/{rel}"] = home / "packs/vendor" / rel
        elif (home / "packs/ref" / f"{r}.md").exists():
            out[f".eos/packs/ref/{r}.md"] = home / "packs/ref" / f"{r}.md"
    return out


def cmd_library(args: argparse.Namespace) -> int:
    home = Path(args.home).resolve() if getattr(args, "home", None) else find_eos_home()
    if home is None:
        eprint("engineering-os checkout not found (set EOS_HOME)")
        return 2
    if args.action == "lint":
        errs, warns = lint_library(home, strict=args.strict)
        for w in warns:
            print("  warn: " + w)
        for e in errs:
            print("  error: " + e)
        n = len(list((home / "packs/ref").rglob("*.md")))
        print(f"eos library lint: {'OK' if not errs else 'FAILED'} ({n} ref files, {len(warns)} warnings)")
        if getattr(args, "and_vendor", False):
            verrs, vwarns = vendor_check(home, _vendor_lock(home))
            for w in vwarns:
                print("  warn: " + w)
            for e in verrs:
                print("  error: " + e)
            print(f"eos vendor check: {'OK' if not verrs else 'FAILED'}")
            errs += verrs
        return 0 if not errs else 1
    if args.action == "index":
        print(library_index(home), end="")
        return 0
    if args.action == "eval":
        return library_eval(home, Path(args.target), Path(args.responses) if args.responses else None, args.json)
    # list
    rows = []
    for p in sorted((home / "packs/ref").rglob("*.md")):
        rel = p.relative_to(home / "packs/ref").as_posix()
        try:
            meta, _ = parse_frontmatter(read(p))
        except ValueError:
            meta = {}
        rows.append((rel, tokens(read(p)), str(meta.get("verified", "-")), len(meta.get("sources", []) or [])))
    print(f"{'ref':<52} {'tokens':>7} {'verified':>11} {'sources':>8}")
    for r in rows:
        print(f"{r[0]:<52} {r[1]:>7} {r[2]:>11} {r[3]:>8}")
    print(f"{len(rows)} files, ~{sum(r[1] for r in rows)} tokens in total (none always-on)")
    return 0


def library_eval(home: Path, target: Path, responses: Path | None, as_json: bool) -> int:
    """Token cost and guidance coverage, with vs without the deep refs, for small eval tasks (tests/evals/*.json).

    Coverage = share of rubric items whose evidence pattern appears in the text. Without --responses it is
    measured on the context the agent would load (pack only vs pack + expected refs): a proxy for "is the
    guidance available". With --responses DIR (files <task-id>.<label>.md written by real agent runs, label =
    'base' or 'lib'), the same rubric scores the agent's actual answers.
    """
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]
    phases, stacks = load_home_packs(home)
    allp = {**phases, **stacks}
    results = []
    for f in files:
        spec = json.loads(read(f))
        for task in spec["tasks"]:
            pk = allp[task["pack"]]
            base = pk.text
            names = task.get("refs", [])
            if isinstance(names, str) or not all((home / "packs/ref" / f"{r}.md").is_file() for r in names):
                raise SystemExit(f"eos library eval: {f.name} task {task.get('id')!r}: refs must list existing refs")
            refs = "".join(read(home / "packs/ref" / f"{r}.md") for r in names)
            rub = task["rubric"]
            if not all(isinstance(r.get("any"), list) and all(isinstance(x, str) for x in r["any"]) for r in rub):
                raise SystemExit(
                    f"eos library eval: {f.name} task {task.get('id')!r}: each rubric `any` must be a list"
                )

            def cov(text: str, rub: list = rub) -> list[str]:
                return [r["id"] for r in rub if any(re.search(x, text, re.IGNORECASE) for x in r["any"])]

            row = {
                "task": task["id"],
                "tokens_base": tokens(base),
                "tokens_lib": tokens(base + refs),
                "coverage_base": len(cov(base)) / len(rub),
                "coverage_lib": len(cov(base + refs)) / len(rub),
                "missing_lib": [r["id"] for r in rub if r["id"] not in cov(base + refs)],
            }
            if responses:
                for label in ("base", "lib"):
                    rp = responses / f"{task['id']}.{label}.md"
                    if rp.exists():
                        row[f"answer_{label}"] = len(cov(read(rp))) / len(rub)
            results.append(row)
    if as_json:
        print(json.dumps(results, indent=1))
        return 0
    print(f"{'task':<34} {'tok base':>8} {'tok +lib':>8} {'cov base':>8} {'cov +lib':>8}")
    for r in results:
        print(
            f"{r['task']:<34} {r['tokens_base']:>8} {r['tokens_lib']:>8} "
            f"{r['coverage_base']:>8.0%} {r['coverage_lib']:>8.0%}"
            + (f"   answers: base {r.get('answer_base', 0):.0%}, lib {r.get('answer_lib', 0):.0%}" if responses else "")
        )
    if results:
        n = len(results)
        print(
            f"{'mean':<34} {sum(r['tokens_base'] for r in results) // n:>8} "
            f"{sum(r['tokens_lib'] for r in results) // n:>8} "
            f"{sum(r['coverage_base'] for r in results) / n:>8.0%} {sum(r['coverage_lib'] for r in results) / n:>8.0%}"
        )
    return 0


# vendor: third-party files pinned to a commit, licence-checked, scanned, with provenance
def _vendor_lock(home: Path) -> dict:
    p = home / "packs/vendor/PROVENANCE.json"
    return json.loads(read(p)) if p.exists() else {"version": 1, "sources": {}}


def _vendor_save(home: Path, lock: dict) -> None:
    write(home / "packs/vendor/PROVENANCE.json", json.dumps(lock, indent=1, sort_keys=True) + "\n")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _vendor_dest(rel: str) -> str:
    """Dot-folders are renamed (.claude/skills -> dot-claude/skills): agent harnesses auto-discover skills and
    rules in folders like .claude, .cursor and .agents, which would load quarantined text without sign-off."""
    return "/".join("dot-" + c[1:] if c.startswith(".") and c not in (".", "..") else c for c in rel.split("/"))


def _vendor_fetch(repo: str, ref: str, paths: list[str], license_file: str, dest: Path) -> tuple[str, list[str]]:
    """Clone `repo` at `ref` into a temp dir and copy `paths` (+ the licence file) to dest. Returns (sha, files)."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / "src"
        rc, out = run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo, str(t)], timeout=300)
        if rc != 0:
            raise SystemExit(f"git clone failed: {out.strip()[-300:]}")
        rc, out = run(["git", "-c", "advice.detachedHead=false", "checkout", "--quiet", ref], cwd=t, timeout=60)
        if rc != 0:
            raise SystemExit(f"cannot check out {ref!r}: {out.strip()[-300:]}")
        sha = run(["git", "rev-parse", "HEAD"], cwd=t)[1].strip()
        if dest.exists():
            shutil.rmtree(dest)
        files: list[str] = []
        for rel in [*paths, license_file]:
            src = t / rel
            if not src.exists():
                raise SystemExit(f"{rel} not found in {repo}@{sha[:12]}")
            for f in [src] if src.is_file() else sorted(x for x in src.rglob("*") if x.is_file()):
                r = _vendor_dest(f.relative_to(t).as_posix())
                (dest / r).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest / r)
                files.append(r)
        return sha, sorted(set(files))


def cmd_vendor(args: argparse.Namespace) -> int:
    home = Path(args.home).resolve() if getattr(args, "home", None) else find_eos_home()
    if home is None:
        eprint("engineering-os checkout not found (set EOS_HOME)")
        return 2
    lock = _vendor_lock(home)
    srcs = lock["sources"]
    if args.action in ("add", "update"):
        sid = args.id
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid or ""):
            eprint("vendor id: lowercase letters, digits and dashes (e.g. anthropic-frontend-design)")
            return 2
        old = srcs.get(sid)
        if args.action == "update" and not old:
            eprint(f"{sid} is not vendored yet: use `eos vendor add`")
            return 2
        if args.action == "add" and old:
            eprint(f"{sid} is already vendored: use `eos vendor update {sid} --ref <commit>`")
            return 2
        repo = args.repo or (old or {}).get("repo")
        paths = args.path or (old or {}).get("paths", [])
        lic = args.license or (old or {}).get("license")
        lic_file = args.license_file or (old or {}).get("license_file", "LICENSE")
        kind = args.kind or (old or {}).get("kind", "knowledge")
        if not (repo and args.ref and paths and lic):
            eprint("needs --repo, --ref (commit or tag), --path (one or more) and --license (SPDX id)")
            return 2
        if lic not in VENDOR_LICENSES:
            eprint(
                f"licence {lic!r} is not on the allow-list {sorted(VENDOR_LICENSES)} (docs/LIBRARY.md): link it instead"
            )
            return 1
        dest = home / "packs/vendor" / sid
        sha, files = _vendor_fetch(repo, args.ref, paths, lic_file, dest)
        findings = []
        for r in files:
            if r.endswith(VENDOR_SCAN_EXT):
                findings += [f"{r}: {h}" for h in scan_injection(read(dest / r))]
        if findings and not args.accept_findings and not args.hold:
            shutil.rmtree(dest, ignore_errors=True)
            if old:  # put the reviewed version back
                _vendor_fetch(old["repo"], old["commit"], old["paths"], old["license_file"], dest)
            eprint("injection scan found text that needs a human look (nothing was vendored):")
            for h in findings:
                eprint("  " + h)
            eprint(
                "A human decides: re-run with --hold to keep it quarantined for review (never installed), or a human"
            )
            eprint("runs it with --accept-findings '<why it is safe>'.")
            return 1
        changed = sorted(f for f in files if (old or {}).get("files", {}).get(f) != _sha256(dest / f))
        srcs[sid] = {
            "repo": repo,
            "commit": sha,
            "ref": args.ref,
            "paths": paths,
            "license": lic,
            "license_file": lic_file,
            "kind": kind,
            "files": {f: _sha256(dest / f) for f in files},
            "tokens": {f: tokens(read(dest / f)) for f in files if f.endswith(".md")},
            "fetched": dt.datetime.now().astimezone().date().isoformat(),
            "scan": {"findings": findings, "accepted": args.accept_findings or ""},
            "attribution": f"{repo} at commit {sha}, licensed {lic} (see {lic_file}); copied unmodified"
            + ("; dot-folders renamed dot-*" if any("dot-" in f for f in files) else ""),
            "status": "pending-human-sign-off",
            "reviewed_by": "",
            "review_note": "",
        }
        _vendor_save(home, lock)
        print(f"vendored {sid} @ {sha[:12]} ({len(files)} files; changed: {', '.join(changed) or 'none'})")
        print("status: pending human sign-off; never installed into projects or pointed to until then.")
        if kind == "code":
            print("kind: code: never loaded as agent context; runs only inside the sandbox (`eos studio run`)")
        print(f"next (a human): read packs/vendor/{sid}/, then `eos vendor review {sid} --by <name> --note ...`")
        return 0
    if args.action == "review":
        if args.id not in srcs:
            eprint(f"{args.id} is not vendored")
            return 2
        if not args.by:
            eprint("--by <name> is required")
            return 2
        src = srcs[args.id]
        if src.get("scan", {}).get("findings") and not (src["scan"].get("accepted") or args.accept_findings):
            eprint(
                f"{args.id} has injection-scan findings: the reviewer must say why they are safe (--accept-findings)"
            )
            return 1
        if args.accept_findings:
            src["scan"]["accepted"] = args.accept_findings
        src.update(
            reviewed_by=args.by,
            review_note=args.note or "",
            reviewed=dt.datetime.now().astimezone().date().isoformat(),
            status="signed-off",
        )
        _vendor_save(home, lock)
        print(f"{args.id}: review recorded")
        return 0
    if args.action == "check":
        errs, warns = vendor_check(home, lock, args.max_age_days, strict=args.strict)
        for w in warns:
            print("  warn: " + w)
        for e in errs:
            print("  error: " + e)
        print(f"eos vendor check: {'OK' if not errs else 'FAILED'} ({len(srcs)} sources)")
        return 0 if not errs else 1
    for sid, s in sorted(srcs.items()):
        tok = sum(s.get("tokens", {}).values())
        st = "pending sign-off" if vendor_pending(s) else f"signed off by {s['reviewed_by']}"
        print(
            f"{sid:<30} {s['commit'][:12]} {s['license']:<14} {s.get('kind', 'knowledge'):<9} {len(s['files'])} files"
            f" ~{tok} tokens  {st}  {s['repo']}"
        )
    if not srcs:
        print("nothing vendored yet (docs/research/v0.7-external-sources.md lists the candidates)")
    return 0


def vendor_pending(s: dict) -> bool:
    """Not yet usable: no human sign-off, or scan findings nobody accepted. Pending sources are never installed."""
    return not s.get("reviewed_by") or bool(s.get("scan", {}).get("findings") and not s["scan"].get("accepted"))


def vendor_check(home: Path, lock: dict, max_age_days: int = 365, strict: bool = False) -> tuple[list[str], list[str]]:
    """Integrity problems are errors. A source still awaiting human sign-off is a warning (it is quarantined:
    never installed or pointed to), or an error with strict=True (use before a release)."""
    errs: list[str] = []
    warns: list[str] = []
    for sid, s in sorted(lock.get("sources", {}).items()):
        d = home / "packs/vendor" / sid
        if s.get("license") not in VENDOR_LICENSES:
            errs.append(f"{sid}: licence {s.get('license')!r} not allowed")
        if s.get("kind", "knowledge") not in VENDOR_KINDS:
            errs.append(f"{sid}: kind {s.get('kind')!r} must be one of {', '.join(VENDOR_KINDS)}")
        if not re.fullmatch(r"[0-9a-f]{40}", s.get("commit", "")):
            errs.append(f"{sid}: commit must be a full 40-character SHA")
        if not (d / s.get("license_file", "LICENSE")).exists():
            errs.append(f"{sid}: licence file {s.get('license_file')} missing")
        for f, h in s.get("files", {}).items():
            p = d / f
            if not p.exists():
                errs.append(f"{sid}: {f} missing")
            elif _sha256(p) != h:
                errs.append(f"{sid}: {f} changed since it was vendored (edit upstream or re-vendor; never in place)")
        on_disk = {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()} if d.exists() else set()
        for extra in sorted(on_disk - set(s.get("files", {}))):
            errs.append(f"{sid}: {extra} is not in PROVENANCE.json")
        if vendor_pending(s):
            why = []
            if s.get("scan", {}).get("findings") and not s["scan"].get("accepted"):
                why.append(f"{len(s['scan']['findings'])} injection-scan findings to judge")
            if not s.get("reviewed_by"):
                why.append("no human review recorded")
            msg = f"{sid}: pending human sign-off ({'; '.join(why)}): `eos vendor review {sid} --by <name> --note ...`"
            (errs if strict else warns).append(msg)
        try:
            age = (dt.datetime.now().astimezone().date() - dt.date.fromisoformat(s.get("fetched", ""))).days
            if age > max_age_days:
                warns.append(f"{sid}: fetched {age} days ago; check upstream for fixes (`eos vendor update`)")
        except ValueError:
            errs.append(f"{sid}: fetched date missing")
    return errs, warns


# ----------------------------------------------------------------------------- check / budget
def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    manifest = load_manifest(root)
    if not manifest:
        eprint("no .eos/manifest.json: not an eos project")
        return 2
    phases, stacks = load_project_packs(root)
    errs: list[str] = []
    for pk in list(phases.values()) + list(stacks.values()):
        errs += pk.validate()
    agents = read(root / "AGENTS.md") if (root / "AGENTS.md").exists() else ""
    core_blocks = "".join(
        re.findall(
            r"<!-- eos:(?:core|stack|map):begin -->.*?<!-- eos:(?:core|stack|map):end -->", agents, flags=re.DOTALL
        )
    )
    if tokens(core_blocks) > BUDGET["core"]:
        errs.append(f"AGENTS.md eos blocks ~{tokens(core_blocks)} tokens > {BUDGET['core']}")
    if tokens(agents) > BUDGET["agents_md"]:
        errs.append(f"AGENTS.md ~{tokens(agents)} tokens > {BUDGET['agents_md']} (move detail into docs/ or a pack)")
    errs += skill_desc_errors(phases)
    for f, limit in MEMORY_CAPS:
        p = root / f
        if p.exists():
            n = len([ln for ln in read(p).splitlines() if ln.strip()])
            if n > limit:
                hint = "move older lines to memory/archive/" if "progress" in f else "summarise or automate (eos-retro)"
                errs.append(f"{f}: {n} non-empty lines > {limit}; {hint}")
    d = drift(root, _project_cfg(root, manifest), phases, stacks, read(root / ".eos/packs/core.md"))
    pin_errs, pin_warns = workflow_pin_problems(root, manifest)
    errs += pin_errs
    if (root / QUARANTINE_FILE).exists():  # expired or unowned flaky-test quarantines fail CI
        try:
            qp, _ = quarantine_problems(
                json.loads(read(root / QUARANTINE_FILE)), int(testing_cfg(root)["quarantine_max_days"])
            )
        except ValueError as exc:
            qp = [f"invalid JSON ({exc})"]
        errs += [f"{QUARANTINE_FILE}: {x}" for x in qp]
    ocfg = ops_cfg(root)
    if has_ops_files(root, ocfg):  # SLO schema, alerts without runbooks, expired feature flags fail CI
        oe, ow = ops_problems(root, ocfg)
        errs += oe
        pin_warns += ow
    ie, iw, isum = i18n_problems(root)  # translation catalogs complete and consistent (when present)
    if isum != "no translation catalogs found" or ie:
        errs += ie
        pin_warns += iw
    if has_design_files(root):  # DTCG token schema + contrast of token pairs; generic-look lint as warnings
        dres = design_problems(root)
        errs += dres["errors"]
        dw = dres["warnings"]
        pin_warns += dw[:10] + ([f"…{len(dw) - 10} more design warnings (`eos design check`)"] if len(dw) > 10 else [])
    if has_mobile_files(root):  # MASVS manifest/app-config checks (backup, cleartext, debuggable, exported, ATS)
        mres = mobile_problems(root)
        errs += mres["errors"]
        pin_warns += mres["warnings"]
    if has_llm_files(root):  # prompt files: frontmatter, declared inputs, untrusted inputs delimited, no secrets
        lres = llm_problems(root)
        errs += lres["errors"]
        pin_warns += lres["warnings"]
    if has_data_files(root):  # ODCS data contracts + committed notebooks (outputs stripped, no secrets)
        dares = data_problems(root)
        errs += dares["errors"]
        dw = dares["warnings"]
        pin_warns += dw[:10] + ([f"…{len(dw) - 10} more data warnings (`eos data check`)"] if len(dw) > 10 else [])
    for w in pin_warns:
        print("  warn: " + w)
    for e in errs:
        print("  error: " + e)
    ok = not errs and not d
    try:  # read by `eos status` / `eos next` (gitignored)
        summary = (errs + d)[0] if (errs or d) else "ok"
        write(
            root / ".eos/state/last-gates.json", json.dumps({"ok": ok, "summary": summary, "time": time.time()}) + "\n"
        )
    except OSError:
        pass
    print(
        f"eos check: {'OK' if ok else 'FAILED'} (AGENTS.md ~{tokens(agents)} tokens; "
        f"{len(phases)} phase + {len(stacks)} stack packs)"
    )
    return 0 if ok else 1


def skill_desc_errors(phases: dict) -> list[str]:
    """Skill names + descriptions are listed to the model on every request, so their total is capped."""
    t = tokens("".join(p.description for p in phases.values() if p.mode in ("intent", "both")))
    return [f"skill descriptions total ~{t} tokens > {BUDGET['skill_descs']}"] if t > BUDGET["skill_descs"] else []


def cmd_budget(args: argparse.Namespace) -> int:
    home = find_eos_home()
    root = Path(args.dir).resolve() if args.dir else Path.cwd()
    profile: str | None = None
    prof_name = ""
    if root and load_manifest(root):
        phases, stacks = load_project_packs(root)
        core = read(root / ".eos/packs/core.md")
    elif home:
        phases, stacks = load_home_packs(home)
        core = read(home / "core/AGENTS.core.md")
        profile = read(profile_file(home))
        prof_name = profile_file(home).relative_to(home).as_posix()
    else:
        eprint("nothing to measure (run inside the eos repo or pass a project dir)")
        return 2
    errs: list[str] = []
    print(f"{'file':<50} {'~tokens':>8} {'budget':>7} {'rule':>6}")
    for pk in list(phases.values()) + list(stacks.values()):
        lim = BUDGET.get(pk.kind, BUDGET["phase"])
        t = tokens(pk.text)
        r = tokens(rule_slice(pk)) if pk.mode in ("files", "both") else 0
        print(f"{pk.src:<50} {t:>8} {lim:>7} {r or '-':>6}{'  OVER' if t > lim else ''}")
        errs += pk.validate()
    errs += skill_desc_errors(phases)
    agents = root / "AGENTS.md" if profile is None else None
    if agents is not None and agents.exists():
        text = read(agents)
        core_t = tokens("".join(re.findall(r"<!-- eos:\w+:begin -->.*?<!-- eos:\w+:end -->", text, re.DOTALL)))
        label = "AGENTS.md eos blocks (this project)"
        total = tokens(text)
        print(
            f"{'AGENTS.md whole file':<50} {total:>8} {BUDGET['agents_md']:>7}{'  OVER' if total > BUDGET['agents_md'] else ''}"
        )
        if total > BUDGET["agents_md"]:
            errs.append(f"AGENTS.md ~{total} > {BUDGET['agents_md']}")
    else:
        two = list(stacks.values())[:2]
        blocks = render_agents_blocks(core, list(phases.values()), two, {}, "pnpm", list(TOOLS_ALL))
        core_t = tokens("\n".join(blocks.values()))
        label = "AGENTS.md eos blocks (all phases + 2 stacks)"
    print(f"{label:<50} {core_t:>8} {BUDGET['core']:>7}")
    if core_t > BUDGET["core"]:
        errs.append(f"AGENTS.md eos blocks ~{core_t} > {BUDGET['core']}")
    pt = 0
    if profile is not None:
        pt = tokens(profile)
        print(f"{prof_name:<50} {pt:>8} {BUDGET['profile']:>7}")
        if pt > BUDGET["profile"]:
            errs.append(f"{prof_name} over budget")
    desc_t = tokens("".join(p.description for p in phases.values() if p.mode in ("intent", "both")))
    print(f"{'skill descriptions (listed every request)':<50} {desc_t:>8}")
    print(f"{'session start (AGENTS.md eos blocks + profile + skill list)':<50} {core_t + pt + desc_t:>8}")
    ph = sorted(tokens(rule_slice(p)) for p in phases.values() if p.mode in ("files", "both")) or [0]
    st = sorted(tokens(s.text) for s in stacks.values()) or [0]
    typical = core_t + pt + desc_t + st[-1] + sum(ph[-2:])
    print(f"while editing ≈ session start + largest stack pack + 2 largest path rules ≈ {typical} tokens")
    for e in errs:
        print("  error: " + e)
    return 1 if errs else 0


# ----------------------------------------------------------------------------- guard (agent hooks)
# Defence in depth for agents: these rules do not replace OS permissions, branch protection or review.
SECRET_PATTERNS = [
    r"(^|/)\.env$",
    r"(^|/)\.env\.(?!example$|sample$|template$|dist$)[^/]+$",
    r"\.pem$",
    r"\.key$",
    r"\.p12$",
    r"\.pfx$",
    r"\.jks$",
    r"\.keystore$",
    r"(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$",
    r"(^|/)\.?secrets?/",
    r"(^|/)secrets\.env$",
    r"credentials[^/]*\.json$",
    r"service[-_]?account[^/]*\.json$",
    r"(^|/)\.netrc$",
    r"(^|/)\.pgpass$",
    r"(^|/)\.npmrc$",
    r"(^|/)\.pypirc$",
    r"(^|/)\.aws/credentials$",
    r"(^|/)\.kube/config$",
]
SHELL_DENY = [
    (r"--no-verify\b|(^|\s)SKIP=\S+|PRE_COMMIT_ALLOW_NO_CONFIG|HUSKY=0", "bypasses git hooks or checks"),
    (r"\bgit\s+push\b[^;&|]*\s(--force(?!-with-lease)\b|-f\b)", "force push"),
    (r"\bgit\s+config\b[^;&|]*core\.hooksPath", "changes the git hooks path"),
    (r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(-[a-zA-Z]+\s+)*(/|~|\$HOME|\*|\.)(\s|$)", "recursive delete of root/home/cwd"),
    (r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "pipes a download into a shell"),
    (r"\bchmod\s+-R\s+0?777\b", "world-writable permissions"),
    (r"(^|[;&|]\s*)(printenv|env)\s*($|[|>;&])|\becho\s+[^;&|]*\$\{?\w*(KEY|TOKEN|SECRET|PASS)", "prints secrets/env"),
]
SHELL_ASK = [
    (
        r"\bgit\s+(reset\s+--hard|clean\s+-\w*f\w*|rebase|filter-branch|filter-repo)\b",
        "rewrites git history",
    ),
    (
        r"\b(terraform|tofu|terragrunt)\s+(apply|destroy|import|state|taint)\b|\bpulumi\s+(up|destroy)\b",
        "changes infrastructure",
    ),
    (
        (
            r"\bkubectl\s+(apply|create|delete|edit|patch|replace|scale|rollout|exec|drain|cordon)\b|"
            r"\bhelm\s+(install|upgrade|uninstall|rollback)\b"
        ),
        "changes a cluster",
    ),
    (
        r"\b(docker|podman)\s+(push|login)\b|\b(npm|pnpm|yarn|bun)\s+publish\b|\buv\s+publish\b|\btwine\s+upload\b",
        "publishes artefacts",
    ),
    (
        (
            r"\balembic\s+(upgrade|downgrade|stamp)\b|\bprisma\s+(migrate\s+(deploy|reset)|db\s+push)\b|\bartisan\s+migrate\b|"
            r"\bflask\s+db\s+(upgrade|downgrade)\b"
        ),
        "runs DB migrations",
    ),
    (r"(?i)\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b|\bDELETE\s+FROM\b", "destructive SQL"),
    (r"\b(psql|mysql|mongosh|redis-cli)\b", "opens a database client"),
    (r"\bgh\s+(pr\s+merge|release\s+create|repo\s+(delete|edit)|secret|variable|workflow\s+run)\b", "acts on GitHub"),
    (r"(^|[;&|]\s*)(ssh|scp|rsync|sudo)\s", "remote access or root"),
    (r"(^|[;&|]\s*)(aws|gcloud|az|doctl|flyctl|vercel|netlify|heroku)\s+\S+", "cloud CLI"),
    (r"(?<![\w.-])\.env(\.(?!example\b|sample\b|template\b)[\w-]+)?(?![\w.-])", "touches an .env file"),
]
READ_TOOL_HINTS = ("read", "grep", "glob", "search", "list", "ls", "view", "find", "fetch")
WRITE_TOOL_HINTS = ("write", "edit", "replace", "delete", "create", "apply", "patch", "move", "rename")
PATH_KEYS = (
    "file_path",
    "path",
    "target_file",
    "filePath",
    "file",
    "notebook_path",
    "target_notebook",
    "relative_path",
)
SHELL_TOOLS = ("bash", "shell", "execute_command", "run_terminal_cmd", "terminal", "powershell")


def _project_root_for_guard() -> Path:
    if SELF.parent.name == "bin" and SELF.parent.parent.name == ".eos":
        return SELF.parent.parent.parent
    for k in ("CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR"):
        if os.environ.get(k):
            return Path(os.environ[k])
    return Path.cwd()


def _load_cfg(root: Path) -> dict:
    try:
        return json.loads(read(root / ".eos/config.json"))
    except (OSError, ValueError):
        return {}


def glob_to_regex(g: str) -> str:
    i, out = 0, ""
    while i < len(g):
        if g.startswith("**/", i):
            out, i = out + r"(?:.*/)?", i + 3
        elif g.startswith("**", i):
            out, i = out + ".*", i + 2
        else:
            out += {"*": "[^/]*", "?": "[^/]"}.get(g[i], re.escape(g[i]))
            i += 1
    return "^" + out + "$"


def protected_match(root: Path, rel: str) -> str | None:
    """gitignore-style: later lines win; '!' un-protects; 'tracked:' protects only committed files."""
    try:
        lines = read(root / ".eos/protected.txt").splitlines()
    except OSError:
        return None
    hit = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        neg = line.startswith("!")
        line = line.lstrip("!")
        tracked_only = line.startswith("tracked:")
        pat = line.removeprefix("tracked:")
        if re.match(glob_to_regex(pat), rel):
            if neg:
                hit = None
            elif tracked_only:
                code, _ = run(["git", "ls-files", "--error-unmatch", rel], cwd=root, timeout=5)
                hit = pat if code == 0 else hit
            else:
                hit = pat
    return hit


def _collect(obj, keys, acc, depth=0) -> None:
    if depth > 4:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str):
                acc.append(v)
            elif k in keys and isinstance(v, list):
                acc.extend(x for x in v if isinstance(x, str))
            else:
                _collect(v, keys, acc, depth + 1)
    elif isinstance(obj, list):
        for x in obj:
            _collect(x, keys, acc, depth + 1)


def _rel(root: Path, p: str) -> str:
    pp = Path(os.path.expanduser(p))
    if not pp.is_absolute():
        pp = root / pp
    try:
        return pp.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return pp.as_posix()  # outside the project: absolute path


def is_secret_path(rel: str) -> bool:
    return any(re.search(p, rel) for p in SECRET_PATTERNS)


def tree_fingerprint(root: Path) -> str:
    """Changes whenever a file is edited, without reading the whole diff (that cost grows with the change)."""
    _, a = run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, timeout=5)
    parts = [a]
    for ln in a.splitlines()[:500]:
        f = ln[3:].split(" -> ")[-1].strip().strip('"')
        try:
            st = (root / f).stat()
            parts.append(f"{f}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f + ":gone")
    return sha("\n".join(parts))


def loop_guard(root: Path, session: str, command: str, limit: int) -> str | None:
    """Same command on the same code state = a loop. Editing code between runs resets the count."""
    state = root / ".eos/state/loop.json"
    try:
        data = json.loads(read(state))
    except (OSError, ValueError):
        data = {}
    now = time.time()
    data = {k: v for k, v in data.items() if now - v.get("ts", 0) < 6 * 3600}
    key = sha(session + "\0" + re.sub(r"\s+", " ", command.strip()) + "\0" + tree_fingerprint(root))
    entry = data.get(key, {"n": 0})
    entry.update(n=entry["n"] + 1, ts=now)
    data[key] = entry
    try:
        write(state, json.dumps(data))
    except OSError:
        pass
    if entry["n"] > limit:
        return (
            f"eos loop guard: this exact command already ran {entry['n'] - 1}x on unchanged code. "
            "Stop repeating it: change approach, or write memory/handoff.md (eos-handoff) and ask the human."
        )
    return None


# Commands that only read or print text. A segment starting with one of these cannot run what it mentions,
# so `rg "DELETE FROM"` or `git commit -m "fix psql docs"` must not trigger an approval prompt (a false ask
# costs a human round-trip and teaches the agent to avoid searching). They also skip the loop guard:
# re-running `git status` on unchanged code is normal, not a loop.
READ_ONLY_CMDS = {
    "rg",
    "grep",
    "egrep",
    "fgrep",
    "ag",
    "ack",
    "find",
    "fd",
    "ls",
    "tree",
    "cat",
    "bat",
    "head",
    "tail",
    "less",
    "more",
    "wc",
    "sort",
    "uniq",
    "cut",
    "diff",
    "echo",
    "printf",
    "pwd",
    "which",
    "type",
    "file",
    "stat",
}
READ_ONLY_GIT = {"status", "log", "show", "diff", "grep", "blame", "branch", "commit", "add", "ls-files", "rev-parse"}
INTERPRETERS = {"sh", "bash", "zsh", "dash", "fish", "eval", "xargs", "source", ".", "exec", "env", "sudo", "pwsh"}
ENV_ASK = SHELL_ASK[-1]  # touching .env is checked even for read-only commands


def _segments(cmd: str) -> list[list[str]]:
    out = []
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        try:
            words = shlex.split(seg, posix=True)
        except ValueError:
            words = seg.split()
        while words and re.match(r"^[A-Za-z_]\w*=", words[0]):  # FOO=bar cmd
            words = words[1:]
        if words:
            out.append(words)
    return out


def _read_only(words: list[str]) -> bool:
    head = os.path.basename(words[0])
    if head == "git":
        rest = words[1:]
        while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
            rest = rest[2:]
        sub = next((w for w in rest if not w.startswith("-")), "")
        return sub in READ_ONLY_GIT and not (sub == "branch" and any(w in ("-D", "-d", "-m", "-M") for w in words))
    if head in ("find", "fd") and any(
        w in ("-exec", "-execdir", "-ok", "-delete", "-x", "-X", "--exec") for w in words
    ):
        return False
    return head in READ_ONLY_CMDS


def _git_sub(words: list[str]) -> tuple[str, list[str]]:
    """('push', args after it) for `git [-C dir] [-c k=v] push ...`; ('', []) when not git."""
    if not words or os.path.basename(words[0]) != "git":
        return "", []
    rest = words[1:]
    while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
        rest = rest[2:]
    while rest and rest[0].startswith("-"):
        rest = rest[1:]
    return (rest[0], rest[1:]) if rest else ("", [])


def push_verdict(root: Path, args: list[str], cfg: dict) -> tuple[str, str]:
    """deny (force), allow (a feature branch, when push_policy = feature-branches) or ask."""
    if any(a in ("-f", "--force") or (a.startswith("+") and len(a) > 1) for a in args):
        return "deny", "force push"
    if cfg.get("push_policy", "ask") != "feature-branches":
        return "ask", "publishes commits (push_policy: ask)"
    risky = ("--delete", "-d", "--mirror", "--all", "--tags", "--prune", "--force-with-lease", "--force-if-includes")
    if any(
        a in risky or a.startswith(("--force-with-lease=", "--repo", "--receive-pack", "-o", "--push-option"))
        for a in args
    ):
        return "ask", "push with a risky option"
    pos = [a for a in args if not a.startswith("-")]
    refspecs = pos[1:]
    code, cur = run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=root, timeout=5)
    cur = cur.strip() if code == 0 else ""  # detached or unknown -> ask below
    if not refspecs:
        refspecs = [cur]
    protected = cfg.get("protected_branches", ["main", "master", "develop", "trunk", "release/*", "production"])
    for r in refspecs:
        dst = r.split(":", 1)[-1] if ":" in r else r
        dst = cur if dst in ("HEAD", "") else dst
        dst = dst.removeprefix("refs/heads/")
        is_tag = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{dst}"], cwd=root, timeout=5)[0] == 0
        if (
            not dst
            or dst == "HEAD"
            or dst.startswith("refs/")
            or is_tag
            or any(fnmatch.fnmatch(dst, g) for g in protected)
        ):
            return "ask", f"pushes to '{dst or '?'}' (protected branch, tag or detached HEAD)"
    return "allow", ""


def decide_shell(root: Path, cmd: str, session: str, cfg: dict) -> tuple[str, str]:
    for pat, why in SHELL_DENY:
        if re.search(pat, cmd):
            return "deny", f"eos guard blocked: {why}. If it is really needed, ask the human to run it."
    segs = _segments(cmd)
    for w in segs:
        sub, rest = _git_sub(w)
        if sub == "push":
            verdict, why = push_verdict(root, rest, cfg)
            if verdict == "deny":
                return "deny", f"eos guard blocked: {why}. If it is really needed, ask the human to run it."
            if verdict == "ask":
                return "ask", f"eos guard: needs human approval ({why})."
    runs_code = any(os.path.basename(w[0]) in INTERPRETERS for w in segs) or "$(" in cmd or "`" in cmd
    if runs_code and re.search(r"\bgit\b[^;&|]*\bpush\b", cmd):  # push hidden inside sh -c / eval / $(...)
        return "ask", "eos guard: needs human approval (push inside a sub-shell)."
    all_ro = bool(segs) and not runs_code and all(_read_only(w) for w in segs)
    for pat, why in [ENV_ASK] if all_ro else SHELL_ASK:
        if re.search(pat, cmd):
            return "ask", f"eos guard: needs human approval ({why})."
    if all_ro:
        return "allow", ""
    loop = loop_guard(root, session, cmd, int(cfg.get("loop_limit", 3)))
    return ("ask", loop) if loop else ("allow", "")


def decide_paths(root: Path, paths: list[str], is_read: bool) -> tuple[str, str]:
    for p in paths:
        rel = _rel(root, p)
        if is_secret_path(rel):
            return "deny", (
                f"eos guard: '{rel}' looks like a secret or credential file. Agents must not read or "
                "write it; refer to env var names instead."
            )
        if not is_read:
            if rel.startswith(("/", "..")):
                return "deny", f"eos guard: writing outside the project ({rel}) is not allowed."
            hit = protected_match(root, rel)
            if hit:
                return "deny", (
                    f"eos guard: '{rel}' is protected ('{hit}' in .eos/protected.txt). Describe the change "
                    "you need and let the human make or approve it."
                )
    return "allow", ""


def session_since(root: Path, session: str) -> float | None:
    """When this agent session was first seen by a hook (recorded on its first guarded tool call)."""
    state = root / ".eos/state/sessions.json"
    try:
        data = json.loads(read(state))
    except (OSError, ValueError):
        data = {}
    now = time.time()
    data = {k: v for k, v in data.items() if now - v < 7 * 86400}
    if session not in data:
        data[session] = now
        try:
            write(state, json.dumps(data))
        except OSError:
            pass
        return None
    return float(data[session])


def stop_check(root: Path, cfg: dict, since: float | None = None) -> tuple[bool, str]:
    """Run the fast check on files changed in this session when the agent says it is done.

    Files you left dirty before the session started are not the agent's job: checking them would make the
    agent "fix" unrelated work on every stop. Returns (ok, capped output tail)."""
    mode = cfg.get("stop_check", "auto")
    if mode == "off":
        return True, ""
    branch = current_branch(root)
    if any(branch.startswith(p.rstrip("*")) for p in cfg.get("no_stop_check_branches", ["spike/"])):
        return True, ""  # throwaway work: checks would only slow the experiment (guards stay on)
    code, status = run(["git", "status", "--porcelain"], cwd=root, timeout=10)
    if code != 0 or not status.strip():
        return True, ""
    files = [
        f for f in (ln[3:].split(" -> ")[-1].strip().strip('"') for ln in status.splitlines()) if (root / f).is_file()
    ]
    if since is not None:
        files = [f for f in files if (root / f).stat().st_mtime >= since - 2]
    if not files:
        return True, ""
    timeout = int(cfg.get("stop_check_timeout", 180))
    # gitleaks still runs at commit time; at stop it only adds time (and a Go build on first run).
    env = dict(os.environ, SKIP="no-commit-to-branch,gitleaks", NO_COLOR="1")
    if mode == "auto":
        if not ((root / ".pre-commit-config.yaml").exists() and shutil.which("pre-commit")):
            return True, ""
        cmd = ["pre-commit", "run", "--color", "never", "--hook-stage", "pre-commit", "--files", *files]
    else:
        cmd = ["cmd", "/c", mode] if IS_WINDOWS else ["sh", "-c", mode]
    rc, out = run(cmd, cwd=root, timeout=timeout, env=env)
    if rc != 0 and mode == "auto":  # formatters fix files and report failure once: re-run to confirm
        rc, out = run(cmd, cwd=root, timeout=timeout, env=env)
    if rc == 124:  # timeout (often first-run hook installs on a slow link): don't make the agent retry
        return True, ""
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)  # strip colours
    return rc == 0, cap_output(root, out)


def cap_output(root: Path, out: str, max_lines: int = 40, max_chars: int = 3000) -> str:
    """Only the failing part goes back into the model's context; the full log is saved for humans."""
    lines = [ln[:300] for ln in out.splitlines() if ln.strip() and not re.search(r"(Passed|Skipped)$", ln.strip())]
    tail = "\n".join(lines[-max_lines:])[-max_chars:]
    try:
        write(root / ".eos/state/last-check.log", out)
    except OSError:
        return tail
    more = len(lines) > max_lines or len("\n".join(lines)) > max_chars
    return tail + ("\n(truncated; full log: .eos/state/last-check.log)" if more else "")


def _stop_counter(root: Path, session: str, reset: bool = False) -> int:
    state = root / ".eos/state/stop.json"
    try:
        data = json.loads(read(state))
    except (OSError, ValueError):
        data = {}
    n = 0 if reset else int(data.get(session, 0)) + 1
    data[session] = n
    try:
        write(state, json.dumps(data))
    except OSError:
        pass
    return n


def _cursor_runs_own_hooks(root: Path, data: object) -> bool:
    """Cursor also runs Claude Code hooks from .claude/settings.json (third-party imports, on by default). When
    eos's native Cursor hooks are installed too, the Claude copy would run the guard and the stop check a second
    time, so it steps aside. Detected from the payload (Cursor sends cursor_version / workspace_roots with every
    hook), not from the environment: a `claude` started in Cursor's terminal may inherit Cursor variables and
    must keep its guard."""
    if not (isinstance(data, dict) and ("cursor_version" in data or "workspace_roots" in data)):
        return False
    try:
        return HOOK_MARK in (root / ".cursor/hooks.json").read_text(encoding="utf-8")
    except OSError:
        return False


def cmd_guard(args: argparse.Namespace) -> int:
    raw = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        data = {}
    if args.mode.startswith("claude-") and _cursor_runs_own_hooks(_project_root_for_guard(), data):
        return 0  # no output = no opinion; the native cursor-* hook decides
    root = _project_root_for_guard()
    cfg = _load_cfg(root)
    t0 = time.time()
    try:
        decision, reason = _guard_decide(args.mode, data if isinstance(data, dict) else {}, root, cfg)
    except Exception as exc:  # noqa: BLE001 - fail open (never brick the editor), but leave a trace
        try:
            (root / ".eos/state").mkdir(parents=True, exist_ok=True)
            with open(root / ".eos/state/guard.log", "a", encoding="utf-8") as fh:
                fh.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {args.mode} error: {exc!r}\n")
        except OSError:
            pass
        decision, reason = "allow", ""
    ms = int((time.time() - t0) * 1000)
    if args.mode.endswith("-stop"):
        log_event(root, "stop", ms=ms, ok=decision != "block", gave_up="gave up" in reason)
    else:
        log_event(root, "guard", m=args.mode, d=decision, ms=ms, **({"r": reason[:120]} if decision != "allow" else {}))
    return _guard_emit(args.mode, decision, reason, cfg)


def _guard_decide(mode: str, data: dict, root: Path, cfg: dict) -> tuple[str, str]:
    session = str(data.get("conversation_id") or data.get("session_id") or data.get("taskId") or "default")
    limit = int(cfg.get("loop_limit", 3))
    since = session_since(root, session)
    if mode in ("cursor-stop", "claude-stop"):
        ok, tail = stop_check(root, cfg, since)
        if ok:
            _stop_counter(root, session, reset=True)
            return "allow", ""
        n = int(data.get("loop_count", 0)) + 1 if mode == "cursor-stop" else _stop_counter(root, session)
        if n > limit:
            return (
                "allow",
                f"eos stop-check: gave up after {limit} attempts; a human must look (see memory/handoff.md).",
            )
        if n == limit:
            return "block", (
                f"eos stop-check still failing after {limit - 1} fix attempts. STOP fixing now: write "
                "memory/handoff.md (eos-handoff skill: goal, failing command + output, what you tried, "
                f"hypotheses) and ask the human. Do not weaken checks. Output tail:\n{tail}"
            )
        return "block", (
            f"eos stop-check failed (attempt {n}/{limit}). Fix the root cause; never skip or weaken "
            f"tests or linters. Output tail:\n{tail}"
        )
    if mode == "cursor-shell":
        return decide_shell(root, str(data.get("command", "")), session, cfg)
    if mode == "cursor-read":
        return decide_paths(root, [str(data.get("file_path", ""))], is_read=True)
    if mode == "cursor-mcp":
        tool = str(data.get("tool_name", ""))
        if cfg.get("mcp_write_ask", True) and re.search(
            r"(create|update|delete|remove|merge|push|write|send|post|publish|deploy|run|exec)", tool, re.IGNORECASE
        ):
            return "ask", f"eos guard: MCP tool '{tool}' can change things; approve it explicitly."
        return "allow", ""
    if mode == "cline-tool":  # generic tool hooks: cursor-tool, claude-tool, cline-tool
        pre = data.get("preToolUse", data)
        tool, tin = str(pre.get("toolName", pre.get("tool", ""))), pre.get("parameters", {}) or {}
    else:
        tool, tin = str(data.get("tool_name", "")), data.get("tool_input", {}) or {}
        if isinstance(tin, str):
            try:
                tin = json.loads(tin)
            except ValueError:
                tin = {"command": tin}
    tl = tool.lower()
    command = tin.get("command") if isinstance(tin, dict) else None
    if isinstance(command, str) and command and (tl in SHELL_TOOLS or "command" in tl or "shell" in tl):
        if mode == "cursor-tool":  # Cursor shell commands go through beforeShellExecution (which supports "ask")
            return "allow", ""
        return decide_shell(root, command, session, cfg)
    paths: list[str] = []
    _collect(tin, PATH_KEYS, paths)
    if not paths:
        return "allow", ""
    is_read = any(h in tl for h in READ_TOOL_HINTS) and not any(h in tl for h in WRITE_TOOL_HINTS)
    return decide_paths(root, paths, is_read)


def _guard_emit(mode: str, decision: str, reason: str, cfg: dict) -> int:
    if mode == "cursor-stop":
        print(json.dumps({"followup_message": reason} if decision == "block" else {}))
        return 0
    if mode == "claude-stop":
        if decision == "block":
            print(json.dumps({"decision": "block", "reason": reason}))
        elif reason:
            print(json.dumps({"systemMessage": reason}))
        return 0
    if mode.startswith("cursor-"):
        if mode in ("cursor-read", "cursor-tool") and decision == "ask":
            decision = "deny"  # these Cursor hooks do not enforce "ask"
        out: dict = {"permission": decision}
        if decision != "allow":
            out.update(user_message=reason, agent_message=reason)
        print(json.dumps(out))
        return 0
    if mode == "claude-tool":
        if decision == "deny":
            eprint(reason)
            return 2  # Claude Code: exit 2 blocks and feeds stderr back to the model
        if decision == "ask":
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": reason,
                        }
                    }
                )
            )
        return 0
    if mode == "cline-tool":
        cancel = decision == "deny" or (decision == "ask" and cfg.get("cline_ask", "cancel") == "cancel")
        out = {"cancel": cancel}
        if cancel:
            out["errorMessage"] = reason + (
                " Cline hooks cannot ask, so the human must run or approve it." if decision == "ask" else ""
            )
        elif reason:
            out["contextModification"] = reason
        print(json.dumps(out))
        return 0
    return 0


# ----------------------------------------------------------------------------- test integrity (anti reward-hacking)
SKIP_RX = _lazy_rx(
    r"pytest\.mark\.(skip|xfail)|pytest\.skip\(|unittest\.skip|@skip\b|\b(it|test|describe)\.(skip|only|todo)\(|"
    r"\bx(it|describe|test)\(|\bfit\(|\bfdescribe\(|t\.Skip\(|@Disabled\b|@Ignore\b|markTestSkipped|#\[ignore\]"
)
SUPPRESS_RX = _lazy_rx(
    r"#\s*noqa|type:\s*ignore|pyright:\s*ignore|@ts-ignore|@ts-expect-error|@ts-nocheck|eslint-disable|"
    r"biome-ignore|pragma:\s*no\s*cover|istanbul\s+ignore|c8\s+ignore|//\s*nolint|@SuppressWarnings|"
    r"#\[allow\(|NOSONAR|\bnosec\b"
)
ASSERT_RX = _lazy_rx(r"\bassert\w*\b|\bexpect\(|\.should\b|\brequire\.\w+\(|\bt\.(Error|Fatal)|\bassertThat\(")
TEST_FILE_RX = _lazy_rx(
    r"(^|/)(tests?|__tests__|e2e|spec)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|"
    r"Test\.java$|Tests?\.cs$"
)
THRESH_FILE_RX = _lazy_rx(
    r"(pyproject\.toml|setup\.cfg|\.coveragerc|tox\.ini|pytest\.ini|vitest\.config\.[cm]?[jt]s|"
    r"jest\.config\.[cm]?[jt]s|package\.json|codecov\.ya?ml|\.nycrc(\.json)?|stryker\.conf\.\w+|"
    r"sonar-project\.properties|\.k6/.*|k6/.*\.js)$"
)
THRESH_RX = _lazy_rx(
    r"(fail[_-]under|threshold\w*|branches|lines|functions|statements|break|min[_-]?\w*)[\"']?\s*[:=]\s*[\"']?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
GATE_CFG_RX = _lazy_rx(
    r"^(\.github/workflows/|\.pre-commit-config\.yaml$|\.eos/(?!state/)|\.cursor/hooks\.json$|"
    r"\.claude/settings\.json$|\.clinerules/hooks/|ruff\.toml$|\.ruff\.toml$|eslint\.config\.|"
    r"\.eslintrc|biome\.jsonc?$|mypy\.ini$|CODEOWNERS$|\.github/CODEOWNERS$|(.*/)?quarantine\.json$|"
    r"(.*/)?ops/(slo|flags)\.json$|(.*/)?\.hadolint\.ya?ml$|(.*/)?\.checkov\.ya?ml$|"
    r"(.*/)?lighthouserc(\.json|\.js|\.cjs|\.ya?ml)?$|\.lighthouserc\.\w+$)"
)


def parse_unified_diff(diff: str) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    added: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    deleted: list[str] = []
    cur = None
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            cur = line.split(" b/", 1)[-1]
            added.setdefault(cur, [])
            removed.setdefault(cur, [])
        elif cur is None:
            continue
        elif line.startswith("deleted file mode"):
            deleted.append(cur)
        elif line.startswith(("+++", "---", "@@", "index ", "new file mode", "similarity", "rename ")):
            continue
        elif line.startswith("+"):
            added[cur].append(line[1:])
        elif line.startswith("-"):
            removed[cur].append(line[1:])
    return added, removed, deleted


def integrity_findings(added: dict, removed: dict, deleted: list[str]) -> list[str]:
    findings: list[str] = []
    for f in sorted(added):
        if GATE_CFG_RX.search(f):
            findings.append(f"{f}: quality-gate config changed (review it carefully)")
        if f.endswith((".md", ".mdc", ".txt")) or f.startswith(".eos/"):
            continue
        for ln in added[f]:
            if SKIP_RX.search(ln):
                findings.append(f"{f}: new skip/only/xfail -> {ln.strip()[:100]}")
            elif SUPPRESS_RX.search(ln):
                findings.append(f"{f}: new suppression comment -> {ln.strip()[:100]}")
        if TEST_FILE_RX.search(f) and f not in deleted:
            a = sum(1 for ln in added[f] if ASSERT_RX.search(ln))
            r = sum(1 for ln in removed[f] if ASSERT_RX.search(ln))
            if r > a:
                findings.append(f"{f}: {r - a} assertion line(s) removed (net)")
        if THRESH_FILE_RX.search(f):

            def nums(lines: list[str]) -> dict[str, float]:
                return {m.group(1).lower(): float(m.group(2)) for ln in lines for m in THRESH_RX.finditer(ln)}

            old, new = nums(removed[f]), nums(added[f])
            for k, v in new.items():
                if k in old and v < old[k]:
                    findings.append(f"{f}: threshold '{k}' lowered {old[k]:g} -> {v:g}")
    for f in deleted:
        if TEST_FILE_RX.search(f):
            findings.append(f"{f}: test file deleted")
    return findings


def cmd_test_integrity(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    code, mb = run(["git", "merge-base", args.base, "HEAD"], cwd=root, timeout=20)
    if code != 0:
        eprint(f"cannot find a merge-base with {args.base}: {mb.strip()}")
        return 2
    code, diff = run(["git", "diff", "--no-color", "-U0", "--no-ext-diff", "-M", mb.strip()], cwd=root, timeout=60)
    if code != 0:
        eprint(diff)
        return 2
    added, removed, deleted = parse_unified_diff(diff)
    _, untracked = run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, timeout=20)
    for f in untracked.splitlines():  # local runs: new files not yet added count as fully added
        try:
            added.setdefault(f, []).extend(read(root / f).splitlines())
            removed.setdefault(f, [])
        except (OSError, UnicodeDecodeError):
            pass
    findings = integrity_findings(added, removed, deleted)
    # A lint/type suppression is often legitimate; blocking every one trained people to add the override label
    # by reflex. They block only in risky lanes (money, auth, migrations, infra) or with --strict; else they warn.
    soft = [f for f in findings if "new suppression comment" in f]
    if soft and not getattr(args, "strict", False):
        risk = classify_change(root, args.base)["risk"]
        if risk not in ("risky", "one-way-door"):
            for x in soft:
                print("  warn: " + x + " (say why in the PR)")
            findings = [f for f in findings if f not in soft]
    if findings:
        print("eos test-integrity: changes that can weaken verification (a human must approve):")
        for x in findings:
            print("  - " + x)
        print("If intended: explain why in the PR, get review, then add the label 'test-change-approved'.")
        return 1
    print("eos test-integrity: OK (no new skips/suppressions, no removed asserts, no lowered thresholds)")
    return 0


# ----------------------------------------------------------------------------- testing gates (stage 5)
# Cheap, stdlib-only gates that turn testing advice into checks: changed-line coverage, flaky-test quarantine
# with expiry, and mutation-testing targets/score for risky code. Heavy tools (mutmut, Stryker, k6) run in CI
# workflows from `eos scaffold`; these commands only plan and judge, so they stay fast enough for any lane.
TESTING_DEFAULTS = {
    "diff_coverage_min": 80.0,  # changed coverable lines that must be executed by tests (all code)
    "diff_coverage_risky_min": 90.0,  # money/auth/security paths (Google: 90% as a per-commit lower bound)
    "quarantine_max_days": 14,  # a flaky test may stay quarantined at most this long (Fowler: e.g. a week)
    "mutation_min": 60.0,  # Stryker's default "low" threshold; raise it for payment/auth modules
}
COVERAGE_REPORTS = ("coverage.xml", "coverage/cobertura-coverage.xml", "coverage/lcov.info", "lcov.info")
TEST_PATH_RX = _lazy_rx(r"(^|/)(tests?|__tests__|e2e|spec|testdata|fixtures)/|(^|/)test_[^/]+$|_test\.\w+$|"
                          r"\.(test|spec)\.[cm]?[jt]sx?$|(^|/)conftest\.py$")  # fmt: skip
HUNK_RX = _lazy_rx(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def testing_cfg(root: Path) -> dict:
    t = _load_cfg(root).get("testing", {})
    return {**TESTING_DEFAULTS, **(t if isinstance(t, dict) else {})}


def changed_lines(diff: str) -> dict[str, set[int]]:
    """New-side line numbers added or modified per file, from a `git diff -U0` text."""
    out: dict[str, set[int]] = {}
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            cur = None if p == "/dev/null" else p.removeprefix("b/")
            if cur:
                out.setdefault(cur, set())
        elif cur and (m := HUNK_RX.match(line)):
            start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            out[cur].update(range(start, start + count))
    return out


def parse_coverage(text: str) -> dict[str, dict[int, int]]:
    """{path: {line: hits}} from a Cobertura XML report (coverage.py, Vitest/Jest/Istanbul `cobertura`)
    or an LCOV tracefile (Vitest/Jest `lcov`, Flutter `--coverage`, c8). Paths are as written in the report;
    Cobertura paths are joined to each <source> so they can be matched against repository paths."""
    cov: dict[str, dict[int, int]] = {}
    if text.lstrip().startswith("<"):
        import xml.etree.ElementTree as ET  # stdlib; reports are produced by our own CI, not untrusted input

        tree = ET.fromstring(text)
        sources = [s.text.strip() for s in tree.iter("source") if s.text and s.text.strip()] or [""]
        for cls in tree.iter("class"):
            fn = cls.get("filename") or ""
            lines = {int(ln.get("number")): int(float(ln.get("hits") or 0)) for ln in cls.iter("line")}
            for s in sources:
                key = os.path.normpath(os.path.join(s, fn)) if s else os.path.normpath(fn)
                d = cov.setdefault(key.replace("\\", "/"), {})
                for n, h in lines.items():
                    d[n] = max(h, d.get(n, 0))
        return cov
    cur: dict[int, int] | None = None
    for ln in text.splitlines():
        if ln.startswith("SF:"):
            cur = cov.setdefault(os.path.normpath(ln[3:].strip()).replace("\\", "/"), {})
        elif ln.startswith("DA:") and cur is not None:
            parts = ln[3:].split(",")
            if len(parts) >= 2 and parts[0].strip().isdigit():
                n, h = int(parts[0]), int(float(parts[1] or 0))
                cur[n] = max(h, cur.get(n, 0))
        elif ln.startswith("end_of_record"):
            cur = None
    return cov


def _match_report_path(rel: str, cov: dict[str, dict[int, int]], root: Path) -> str | None:
    """Report key for repository path `rel`. Reports may hold absolute paths, repo-relative paths, or paths
    relative to an app directory (`backend/app/x.py` is `app/x.py` in a report made inside `backend/`)."""
    absp = (root / rel).resolve().as_posix()
    for k in (rel, absp):
        if k in cov:
            return k
    best, best_len = None, 0
    for k in cov:
        kk = k.removeprefix("./")
        if k.endswith("/" + rel) or rel.endswith("/" + kk):
            n = min(len(kk), len(rel))
            if n > best_len:
                best, best_len = k, n
    return best


def _is_risky_path(rel: str, cfg: dict) -> bool:
    lc = cfg.get("lanes", {}) if isinstance(cfg.get("lanes"), dict) else {}
    words = RISK_WORDS | set(lc.get("risk_words", []))
    return bool(words & _path_words(rel) or any(re.match(glob_to_regex(g), rel) for g in lc.get("risky", [])))


def diff_coverage(
    root: Path, reports: list[Path], base: str | None, cfg: dict, min_all: float, min_risky: float
) -> dict:
    """Changed-line coverage for the diff from `base` (merge-base) to the working tree."""
    cov: dict[str, dict[int, int]] = {}
    for rp in reports:
        for k, v in parse_coverage(read(rp)).items():
            d = cov.setdefault(k, {})
            for n, h in v.items():
                d[n] = max(h, d.get(n, 0))
    ref, ref_name = lane_base(root, base)
    _, diff = run(["git", "diff", "--no-color", "-U0", "--no-ext-diff", "-M", ref], cwd=root, timeout=60)
    lines = changed_lines(diff if ref else "")
    _, untracked = run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, timeout=20)
    for f in untracked.splitlines():
        try:
            lines[f] = set(range(1, len(read(root / f).splitlines()) + 1))
        except (OSError, UnicodeDecodeError, ValueError):
            pass
    files, unmeasured = [], []
    for rel in sorted(lines):
        if not lines[rel] or TEST_PATH_RX.search(rel) or not (root / rel).is_file():
            continue
        key = _match_report_path(rel, cov, root)
        if key is None:
            if re.search(r"\.(py|[cm]?[jt]sx?|dart|go|rb|java|kt|cs|rs)$", rel):
                unmeasured.append(rel)
            continue
        coverable = sorted(n for n in lines[rel] if n in cov[key])
        if not coverable:
            continue
        missing = [n for n in coverable if cov[key][n] == 0]
        risky = _is_risky_path(rel, cfg)
        files.append({"file": rel, "lines": len(coverable), "missing": missing, "risky": risky})
    out: dict = {"base": ref_name, "files": files, "unmeasured": unmeasured, "groups": {}}
    ok = True
    for name, want, sel in (("all", min_all, files), ("risky", min_risky, [f for f in files if f["risky"]])):
        total = sum(f["lines"] for f in sel)
        if not total:
            continue
        hit = total - sum(len(f["missing"]) for f in sel)
        pct = round(100.0 * hit / total, 1)
        passed = pct >= want
        ok = ok and passed
        out["groups"][name] = {"lines": total, "covered": hit, "percent": pct, "min": want, "ok": passed}
    out["ok"] = ok
    return out


def _ranges(nums: list[int]) -> str:
    out, start, prev = [], None, None
    for n in nums + [None]:  # type: ignore[list-item]
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    return ",".join(out)


def render_diff_coverage(r: dict) -> str:
    out = []
    for f in r["files"]:
        pct = 100.0 * (f["lines"] - len(f["missing"])) / f["lines"]
        miss = f" missing {_ranges(f['missing'])}" if f["missing"] else ""
        out.append(f"  {f['file']}{' [risky]' if f['risky'] else ''}: {pct:.0f}% of {f['lines']} line(s){miss}")
    for name, g in r["groups"].items():
        label = "changed lines" if name == "all" else "changed lines in money/auth/security paths"
        out.append(
            f"  {label}: {g['percent']}% ({g['covered']}/{g['lines']}), minimum {g['min']:g}%"
            + ("" if g["ok"] else "  <- below minimum")
        )
    if r["unmeasured"]:
        out.append(
            "  not in the coverage report (unimported or excluded? set coverage `source` so they show as 0%): "
            + ", ".join(r["unmeasured"][:8])
        )
    return "\n".join(out)


def find_coverage_reports(root: Path, m: dict | None = None) -> list[Path]:
    dirs = {"."}
    for v in ((m or {}).get("stacks") or {}).values():
        dirs.update(as_dirs(v))
    found = []
    for d in sorted(dirs):
        for name in COVERAGE_REPORTS:
            p = (root / d / name) if d not in (".", "") else root / name
            if p.is_file() and p not in found:
                found.append(p)
    return found


def cmd_diff_coverage(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = _load_cfg(root)
    t = testing_cfg(root)
    reports = [Path(r).resolve() for r in args.reports] or find_coverage_reports(root, load_manifest(root))
    reports = [r for r in reports if r.is_file()]
    if not reports:
        eprint(
            "eos diff-coverage: no coverage report found. Produce one first, e.g. `pytest --cov --cov-report=xml`"
            " (coverage.xml) or Vitest `coverage.reporter: ['lcov']` (coverage/lcov.info)."
        )
        return 2
    min_all = args.min if args.min is not None else float(t["diff_coverage_min"])
    min_risky = args.risky_min if args.risky_min is not None else float(t["diff_coverage_risky_min"])
    r = diff_coverage(root, reports, args.base, cfg, min_all, min_risky)
    if args.json:
        print(json.dumps(r, indent=2))
        return 0 if r["ok"] else 1
    body = render_diff_coverage(r)
    if not r["groups"]:
        print("eos diff-coverage: no changed coverable lines (nothing to measure)")
        if body:
            print(body)
        return 0
    print(f"eos diff-coverage vs {r['base'] or 'HEAD'} ({', '.join(p.name for p in reports)}):")
    print(body)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as fh:
            fh.write("### Diff coverage\n\n```\n" + body + "\n```\n")
    if r["ok"]:
        print("eos diff-coverage: OK")
        return 0
    print(
        "eos diff-coverage: FAILED. Add tests that exercise the missing lines (assert behaviour, not just execute"
        " it). Lowering the minimum is a gate change a human must approve."
    )
    return 1


# Flaky-test quarantine: a reviewed list with an owner, a ticket and an expiry, never a silent skip.
QUARANTINE_FILE = "tests/quarantine.json"
QUARANTINE_FIELDS = ("id", "reason", "owner", "issue", "added", "expires")


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def quarantine_problems(data: object, max_days: int, today: dt.date | None = None) -> tuple[list[str], list[dict]]:
    """(problems, active entries) for a quarantine file. Expired entries are problems: fix or delete the test."""
    today = today or _today()
    probs: list[str] = []
    active: list[dict] = []
    if not isinstance(data, dict) or not isinstance(data.get("tests"), list):
        return ['quarantine file must be a JSON object with a "tests" list'], []
    seen: set[str] = set()
    for i, e in enumerate(data["tests"]):
        where = f"tests[{i}]"
        if not isinstance(e, dict):
            probs.append(f"{where}: not an object")
            continue
        tid = str(e.get("id", "")).strip()
        where = f"{where} {tid!r}" if tid else where
        missing = [k for k in QUARANTINE_FIELDS if not str(e.get(k, "")).strip()]
        if missing:
            probs.append(f"{where}: missing {', '.join(missing)}")
            continue
        if tid in seen:
            probs.append(f"{where}: listed twice")
        seen.add(tid)
        try:
            added = dt.date.fromisoformat(str(e["added"]))
            expires = dt.date.fromisoformat(str(e["expires"]))
        except ValueError:
            probs.append(f"{where}: added/expires must be ISO dates (YYYY-MM-DD)")
            continue
        if expires < added:
            probs.append(f"{where}: expires before it was added")
        elif (expires - added).days > max_days:
            probs.append(f"{where}: quarantined for {(expires - added).days} days > max {max_days}; fix it sooner")
        elif expires < today:
            probs.append(f"{where}: quarantine expired on {expires} (fix the test, or delete it with a reason)")
        else:
            active.append(e)
    return probs, active


def cmd_quarantine(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    path = root / (args.file or QUARANTINE_FILE)
    max_days = int(args.max_days or testing_cfg(root)["quarantine_max_days"])
    if args.action == "add":
        if not (args.id and args.reason and args.owner and args.issue):
            eprint("eos quarantine add needs ID --reason --owner --issue")
            return 2
        data = json.loads(read(path)) if path.exists() else {"tests": []}
        if any(e.get("id") == args.id for e in data.get("tests", [])):
            eprint(f"{args.id} is already quarantined")
            return 1
        days = min(int(args.days or max_days), max_days)
        today = _today()
        data.setdefault("tests", []).append(
            {
                "id": args.id,
                "reason": args.reason,
                "owner": args.owner,
                "issue": args.issue,
                "added": today.isoformat(),
                "expires": (today + dt.timedelta(days=days)).isoformat(),
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, json.dumps(data, indent=2) + "\n")
        print(f"quarantined {args.id} until {data['tests'][-1]['expires']} ({path.relative_to(root).as_posix()})")
        print("  it still runs, but cannot fail the build; this change needs human review (test integrity)")
        return 0
    if not path.exists():
        print(f"eos quarantine: no {path.relative_to(root).as_posix()} (nothing quarantined)")
        return 0
    try:
        data = json.loads(read(path))
    except ValueError as exc:
        print(f"eos quarantine: {path.relative_to(root).as_posix()} is not valid JSON: {exc}")
        return 1
    probs, active = quarantine_problems(data, max_days)
    if args.action == "list":
        for e in active:
            print(f"  {e['id']}  until {e['expires']}  owner {e['owner']}  {e['issue']}  ({e['reason']})")
    for p in probs:
        print("  error: " + p)
    print(f"eos quarantine: {len(active)} active, {len(probs)} problem(s)")
    return 1 if probs else 0


# Mutation testing: plan targets from the diff (risky paths, or every changed source file with lane:risky) and
# judge a run's score. Running mutmut/Stryker is left to CI (`eos scaffold mutation`), never the local fast path.
PY_SRC_RX = _lazy_rx(r"\.py$")
JS_SRC_RX = _lazy_rx(r"\.(m|c)?[jt]sx?$")


def _py_module(rel_in_dir: str, src_root: str) -> str | None:
    p = rel_in_dir
    if src_root and p.startswith(src_root.rstrip("/") + "/"):
        p = p[len(src_root.rstrip("/")) + 1 :]
    if not p.endswith(".py"):
        return None
    mod = p[:-3].replace("/", ".")
    return mod.removesuffix(".__init__")


def mutation_plan(root: Path, m: dict, base: str | None, everything: bool = False, labels: str = "") -> dict:
    """Targets for incremental mutation testing. Default: changed source files on money/auth/security paths
    (risk words, `lanes.risky` globs). `lane:risky` label or everything=True: every changed source file."""
    c = classify_change(root, base, labels=labels)
    cfg = _load_cfg(root)
    lbls = {x.strip() for x in (labels or os.environ.get("EOS_LABELS", "")).split(",")}
    all_changed = bool(lbls & {"lane:risky", "lane:one-way-door"}) or os.environ.get("EOS_LANE") in (
        "risky",
        "one-way-door",
    )
    if everything:
        _, ls = run(["git", "ls-files"], cwd=root, timeout=20)
        cands = [f for f in ls.splitlines() if _is_risky_path(f, cfg)]
    else:
        cands = [f for f in c["files"] if f not in c["deleted"] and (all_changed or _is_risky_path(f, cfg))]
    cands = [f for f in cands if (root / f).is_file() and not TEST_PATH_RX.search(f)]
    home_packs = load_project_packs(root)[1]
    plan: dict = {"base": c["base"], "python": [], "node": []}
    for sid, v in sorted((m.get("stacks") or {}).items()):
        ci = (home_packs.get(sid).meta.get("ci") if home_packs.get(sid) else "") or ""
        for d in as_dirs(v):
            mine = _rel_to(d, [f for f in cands if _within(f, d)])
            if (ci == "python" or sid.startswith("python")) and not any(p["dir"] == d for p in plan["python"]):
                src = "src" if (root / d / "src").is_dir() else ""
                mods = sorted({mod for f in mine if PY_SRC_RX.search(f) and (mod := _py_module(f, src))})
                if mods:
                    plan["python"].append({"dir": d, "patterns": [f"{x}.*" for x in mods]})
            elif ci == "node" and not any(p["dir"] == d for p in plan["node"]):
                srcs = [f for f in mine if JS_SRC_RX.search(f) and not f.endswith(".d.ts")]
                if srcs:
                    plan["node"].append({"dir": d, "files": sorted(srcs)})
    return plan


def cmd_mutation_plan(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    m = load_manifest(root) or {}
    plan = mutation_plan(root, m, args.base, args.all, args.labels or "")
    gh = os.environ.get("GITHUB_OUTPUT") if args.github_output else None
    if gh:
        py = plan["python"][0] if plan["python"] else {"dir": "", "patterns": []}
        nd = plan["node"][0] if plan["node"] else {"dir": "", "files": []}
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(f"python_dir={py['dir']}\npython_targets={' '.join(py['patterns'])}\n")
            fh.write(f"node_dir={nd['dir']}\nnode_files={','.join(nd['files'])}\n")
    if args.json:
        print(json.dumps(plan, indent=2))
        return 0
    if not plan["python"] and not plan["node"]:
        print("eos mutation-plan: no money/auth/security source files changed (label the PR lane:risky to force)")
        return 0
    for p in plan["python"]:
        print(f"  [{p['dir']}] mutmut run " + " ".join(shlex.quote(x) for x in p["patterns"]))
    for p in plan["node"]:
        print(f"  [{p['dir']}] stryker run --incremental --mutate {shlex.quote(','.join(p['files']))}")
    print("eos mutation-plan: then `eos mutation-score <report>` (CI: `eos scaffold mutation`)")
    return 0


def mutation_score(data: dict) -> dict:
    """Score from mutmut's `export-cicd-stats` JSON or a Stryker mutation-testing-report-schema JSON.
    detected = killed + timeout; undetected = survived + no coverage; score = detected / (detected + undetected)."""
    survivors: list[str] = []
    if "files" in data and isinstance(data["files"], dict):  # Stryker / mutation-testing-elements schema
        counts = {"Killed": 0, "Timeout": 0, "Survived": 0, "NoCoverage": 0}
        for fname, f in data["files"].items():
            for mu in f.get("mutants", []):
                st = mu.get("status", "")
                if st in counts:
                    counts[st] += 1
                if st in ("Survived", "NoCoverage"):
                    line = (mu.get("location") or {}).get("start", {}).get("line", "?")
                    survivors.append(f"{fname}:{line} {mu.get('mutatorName', '')} ({st})")
        detected, undetected = counts["Killed"] + counts["Timeout"], counts["Survived"] + counts["NoCoverage"]
        tool = "stryker"
    elif "killed" in data and "survived" in data:  # mutmut 3 export-cicd-stats
        detected = int(data.get("killed", 0)) + int(data.get("timeout", 0))
        undetected = int(data.get("survived", 0)) + int(data.get("no_tests", 0))
        tool = "mutmut"
    else:
        raise ValueError("not a mutmut cicd-stats or Stryker JSON report")
    total = detected + undetected
    return {
        "tool": tool,
        "detected": detected,
        "undetected": undetected,
        "score": round(100.0 * detected / total, 1) if total else None,
        "survivors": survivors,
    }


def cmd_mutation_score(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    want = args.min if args.min is not None else float(testing_cfg(root)["mutation_min"])
    try:
        r = mutation_score(json.loads(read(Path(args.report))))
    except (OSError, ValueError) as exc:
        eprint(f"eos mutation-score: {exc}")
        return 2
    if r["score"] is None:
        print(f"eos mutation-score ({r['tool']}): no mutants were tested (nothing to judge)")
        return 0
    print(
        f"eos mutation-score ({r['tool']}): {r['score']}% ({r['detected']} detected, {r['undetected']} survived"
        f" or uncovered), minimum {want:g}%"
    )
    for s in r["survivors"][:20]:
        print("  survived: " + s)
    if r["tool"] == "mutmut" and r["undetected"]:
        print("  list survivors: mutmut results; inspect one: mutmut show <name>")
    if r["score"] < want:
        print("eos mutation-score: FAILED. Each surviving mutant is a bug your tests would miss: add an assertion"
              " that fails for it (or mark it equivalent with a reason).")  # fmt: skip
        return 1
    print("eos mutation-score: OK")
    return 0


def testing_extras(
    root: Path, m: dict, c: dict, full: bool, base: str | None
) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """Cheap testing gates `eos verify` adds per lane (milliseconds, no test runs of their own).
    standard+: quarantine expiry. risky/one-way-door/--full: changed-line coverage when a coverage report newer
    than the changes exists (the full check may have just written it), and a pointer to CI mutation testing."""
    results: list[tuple[str, int, str, float]] = []
    notes: list[str] = []
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return results, notes
    t = testing_cfg(root)
    qf = root / QUARANTINE_FILE
    if qf.exists():
        try:
            probs, _ = quarantine_problems(json.loads(read(qf)), int(t["quarantine_max_days"]))
        except ValueError as exc:
            probs = [f"{QUARANTINE_FILE}: invalid JSON ({exc})"]
        results.append(("flaky quarantine", 1 if probs else 0, "\n".join(probs), 0.0))
    if not (full or c["risk"] in ("risky", "one-way-door")):
        return results, notes
    t0 = time.time()
    changed = [root / f for f in c["files"] if (root / f).is_file()]
    newest = max((p.stat().st_mtime for p in changed), default=0.0)
    fresh = [r for r in find_coverage_reports(root, m) if r.stat().st_mtime >= newest]
    if fresh:
        r = diff_coverage(
            root, fresh, base, _load_cfg(root), float(t["diff_coverage_min"]), float(t["diff_coverage_risky_min"])
        )
        if r["groups"]:
            results.append(("changed-line coverage", 0 if r["ok"] else 1, render_diff_coverage(r), time.time() - t0))
    else:
        notes.append(
            "changed-line coverage not measured: no coverage report newer than your edits (run tests with coverage,"
            " then `eos diff-coverage`; CI runs it on the PR)"
        )
    cfg = _load_cfg(root)
    if any(_is_risky_path(f, cfg) and not TEST_PATH_RX.search(f) for f in c["files"]):
        notes.append(
            "money/auth/security code changed: mutation testing runs in CI (`eos scaffold mutation`);"
            " targets: `eos mutation-plan`"
        )
    return results, notes


# ----------------------------------------------------------------------------- operations gates (stage 6)
# Stdlib-only checks that turn SRE advice into gates: an SLO file with a schema, multiwindow multi-burn-rate
# alert rules generated from it (Google SRE Workbook, "Alerting on SLOs"), every alert has a severity and a
# runbook that exists, and a feature-flag registry with owners and expiry dates (stale flags fail CI).
# Heavy tools (promtool, hadolint, checkov) run in CI from `eos scaffold`; `eos verify` calls the local
# binaries only in risky lanes and only for the files that changed.
OPS_DEFAULTS = {
    "slo_file": "ops/slo.json",
    "alert_rules": ["ops/alerts", "monitoring/alerts", "prometheus/rules"],  # folders scanned for *.yml/*.yaml
    "generated_rules": "ops/alerts/slo-burn-rate.rules.yml",
    "flags_file": "ops/flags.json",
    "runbook_dir": "docs/runbooks",
    "runbook_base_url": "",  # e.g. https://github.com/org/repo/blob/main/ (runbook_url = base + path)
    "flag_max_days": 90,  # release/experiment flags must be removed (or renewed in review) within this
}
# (severity, long window, short window, hours of the long window, share of the error budget consumed)
BURN_ALERTS = (
    ("page", "1h", "5m", 1, 0.02),
    ("page", "6h", "30m", 6, 0.05),
    ("ticket", "3d", "6h", 72, 0.10),
)
SLO_ID_RX = _lazy_rx(r"^[a-z0-9][a-z0-9-]{0,62}$")
FLAG_KEY_RX = _lazy_rx(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
FLAG_TYPES = ("release", "experiment", "ops", "permission")
ALERT_SEVERITIES = ("page", "ticket", "critical", "warning", "info")
FLAG_USE_RX = _lazy_rx(
    r"""\b(?:get_(?:boolean|string|integer|float|object)_(?:value|details)|flag_enabled|"""
    r"""get(?:Boolean|String|Number|Object)(?:Value|Details)|flagEnabled)\(\s*["'`]([A-Za-z0-9_.-]+)["'`]"""
)
CODE_EXT_RX = _lazy_rx(r"\.(py|[cm]?[jt]sx?|dart|go|kt|swift|rb)$")
OPS_CFG_FILES = ("slo_file", "flags_file")


def ops_cfg(root: Path) -> dict:
    o = _load_cfg(root).get("ops", {})
    return {**OPS_DEFAULTS, **(o if isinstance(o, dict) else {})}


def _num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_url(s: str) -> bool:
    return s.startswith(("https://", "http://"))


def _local_runbook(root: Path, ref: str, base_url: str) -> Path | None:
    """The repo file a runbook reference points to, or None for an external URL we cannot check."""
    ref = ref.strip().strip("\"'")
    if base_url and ref.startswith(base_url):
        ref = ref[len(base_url) :]
    elif _is_url(ref):
        m = re.search(r"/(?:blob|tree)/[^/]+/(.+)$", ref)  # GitHub/GitLab-style link into this repo
        if not m:
            return None
        ref = m.group(1)
    return root / ref.split("#")[0]


def slo_problems(root: Path, data: object, cfg: dict) -> tuple[list[str], list[str]]:
    """Schema check for ops/slo.json. Returns (errors, warnings)."""
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("slos"), list) or not data["slos"]:
        return ['needs {"service": "...", "slos": [ ... ]} with at least one SLO'], warns
    if not isinstance(data.get("service"), str) or not data["service"].strip():
        errs.append('"service" (the service name used in alert labels) is required')
    seen: set[str] = set()
    for i, s in enumerate(data["slos"]):
        if not isinstance(s, dict):
            errs.append(f"slos[{i}]: must be an object")
            continue
        sid = s.get("id")
        where = f"slo {sid!r}" if isinstance(sid, str) else f"slos[{i}]"
        if not isinstance(sid, str) or not SLO_ID_RX.match(sid):
            errs.append(f"{where}: id must be lower-case letters, digits and dashes")
        elif sid in seen:
            errs.append(f"{where}: duplicate id")
        else:
            seen.add(sid)
        for f in ("journey", "owner"):
            if not isinstance(s.get(f), str) or not s[f].strip():
                errs.append(f"{where}: {f} is required")
        obj = s.get("objective")
        if not _num(obj) or not 50 < obj < 100:
            errs.append(f"{where}: objective must be a percentage between 50 and 100 (exclusive), e.g. 99.5")
        elif obj > 99.99:
            warns.append(f"{where}: objective {obj}% leaves under 5 minutes of budget a month; is it real?")
        win = s.get("window_days")
        if not isinstance(win, int) or isinstance(win, bool) or not 7 <= win <= 90:
            errs.append(f"{where}: window_days must be a whole number of days between 7 and 90 (28 or 30 is usual)")
        rb = s.get("runbook")
        if not isinstance(rb, str) or not rb.strip():
            errs.append(f"{where}: runbook (path under {cfg['runbook_dir']}/ or URL) is required")
        else:
            p = _local_runbook(root, rb, cfg["runbook_base_url"])
            if p is not None and not p.is_file():
                errs.append(f"{where}: runbook {rb} does not exist (create it: eos ops runbook {sid})")
        sli = s.get("sli")
        if not isinstance(sli, dict) or not isinstance(sli.get("description"), str):
            errs.append(f'{where}: sli needs a "description" (what counts as good, measured where)')
            continue
        if s.get("alerting", True) is not False:
            for q in ("bad", "total"):
                v = sli.get(q)
                if not isinstance(v, str) or "{{window}}" not in v:
                    errs.append(
                        f'{where}: sli.{q} must be a PromQL expression with "{{{{window}}}}" for the rate window'
                        ' (or set "alerting": false)'
                    )
    return errs, warns


def _fmt(x: float) -> str:
    return format(round(x, 10), "g")


def slo_alert_rules(data: dict, cfg: dict) -> str:
    """Prometheus recording + alerting rules: multiwindow, multi-burn-rate (SRE Workbook ch. 5, iteration 6).
    Burn rate = share of budget consumed x SLO window / alert window: 14.4 / 6 / 1 for a 30-day window."""
    svc = data["service"]
    out = [
        "# GENERATED by `eos ops alerts` from " + cfg["slo_file"] + " - do not edit; edit the SLO file and regenerate.",
        "# Multiwindow, multi-burn-rate alerts (Google SRE Workbook, Alerting on SLOs): page when 2% of the error",
        "# budget burns in 1h (confirmed over 5m) or 5% in 6h (over 30m); ticket when 10% burns in 3 days (over 6h).",
        "groups:",
    ]
    for s in data["slos"]:
        if s.get("alerting", True) is False:
            continue
        sid, budget = s["id"], 1 - float(s["objective"]) / 100
        sel = f'{{slo="{sid}"}}'
        out += [f"  - name: slo-{sid}", "    rules:"]
        for w in sorted({w for _, lw, sw, _, _ in BURN_ALERTS for w in (lw, sw)}, key=_window_seconds):
            bad, total = (s["sli"][k].replace("{{window}}", w) for k in ("bad", "total"))
            out += [
                f"      - record: slo:sli_error:ratio_rate{w}",
                "        expr: |-",
                f"          ({bad}) / ({total})",
                "        labels:",
                f'          slo: "{sid}"',
                f'          service: "{svc}"',
            ]
        rb = s["runbook"]
        url = rb if _is_url(rb) else cfg["runbook_base_url"] + rb
        for sev in ("page", "ticket"):
            conds = [
                f"(slo:sli_error:ratio_rate{lw}{sel} > ({_fmt(f * s['window_days'] * 24 / h)} * {_fmt(budget)})"
                f" and slo:sli_error:ratio_rate{sw}{sel} > ({_fmt(f * s['window_days'] * 24 / h)} * {_fmt(budget)}))"
                for sv, lw, sw, h, f in BURN_ALERTS
                if sv == sev
            ]
            name = "SLOErrorBudgetBurn" + ("Fast" if sev == "page" else "Slow")
            out += [
                f"      - alert: {name}",
                "        expr: |-",
                "          " + "\n          or ".join(conds),
                "        labels:",
                f"          severity: {sev}",
                f'          slo: "{sid}"',
                f'          service: "{svc}"',
                "        annotations:",
                (
                    f'          summary: "{_q(svc)}: {sid} is burning its error budget ({s["objective"]}% over'
                    f' {s["window_days"]}d)"'
                ),
                f'          description: "{_q(s["journey"])}. Owner: {_q(s["owner"])}."',
                f"          runbook_url: {url}",
            ]
    return "\n".join(out) + "\n"


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _window_seconds(w: str) -> int:
    return int(w[:-1]) * {"m": 60, "h": 3600, "d": 86400}[w[-1]]


ALERT_RX = _lazy_rx(r"^(\s*)-\s+alert:\s*[\"']?([^\"'#\s]+)")


def alert_rule_files(root: Path, cfg: dict) -> list[Path]:
    out: list[Path] = []
    for d in cfg["alert_rules"]:
        p = root / d
        if p.is_dir():
            out += sorted(x for x in p.rglob("*") if x.suffix in (".yml", ".yaml") and x.is_file())
    return out


def alert_problems(root: Path, files: list[Path], cfg: dict) -> tuple[list[str], list[str]]:
    """Every Prometheus-style alert has labels.severity and annotations.runbook_url, and a local runbook exists.
    Line-based so it needs no YAML library; rules written as `- alert: Name` blocks."""
    errs: list[str] = []
    warns: list[str] = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        lines = read(f).splitlines()
        starts = [(i, m) for i, ln in enumerate(lines) if (m := ALERT_RX.match(ln))]
        for n, (i, m) in enumerate(starts):
            indent = len(m.group(1))
            end = len(lines)
            for j in range(i + 1, len(lines)):
                s = lines[j]
                if s.strip() and not s.lstrip().startswith("#") and len(s) - len(s.lstrip()) <= indent:
                    end = j
                    break
            if n + 1 < len(starts):
                end = min(end, starts[n + 1][0])
            block = lines[i:end]
            name = m.group(2)
            sev = next((re.sub(r"^\s*severity:\s*", "", b).strip().strip("\"'") for b in block
                        if re.match(r"^\s*severity:", b)), None)  # fmt: skip
            rb = next((re.sub(r"^\s*runbook_url:\s*", "", b).strip() for b in block
                       if re.match(r"^\s*runbook_url:", b)), None)  # fmt: skip
            where = f"{rel}:{i + 1} alert {name}"
            if not sev:
                errs.append(f"{where}: labels.severity is missing (page | ticket)")
            elif sev not in ALERT_SEVERITIES:
                warns.append(f"{where}: severity {sev!r} is not one of {', '.join(ALERT_SEVERITIES)}")
            if not rb:
                errs.append(f"{where}: annotations.runbook_url is missing (every alert needs a runbook)")
                continue
            p = _local_runbook(root, rb, cfg["runbook_base_url"])
            if p is None:
                continue
            if not p.is_file():
                errs.append(f"{where}: runbook {p.relative_to(root).as_posix()} does not exist")
            elif not re.search(r"(?im)^#+\s*(mitigat|first steps|immediate)", read(p)):
                warns.append(f"{where}: runbook {p.relative_to(root).as_posix()} has no Mitigation section")
    return errs, warns


def flag_problems(
    root: Path, data: object, max_days: int, today: dt.date | None = None, scan: bool = True
) -> tuple[list[str], list[str]]:
    """Feature-flag registry: owner, type, created/expires (release and experiment flags must expire within
    max_days); expired flags fail; flags read in code must be registered; registered but unread flags warn."""
    today = today or _today()
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("flags"), list):
        return ['needs {"flags": [ ... ]}'], warns
    keys: set[str] = set()
    for i, f in enumerate(data["flags"]):
        if not isinstance(f, dict):
            errs.append(f"flags[{i}]: must be an object")
            continue
        key = f.get("key")
        where = f"flag {key!r}" if isinstance(key, str) else f"flags[{i}]"
        if not isinstance(key, str) or not FLAG_KEY_RX.match(key):
            errs.append(f"{where}: key must be lower-case letters, digits, '_', '.', '-'")
            continue
        if key in keys:
            errs.append(f"{where}: duplicate key")
        keys.add(key)
        for k in ("owner", "description"):
            if not isinstance(f.get(k), str) or not f[k].strip():
                errs.append(f"{where}: {k} is required")
        typ = f.get("type")
        if typ not in FLAG_TYPES:
            errs.append(f"{where}: type must be one of {', '.join(FLAG_TYPES)}")
        pct = f.get("rollout_percent")
        if pct is not None and (isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0 <= pct <= 100):
            errs.append(f"{where}: rollout_percent must be a number from 0 to 100")
        elif pct is not None and not isinstance(f.get("default", False), bool):
            errs.append(f"{where}: rollout_percent only works on boolean flags")
        try:
            created = dt.date.fromisoformat(str(f.get("created")))
        except ValueError:
            errs.append(f"{where}: created must be an ISO date (YYYY-MM-DD)")
            continue
        exp = f.get("expires")
        if exp is None:
            if typ in ("release", "experiment"):
                errs.append(f"{where}: {typ} flags need an expires date (at most {max_days} days after created)")
            continue
        try:
            expires = dt.date.fromisoformat(str(exp))
        except ValueError:
            errs.append(f"{where}: expires must be an ISO date (YYYY-MM-DD)")
            continue
        if typ in ("release", "experiment") and (expires - created).days > max_days:
            errs.append(f"{where}: lives {(expires - created).days} days; {typ} flags may live {max_days} at most")
        if expires < today:
            errs.append(
                f"{where}: expired on {expires} (owner {f.get('owner', '?')}): remove the flag and its dead branch,"
                " or extend it in a reviewed PR"
            )
        elif (expires - today).days <= 7:
            warns.append(f"{where}: expires on {expires}")
    if scan and not errs:
        used = flag_uses(root)
        for k, locs in sorted(used.items()):
            if k not in keys:
                errs.append(f"flag {k!r} is read in {locs[0]} but not registered in the flags file")
        for k in sorted(keys - set(used)):
            warns.append(f"flag {k!r} is registered but never read in code: remove it")
    return errs, warns


def flag_uses(root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    files = git_out(root, "ls-files", "-co", "--exclude-standard").splitlines()
    for rel in files:
        if not CODE_EXT_RX.search(rel) or TEST_PATH_RX.search(rel) or "node_modules/" in rel or rel.startswith(".eos/"):
            continue
        p = root / rel
        try:
            if p.stat().st_size > 1_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in FLAG_USE_RX.finditer(text):
            out.setdefault(m.group(1), []).append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}")
    return out


def ops_problems(root: Path, cfg: dict | None = None) -> tuple[list[str], list[str]]:
    """All operations gates for the files that exist. Empty when the project has none of them."""
    cfg = cfg or ops_cfg(root)
    errs: list[str] = []
    warns: list[str] = []
    sf = root / cfg["slo_file"]
    if sf.is_file():
        try:
            data = json.loads(read(sf))
            e, w = slo_problems(root, data, cfg)
            errs += [f"{cfg['slo_file']}: {x}" for x in e]
            warns += [f"{cfg['slo_file']}: {x}" for x in w]
            gen = root / cfg["generated_rules"] if cfg["generated_rules"] else None
            alerting = any(isinstance(s, dict) and s.get("alerting", True) for s in data.get("slos", []))
            if e or gen is None:
                pass
            elif gen.is_file() and read(gen) != slo_alert_rules(data, cfg):
                errs.append(f"{cfg['generated_rules']}: out of date with {cfg['slo_file']}: run `eos ops alerts`")
            elif not gen.is_file() and alerting:
                warns.append(
                    "no burn-rate alerts generated: run `eos ops alerts` (alerting elsewhere? set"
                    ' "ops": {"generated_rules": ""} in .eos/config.json)'
                )
        except ValueError as exc:
            errs.append(f"{cfg['slo_file']}: invalid JSON ({exc})")
    e, w = alert_problems(root, alert_rule_files(root, cfg), cfg)
    errs += e
    warns += w
    ff = root / cfg["flags_file"]
    if ff.is_file():
        try:
            e, w = flag_problems(root, json.loads(read(ff)), int(cfg["flag_max_days"]))
        except ValueError as exc:
            e, w = [f"invalid JSON ({exc})"], []
        errs += [f"{cfg['flags_file']}: {x}" for x in e]
        warns += [f"{cfg['flags_file']}: {x}" for x in w]
    return errs, warns


def has_ops_files(root: Path, cfg: dict) -> bool:
    return any((root / cfg[k]).is_file() for k in OPS_CFG_FILES) or bool(alert_rule_files(root, cfg))


RUNBOOK_TEMPLATE = """# Runbook: {name}

Alert or SLO: `{name}` · Owner: @owner · Dashboard: <link> · Last reviewed: {today}

## Symptoms
What fires, what users see (errors, slowness, failed payments), which SLO burns.

## Impact
Who is affected and how badly; when to declare an incident (see docs/ops/incident-response.md).

## Diagnose
1. Open the dashboard; compare with the last deploy and feature-flag changes (`git log -5`, flag registry).
2. Check dependencies: database, cache, queue, payment/mobile-money provider status pages.
3. Read the logs filtered by `trace_id` of a failing request.

## Mitigation
1. Roll back the last deploy, or turn off the flag that changed (`ops/flags.json`).
2. If a dependency is down: degrade gracefully (queue payments, show a status banner), do not retry in a loop.
Commands go here, copy-pasteable. Never paste secrets; reference where they live.

## Escalate
Who to wake, how (phone, not chat), after how long.

## Afterwards
Write the timeline; postmortem from docs/postmortems/_template.md if users were affected.
"""


def cmd_ops(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = ops_cfg(root)
    sf = root / cfg["slo_file"]
    if args.action == "check":
        if not has_ops_files(root, cfg):
            print(
                f"eos ops: nothing to check (no {cfg['slo_file']}, {cfg['flags_file']} or alert rules in"
                f" {', '.join(cfg['alert_rules'])}); start with `eos scaffold ops`"
            )
            return 0
        errs, warns = ops_problems(root, cfg)
        for w in warns:
            print("  warn: " + w)
        for e in errs:
            print("  error: " + e)
        print(f"eos ops check: {'FAILED' if errs else 'OK'} ({len(errs)} errors, {len(warns)} warnings)")
        return 1 if errs else 0
    if args.action == "runbook":
        if not args.name or not SLO_ID_RX.match(args.name.lower()):
            eprint("usage: eos ops runbook <name> (lower-case letters, digits, dashes)")
            return 2
        p = root / cfg["runbook_dir"] / f"{args.name.lower()}.md"
        if p.exists():
            print(f"exists: {p.relative_to(root).as_posix()}")
            return 0
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            RUNBOOK_TEMPLATE.format(name=args.name, today=_today().isoformat()), encoding="utf-8", newline="\n"
        )
        print(f"wrote {p.relative_to(root).as_posix()}: fill in the commands and owner")
        return 0
    if not sf.is_file():
        eprint(f"no {cfg['slo_file']} (eos scaffold ops writes an example)")
        return 2
    try:
        data = json.loads(read(sf))
    except ValueError as exc:
        eprint(f"{cfg['slo_file']}: invalid JSON ({exc})")
        return 2
    errs, _ = slo_problems(root, data, cfg)
    if errs:
        for e in errs:
            print("  error: " + e)
        return 1
    if args.action == "budget":
        for s in data["slos"]:
            budget = 1 - float(s["objective"]) / 100
            mins = budget * s["window_days"] * 24 * 60
            print(
                f"  {s['id']:<28} {s['objective']}% over {s['window_days']}d → {mins:,.0f} min of full outage allowed"
            )
        return 0
    if not (args.out or cfg["generated_rules"]):
        eprint('ops.generated_rules is "" in .eos/config.json (alerting elsewhere); pass --out to write rules')
        return 2
    text = slo_alert_rules(data, cfg)
    out = root / (args.out or cfg["generated_rules"])
    if args.check:
        ok = out.is_file() and read(out) == text
        print(
            f"eos ops alerts: {'up to date' if ok else 'OUT OF DATE (run `eos ops alerts`)'}: {out.relative_to(root).as_posix()}"
        )
        return 0 if ok else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"wrote {out.relative_to(root).as_posix()} ({text.count('- alert:')} alerts); validate: promtool check rules {out}"
    )
    return 0


def ops_extras(root: Path, m: dict, c: dict, full: bool) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for operations, scaled to the lane. standard+: SLO/alert/flag gates in-process
    (milliseconds) when the project has those files. risky/--full: hadolint on changed Dockerfiles when it is
    installed; with --full also checkov on changed IaC folders. Missing tools become a note (CI runs them)."""
    results: list[tuple[str, int, str, float]] = []
    notes: list[str] = []
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return results, notes
    cfg = ops_cfg(root)
    if has_ops_files(root, cfg):
        t0 = time.time()
        errs, _ = ops_problems(root, cfg)
        results.append(("ops config (SLOs, alerts, flags)", 1 if errs else 0, "\n".join(errs), time.time() - t0))
    if not (full or c["risk"] in ("risky", "one-way-door")):
        return results, notes
    files = [f for f in c["files"] if (root / f).is_file()]
    docker = [f for f in files if re.search(r"(^|/)Dockerfile[^/]*$|\.dockerfile$", f)]
    if docker:
        if shutil.which("hadolint"):
            t0 = time.time()
            code, out = run(["hadolint", *docker], cwd=root, timeout=60)
            results.append(("hadolint", code, out, time.time() - t0))
        else:
            notes.append("Dockerfile changed: hadolint is not installed here; CI lints it (eos scaffold docker-*)")
    iac = sorted({str(Path(f).parent) for f in files if re.search(r"\.(tf|tofu|tfvars)$", f)})
    if iac:
        if full and shutil.which("checkov"):
            t0 = time.time()
            code, out = run(
                ["checkov", "--quiet", "--compact", "--framework", "terraform", *[x for d in iac for x in ("-d", d)]],
                cwd=root,
                timeout=300,
            )
            results.append(("checkov (IaC)", code, out, time.time() - t0))
        else:
            notes.append(
                "IaC changed: plan + checkov run in CI (eos scaffold iac); locally: `eos verify --full` with checkov"
                " installed, and `tofu plan` before asking a human to apply"
            )
    return results, notes


# ----------------------------------------------------------------------------- frontend gates (stage 7)
FRONTEND_DEFAULTS = {
    "i18n": {
        "dir": "",  # catalog folder; "" = auto-detect from I18N_DIRS
        "default_locale": "",  # "" = en, then fr, then the first locale found
        "code_dirs": ["src", "app", "components", "lib", "pages", "features"],
    },
    "bundle": {
        "dirs": [".next/static", "out/_next/static", "dist/assets", "dist/_expo/static", "build/static"],
        "baseline": ".eos/bundle-baseline.json",
        "max_growth_pct": 5,  # ratchet: fail when gzip JS or CSS grows more than this vs the reviewed baseline
        "min_growth_kib": 1,  # ...and by more than this many KiB (tiny files would trip the percentage)
        "budget_kib": {},  # optional absolute gzip budgets, e.g. {"js": 365}; no default number on purpose
    },
}
I18N_DIRS = ("messages", "locales", "src/messages", "src/locales", "public/locales", "src/i18n/messages", "i18n")
LOCALE_RX = _lazy_rx(r"^[a-z]{2,3}(?:[-_](?:[A-Z]{2}|[A-Za-z]{4}|\d{3}))?$")
I18N_IMPORT_RX = _lazy_rx(r"""from\s+["'](?:next-intl(?:/server)?|use-intl|react-i18next|i18next)["']""")
I18N_NS_RX = _lazy_rx(
    r"""(?:const|let)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*"""
    r"""(?:["'`]([\w.-]*)["'`]|\{[^}]*?namespace\s*:\s*["'`]([\w.-]*)["'`][^}]*\})?\s*\)"""
)
I18N_TFN_RX = _lazy_rx(r"""(?:const|let)\s+\{\s*t\s*\}\s*=\s*(?:useTranslation|i18n)\(\s*(?:["'`]([\w.-]*)["'`])?""")
ICU_COMPLEX = ("plural", "select", "selectordinal")


def frontend_cfg(root: Path) -> dict:
    f = _load_cfg(root).get("frontend", {})
    f = f if isinstance(f, dict) else {}
    out = {}
    for k, dflt in FRONTEND_DEFAULTS.items():
        v = f.get(k, {})
        out[k] = {**dflt, **(v if isinstance(v, dict) else {})}
    return out


def _flatten_messages(obj: object, prefix: str, out: dict[str, object], objs: set[str]) -> None:
    if isinstance(obj, dict):
        if prefix:
            objs.add(prefix)
        for k, v in obj.items():
            _flatten_messages(v, f"{prefix}.{k}" if prefix else str(k), out, objs)
    else:
        out[prefix] = obj


def _app_prefixes(root: Path) -> list[str]:
    """ "" plus each stack folder from the manifest (web/, apps/site/ ...), so monorepo apps are found too."""
    out = [""]
    for v in (load_manifest(root) or {}).get("stacks", {}).values():
        for d in as_dirs(v):
            if d not in (".", "") and d.rstrip("/") + "/" not in out:
                out.append(d.rstrip("/") + "/")
    return out


def i18n_catalogs(root: Path, cfg: dict) -> tuple[Path | None, dict[str, dict], list[str]]:
    """Find the catalog folder and load every locale: {locale: {"leaves": {key: value}, "objects": {key}}}.
    Layouts: <dir>/<locale>.json, or <dir>/<locale>/<namespace>.json (keys become "<namespace>.<key>")."""
    errs: list[str] = []
    cands = [cfg["i18n"]["dir"]] if cfg["i18n"]["dir"] else [px + c for px in _app_prefixes(root) for c in I18N_DIRS]
    for c in cands:
        d = root / c
        if not d.is_dir():
            continue
        files = {p.stem: [p] for p in sorted(d.glob("*.json")) if LOCALE_RX.match(p.stem)}
        nested = {
            p.name: sorted(p.glob("*.json")) for p in sorted(d.iterdir()) if p.is_dir() and LOCALE_RX.match(p.name)
        }
        nested = {k: v for k, v in nested.items() if v}
        layout = files or nested
        if not layout:
            continue
        cats: dict[str, dict] = {}
        for loc, paths in layout.items():
            leaves: dict[str, object] = {}
            objs: set[str] = set()
            for p in paths:
                try:
                    data = json.loads(read(p))
                except ValueError as exc:
                    errs.append(f"{p.relative_to(root).as_posix()}: invalid JSON ({exc})")
                    continue
                if not isinstance(data, dict):
                    errs.append(f"{p.relative_to(root).as_posix()}: top level must be an object")
                    continue
                _flatten_messages(data, p.stem if nested and not files else "", leaves, objs)
            cats[loc] = {"leaves": leaves, "objects": objs}
        return d, cats, errs
    return None, {}, errs


def icu_parse(msg: str) -> tuple[set[str], list[str]]:
    """Argument names used by an ICU message plus problems (unbalanced braces, plural/select without `other`).
    Small recursive parser: enough for completeness checks, not a full ICU implementation."""
    args: set[str] = set()
    probs: list[str] = []
    if "{{" in msg:  # i18next interpolation: {{name}}
        return set(re.findall(r"\{\{\s*-?\s*([\w.]+)", msg)), probs
    n = len(msg)

    def skip_quote(i: int) -> int:
        # ICU apostrophe quoting: '' is a literal ', '{...}' is literal text
        if msg.startswith("''", i):
            return i + 2
        if i + 1 < n and msg[i + 1] in "{}#|":
            j = msg.find("'", i + 1)
            return n if j < 0 else j + 1
        return i + 1

    def message(i: int, depth: int) -> int:
        while i < n:
            ch = msg[i]
            if ch == "'":
                i = skip_quote(i)
            elif ch == "{":
                i = argument(i + 1, depth)
            elif ch == "}":
                if depth == 0:
                    probs.append("unbalanced '}'")
                    i += 1
                else:
                    return i
            else:
                i += 1
        if depth:
            probs.append("unclosed '{'")
        return i

    def argument(i: int, depth: int) -> int:
        j = i
        while j < n and msg[j] not in ",}":
            j += 1
        name = msg[i:j].strip()
        if name:
            args.add(name)
        if j >= n:
            probs.append("unclosed '{'")
            return n
        if msg[j] == "}":
            return j + 1
        k = j + 1
        while k < n and msg[k] not in ",}":
            k += 1
        kind = msg[j + 1 : k].strip()
        if k >= n:
            probs.append("unclosed '{'")
            return n
        if kind not in ICU_COMPLEX:  # {n, number}, {d, date, short}: skip to the matching brace
            lvl, p = 1, k
            while p < n and lvl:
                lvl += {"{": 1, "}": -1}.get(msg[p], 0)
                p += 1
            if lvl:
                probs.append("unclosed '{'")
            return p
        if msg[k] == "}":
            probs.append(f"{{{name}, {kind}}} has no branches")
            return k + 1
        p = k + 1
        selectors: list[str] = []
        while p < n:
            while p < n and msg[p] in " \t\n\r":
                p += 1
            if p >= n:
                break
            if msg[p] == "}":
                p += 1
                break
            s0 = p
            while p < n and msg[p] not in "{} \t\n\r":
                p += 1
            sel = msg[s0:p]
            if sel.startswith("offset:"):
                continue
            while p < n and msg[p] in " \t\n\r":
                p += 1
            if p >= n or msg[p] != "{":
                probs.append(f"{name}: expected '{{' after '{sel}'")
                return n
            selectors.append(sel)
            p = message(p + 1, depth + 1)
            if p < n and msg[p] == "}":
                p += 1
        else:
            probs.append("unclosed '{'")
        if "other" not in selectors:
            probs.append(f"{{{name}, {kind}}} has no 'other' branch")
        return p

    message(0, 0)
    return args, probs


def i18n_code_keys(root: Path, cfg: dict) -> list[tuple[str, str, bool]]:
    """(file:line, full key) for literal t('key') calls in files that import next-intl/use-intl/i18next."""
    found: list[tuple[str, str, bool]] = []
    for d in dict.fromkeys(px + c for px in _app_prefixes(root) for c in cfg["i18n"]["code_dirs"]):
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or not re.search(r"\.[cm]?[jt]sx?$", p.name) or "node_modules" in p.parts:
                continue
            try:
                src = read(p)
            except (OSError, UnicodeDecodeError):
                continue
            if not I18N_IMPORT_RX.search(src):
                continue
            fns: dict[str, tuple[str, bool]] = {}  # variable -> (namespace, i18next style)
            for m in I18N_NS_RX.finditer(src):
                fns[m.group(1)] = (m.group(2) or m.group(3) or "", False)
            for m in I18N_TFN_RX.finditer(src):
                fns["t"] = (m.group(1) or "", True)
            for var, (ns, i18next) in fns.items():
                call = re.compile(rf"""(?<![\w.]){re.escape(var)}(?:\.(?:rich|markup|raw))?\(\s*["']([\w.:-]+)["']""")
                for m in call.finditer(src):
                    key = m.group(1)
                    if i18next:
                        nsp, _, rest = key.rpartition(":")
                        full = ".".join(x for x in (nsp or ns, rest) if x)
                    else:
                        full = f"{ns}.{key}" if ns else key
                    line = src.count("\n", 0, m.start()) + 1
                    found.append((f"{p.relative_to(root).as_posix()}:{line}", full, i18next))
    return found


def i18n_problems(root: Path, cfg: dict | None = None) -> tuple[list[str], list[str], str]:
    """Translation completeness: missing keys per locale, leaf/object clashes, empty values, ICU argument
    mismatches, plural/select without `other`, i18next plural keys without `_other`, keys used in code but
    absent from every catalog. Returns (errors, warnings, summary)."""
    cfg = cfg or frontend_cfg(root)
    d, cats, errs = i18n_catalogs(root, cfg)
    warns: list[str] = []
    if d is None:
        return errs, warns, "no translation catalogs found"
    rel = d.relative_to(root).as_posix()
    locales = sorted(cats)
    want = cfg["i18n"]["default_locale"]
    ref = want if want in cats else next((x for x in ("en", "fr") if x in cats), locales[0] if locales else "")
    if want and want not in cats:
        errs.append(f"{rel}: default_locale '{want}' has no catalog (found: {', '.join(locales)})")
    if len(locales) < 2:
        warns.append(f"{rel}: only one locale ({', '.join(locales)}); nothing to compare yet")
    union = set().union(*(set(c["leaves"]) for c in cats.values())) if cats else set()
    objs = set().union(*(c["objects"] for c in cats.values())) if cats else set()
    for k in sorted(union & objs):
        has_leaf = [lc for lc in locales if k in cats[lc]["leaves"]]
        has_obj = [lc for lc in locales if k in cats[lc]["objects"]]
        errs.append(f"{rel}: '{k}' is text in {','.join(has_leaf)} but a group in {','.join(has_obj)}")
    for lc in locales:
        leaves = cats[lc]["leaves"]
        clash = {k for k in leaves if k in objs}  # reported above; don't repeat every child key
        missing = sorted(
            k
            for k in union - set(leaves)
            if k not in cats[lc]["objects"] and not any(k.startswith(c + ".") for c in clash)
        )
        for k in missing[:50]:
            src = next((o for o in locales if k in cats[o]["leaves"]), "?")
            errs.append(f"{rel}: [{lc}] missing '{k}' (present in {src})")
        if len(missing) > 50:
            errs.append(f"{rel}: [{lc}] … and {len(missing) - 50} more missing keys")
        for k, v in sorted(leaves.items()):
            if isinstance(v, str) and not v.strip():
                errs.append(f"{rel}: [{lc}] '{k}' is empty")
            elif isinstance(v, str):
                _, probs = icu_parse(v)
                errs += [f"{rel}: [{lc}] '{k}': {p}" for p in probs]
            m = re.match(r"^(.*)_(zero|one|two|few|many|other)$", k)
            if m and not any(x.startswith(m.group(1) + "_other") for x in leaves):
                errs.append(f"{rel}: [{lc}] '{k}' has no '{m.group(1)}_other' sibling (i18next plural)")
    if ref:
        for k, v in sorted(cats[ref]["leaves"].items()):
            if not isinstance(v, str):
                continue
            a_ref, _ = icu_parse(v)
            for lc in locales:
                ov = cats[lc]["leaves"].get(k)
                if lc == ref or not isinstance(ov, str) or not ov.strip():
                    continue
                a_o, _ = icu_parse(ov)
                if a_o != a_ref:
                    errs.append(
                        f"{rel}: '{k}' arguments differ: {ref} {{{', '.join(sorted(a_ref)) or '-'}}}"
                        f" vs {lc} {{{', '.join(sorted(a_o)) or '-'}}}"
                    )
    known = union | objs
    for where, key, i18next in i18n_code_keys(root, cfg):
        if key in known:
            continue
        if i18next and any(k.endswith("." + key) or k.startswith(key + "_") or ("." + key + "_") in k for k in known):
            continue  # i18next: default namespace prefix and plural suffixes (key_one, key_other)
        errs.append(f"{where}: t('{key}') not found in {rel}")
    return errs, warns, f"{rel}: {len(locales)} locales ({', '.join(locales)}), {len(union)} keys, reference {ref}"


def cmd_i18n(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    errs, warns, summary = i18n_problems(root)
    if summary == "no translation catalogs found" and not errs:
        print(
            "eos i18n: no catalogs found (looked in " + ", ".join(I18N_DIRS) + "); start with `eos scaffold i18n`"
            ' or set "frontend": {"i18n": {"dir": "..."}} in .eos/config.json'
        )
        return 0
    for w in warns:
        print("  warn: " + w)
    for e in errs:
        print("  error: " + e)
    print(f"eos i18n check: {'FAILED' if errs else 'OK'} ({summary}; {len(errs)} errors)")
    return 1 if errs else 0


def bundle_measure(root: Path, cfg: dict) -> tuple[str, dict[str, int], float] | None:
    """gzip size (level 9, deterministic) of emitted JS and CSS in the first build-output folder found."""
    for d in [px + c for px in _app_prefixes(root) for c in cfg["bundle"]["dirs"]]:
        base = root / d
        if not base.is_dir():
            continue
        sizes = {"js": 0, "css": 0, "files": 0}
        newest = 0.0
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.is_symlink():
                continue
            kind = "js" if re.search(r"\.[cm]?js$", p.name) else "css" if p.name.endswith(".css") else ""
            if not kind:
                continue
            sizes[kind] += len(gzip.compress(p.read_bytes(), compresslevel=9, mtime=0))
            sizes["files"] += 1
            newest = max(newest, p.stat().st_mtime)
        if sizes["files"]:
            return d, sizes, newest
    return None


def bundle_problems(root: Path, cfg: dict, measured: tuple[str, dict[str, int], float]) -> tuple[list[str], list[str]]:
    d, cur, _ = measured
    errs: list[str] = []
    lines: list[str] = []
    bpath = root / cfg["bundle"]["baseline"]
    base: dict = {}
    if bpath.is_file():
        try:
            base = json.loads(read(bpath))
        except ValueError as exc:
            errs.append(f"{cfg['bundle']['baseline']}: invalid JSON ({exc})")
    tol = float(cfg["bundle"]["max_growth_pct"])
    for kind in ("js", "css"):
        now = cur[kind]
        msg = f"{kind}: {now / 1024:,.1f} KiB gzip"
        old = base.get(kind) if base.get("dir", d) == d else None
        if isinstance(old, int) and old > 0:
            pct = (now - old) / old * 100
            msg += f" ({pct:+.1f}% vs baseline {old / 1024:,.1f} KiB)"
            if pct > tol and now - old > float(cfg["bundle"]["min_growth_kib"]) * 1024:
                errs.append(
                    f"{d}: {kind} grew {pct:.1f}% (> {tol:g}% allowed): find the cause with your bundle analyzer"
                    " (`next analyze`), or accept it in review with `eos bundle-size --update`"
                )
        budget = cfg["bundle"]["budget_kib"].get(kind) if isinstance(cfg["bundle"]["budget_kib"], dict) else None
        if _num(budget) and now > budget * 1024:
            errs.append(f"{d}: {kind} {now / 1024:,.1f} KiB gzip > budget {budget} KiB")
        lines.append(msg)
    if not base:
        lines.append("no baseline yet: run `eos bundle-size --update` after review to start the ratchet")
    return errs, lines


def cmd_bundle_size(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = frontend_cfg(root)
    measured = bundle_measure(root, cfg)
    if not measured:
        print("eos bundle-size: no build output found (" + ", ".join(cfg["bundle"]["dirs"]) + "); build first")
        return 0 if not args.update else 2
    d, cur, _ = measured
    if args.update:
        out = root / cfg["bundle"]["baseline"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"dir": d, **cur, "updated": _today().isoformat()}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"wrote {out.relative_to(root).as_posix()}: js {cur['js'] / 1024:,.1f} KiB, css {cur['css'] / 1024:,.1f} KiB gzip"
        )
        return 0
    errs, lines = bundle_problems(root, cfg, measured)
    print(f"eos bundle-size: {d} ({cur['files']} files)")
    for ln in lines:
        print("  " + ln)
    for e in errs:
        print("  error: " + e)
    return 1 if errs else 0


def frontend_extras(root: Path, m: dict, c: dict, full: bool) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for web frontends, scaled to the lane. standard+: translation completeness
    in-process when catalogs exist. risky/--full: the gzip bundle ratchet, only when a build output is newer
    than the changed files (a stale build would measure the wrong code); otherwise a note."""
    results: list[tuple[str, int, str, float]] = []
    notes: list[str] = []
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return results, notes
    cfg = frontend_cfg(root)
    t0 = time.time()
    errs, _, summary = i18n_problems(root, cfg)
    if summary != "no translation catalogs found" or errs:
        results.append(("i18n catalogs", 1 if errs else 0, "\n".join(errs), time.time() - t0))
    if not (full or c["risk"] in ("risky", "one-way-door")):
        return results, notes
    web = [f for f in c["files"] if re.search(r"\.([cm]?[jt]sx?|css|scss)$|(^|/)package\.json$", f)]
    if not web:
        return results, notes
    t0 = time.time()
    measured = bundle_measure(root, cfg)
    newest_change = max(((root / f).stat().st_mtime for f in web if (root / f).is_file()), default=0.0)
    if not measured:
        notes.append("client code changed: build, then `eos bundle-size` (gzip ratchet vs .eos/bundle-baseline.json)")
    elif measured[2] < newest_change:
        notes.append(f"{measured[0]} is older than your changes: rebuild, then `eos bundle-size`")
    else:
        errs, lines = bundle_problems(root, cfg, measured)
        results.append(("bundle size (gzip ratchet)", 1 if errs else 0, "\n".join(errs + lines), time.time() - t0))
    return results, notes


# ----------------------------------------------------------------------------- mobile gates (stage 9)
# OWASP MASVS-based checks of what ships in the app package: Android manifest + network security config, iOS
# Info.plist (ATS), Expo app config, public (bundled) env names; plus an app-size budget/ratchet on built artefacts.
MOBILE_DEFAULTS = {
    "allow": {},  # {"MOB001": "why this app needs Android backup (reviewed by …)"}: a reason is required
    "artifacts": ["**/*.aab", "**/*.apk", "**/*.ipa"],  # built packages for `eos mobile size`
    "size_baseline": ".eos/app-size-baseline.json",
    "size_budget_mb": {},  # optional absolute budgets per kind, e.g. {"aab": 30, "ipa": 60}; no default number
    "max_growth_pct": 5,  # ratchet: fail when a package grows more than this vs the reviewed baseline...
    "min_growth_kb": 100,  # ...and by more than this many KB
    "public_env_prefixes": ["EXPO_PUBLIC_"],  # inlined into the JS bundle at build time (readable by anyone)
}
MOBILE_SKIP_DIRS = {
    "node_modules", ".git", ".next", "dist", "build", "out", "coverage", ".expo", ".turbo", ".eos", "vendor",
    "Pods", ".gradle", "intermediates", "generated", "DerivedData", ".dart_tool",
}  # fmt: skip
MOBILE_RULES = {
    "MOB000": "mobile config file could not be parsed (fix it so the other rules can run)",
    "MOB001": "Android backup on: tokens and databases can be copied off the device (MASVS-STORAGE-2)",
    "MOB002": "cleartext HTTP allowed (MASVS-NETWORK-1)",
    "MOB003": "debuggable release build (MASVS-RESILIENCE-4; stores reject debuggable apps)",
    "MOB004": "exported component without a permission (MASVS-PLATFORM-1)",
    "MOB005": "component with an intent filter but no android:exported (install fails on Android 12+)",
    "MOB006": "iOS App Transport Security disabled: NSAllowsArbitraryLoads (MASVS-NETWORK-1)",
    "MOB007": "secret-looking name in a public, bundled env variable (the bundle is public; MASVS-CRYPTO-2)",
    "MOB008": "expo-updates without a runtimeVersion policy (an OTA update could reach an incompatible binary)",
    "MOB009": "custom-scheme or http deep link without a verified https App Link (link hijacking, MASVS-PLATFORM-1)",
}
MOBILE_WARN_ONLY = {"MOB000", "MOB008", "MOB009"}
SECRET_ENV_RX = _lazy_rx(r"(SECRET|PRIVATE|PASSWORD|PASSWD|SERVICE_ROLE|SIGNING|CREDENTIAL)", re.IGNORECASE)
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def mobile_cfg(root: Path) -> dict:
    m = _load_cfg(root).get("mobile", {})
    m = m if isinstance(m, dict) else {}
    out = {k: m.get(k, v) for k, v in MOBILE_DEFAULTS.items()}
    if not isinstance(out["allow"], dict):
        out["allow"] = {}
    return out


def _mobile_walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in MOBILE_SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            yield Path(dirpath) / f


def mobile_files(root: Path) -> dict[str, list[Path]]:
    """Mobile config files that end up in a shipped app. Debug-only Android source sets are skipped."""
    out: dict[str, list[Path]] = {"manifest": [], "netsec": [], "plist": [], "expo": [], "env": []}
    for p in _mobile_walk(root):
        rel = p.relative_to(root).as_posix()
        name = p.name
        if name == "AndroidManifest.xml" and not re.search(r"(^|/)src/(debug|androidTest|test)/", rel):
            out["manifest"].append(p)
        elif name.endswith(".xml") and "/res/xml/" in f"/{rel}" and "/src/debug/" not in f"/{rel}":
            try:
                if "<network-security-config" in read(p):
                    out["netsec"].append(p)
            except (OSError, UnicodeDecodeError):
                pass
        elif name == "Info.plist" and "/ios/" in f"/{rel}" or name == "Info.plist" and rel.count("/") <= 2:
            out["plist"].append(p)
        elif name in ("app.json", "app.config.js", "app.config.ts", "app.config.mjs", "app.config.cjs"):
            out["expo"].append(p)
        elif name == "eas.json":
            out["env"].append(p)
    rc, tracked = run(["git", "ls-files", "--", ".env*", "**/.env*"], cwd=root, timeout=10)
    if rc == 0:  # committed env files only (a local .env is not read)
        out["env"] += [root / t for t in tracked.splitlines() if t and (root / t).is_file()]
    return out


def has_mobile_files(root: Path) -> bool:
    f = mobile_files(root)
    return bool(f["manifest"] or f["plist"] or _expo_configs(f["expo"]))


def _expo_configs(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        try:
            text = read(p)
        except (OSError, UnicodeDecodeError):
            continue
        if p.name == "app.json" and '"expo"' not in text:
            continue  # some other tool's app.json
        out.append(p)
    return out


def _xml_root(p: Path):
    import xml.etree.ElementTree as ET  # stdlib; manifests are trusted project files, no entity expansion needed

    try:
        return ET.fromstring(read(p))
    except (ET.ParseError, OSError, UnicodeDecodeError, ValueError):
        return None


def _manifest_findings(root: Path, p: Path) -> list[tuple[str, str]]:
    rel = p.relative_to(root).as_posix()
    doc = _xml_root(p)
    if doc is None:
        return []
    a = ANDROID_NS
    out: list[tuple[str, str]] = []
    app = doc.find("application")
    if app is not None:
        backup = app.get(a + "allowBackup")
        rules = app.get(a + "dataExtractionRules") or app.get(a + "fullBackupContent")
        launcher = any(
            any(x.get(a + "name") == "android.intent.action.MAIN" for x in f.findall("action"))
            and any(x.get(a + "name") == "android.intent.category.LAUNCHER" for x in f.findall("category"))
            for f in app.iter("intent-filter")
        )  # the app module's manifest (library manifests are merged into it and inherit its value)
        if not rules and (backup == "true" or backup is None and launcher):
            out.append(("MOB001", (f'{rel}: set android:allowBackup="false", or keep it and add dataExtractionRules'
                        " (Android 12+) / fullBackupContent excluding tokens and databases")))  # fmt: skip
        if app.get(a + "usesCleartextTraffic") == "true":
            out.append(
                ("MOB002", f'{rel}: android:usesCleartextTraffic="true" (HTTPS only; the default from Android 9)')
            )
        if app.get(a + "debuggable") == "true":
            out.append(("MOB003", f'{rel}: android:debuggable="true" (let the build type decide; never in release)'))
        for comp in list(app):
            tag = comp.tag
            if tag not in ("activity", "activity-alias", "service", "receiver", "provider"):
                continue
            cname = comp.get(a + "name", "?")
            exported = comp.get(a + "exported")
            filters = comp.findall("intent-filter")
            if filters and exported is None:
                out.append(("MOB005", f"{rel}: <{tag} {cname}> has an intent-filter but no android:exported"))
            perm = comp.get(a + "permission") or comp.get(a + "readPermission") or comp.get(a + "writePermission")
            if exported == "true" and tag in ("service", "receiver", "provider") and not perm:
                out.append(("MOB004", (f'{rel}: <{tag} {cname}> android:exported="true" without android:permission'
                            " (export only what other apps must reach, and protect it)")))  # fmt: skip
            for f in filters:
                acts = {x.get(a + "name") for x in f.findall("action")}
                cats = {x.get(a + "name") for x in f.findall("category")}
                if "android.intent.action.VIEW" not in acts or "android.intent.category.BROWSABLE" not in cats:
                    continue
                schemes = {x.get(a + "scheme") for x in f.findall("data") if x.get(a + "scheme")}
                verified = f.get(a + "autoVerify") == "true" and "https" in schemes
                if schemes and not verified:
                    out.append(("MOB009", (f"{rel}: <{tag} {cname}> deep link ({', '.join(sorted(schemes))}) is not a"
                                ' verified App Link: use https + android:autoVerify="true" for links that carry'
                                " tokens or open sensitive screens")))  # fmt: skip
    return out


def _netsec_findings(root: Path, p: Path) -> list[tuple[str, str]]:
    rel = p.relative_to(root).as_posix()
    doc = _xml_root(p)
    if doc is None:
        return []
    out = []
    base = doc.find("base-config")
    if base is not None and base.get("cleartextTrafficPermitted") == "true":
        out.append(("MOB002", f'{rel}: base-config cleartextTrafficPermitted="true" (all hosts over HTTP)'))
    for dc in doc.iter("domain-config"):
        if dc.get("cleartextTrafficPermitted") != "true":
            continue
        hosts = [(d.text or "").strip() for d in dc.findall("domain")]
        if hosts and all(h in ("localhost", "127.0.0.1", "10.0.2.2", "10.0.3.2") for h in hosts):
            continue  # local development hosts only
        out.append(("MOB002", f"{rel}: cleartext allowed for {', '.join(hosts) or 'a domain-config'}"))
    for trust in doc.iter("certificates"):
        if trust.get("src") == "user" and not any(e.tag == "debug-overrides" for e in doc.iter()):
            out.append(
                ("MOB002", f'{rel}: trusts user-installed CAs (<certificates src="user">) outside debug-overrides')
            )
    return out


def _plist_ats(text: str) -> bool:
    m = re.search(r"<key>\s*NSAllowsArbitraryLoads\s*</key>\s*<true\s*/>", text)
    return bool(m)


def _expo_flags(p: Path) -> dict:
    """What one Expo config file says. JSON is parsed; JS/TS configs are read as text (never executed)."""
    text = read(p)
    if p.suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as exc:
            return {"invalid": str(exc), "text": text}
        cfg = data.get("expo", data) if isinstance(data, dict) else {}
        android = cfg.get("android") if isinstance(cfg.get("android"), dict) else {}
        ios = cfg.get("ios") if isinstance(cfg.get("ios"), dict) else {}
        plist = ios.get("infoPlist") if isinstance(ios.get("infoPlist"), dict) else {}
        ats = plist.get("NSAppTransportSecurity") if isinstance(plist.get("NSAppTransportSecurity"), dict) else {}
        return {
            "backup_off": android.get("allowBackup") is False,
            "cleartext": '"usesCleartextTraffic": true' in json.dumps(cfg.get("plugins", [])),
            "ats_off": ats.get("NSAllowsArbitraryLoads") is True,
            "runtime": "runtimeVersion" in cfg,
            "android": "android" in json.dumps(cfg.get("platforms", ["android"])),
            "text": text,
        }
    return {
        "backup_off": bool(re.search(r"allowBackup\s*:\s*false", text)),
        "cleartext": bool(re.search(r"usesCleartextTraffic\s*:\s*true", text)),
        "ats_off": bool(re.search(r"NSAllowsArbitraryLoads\s*:\s*true", text)),
        "runtime": "runtimeVersion" in text,
        "android": True,
        "text": text,
    }


def _expo_findings(root: Path, paths: list[Path], cfg: dict) -> list[tuple[str, str]]:
    """One app = app.json and/or app.config.* in the same folder (the dynamic config extends app.json), so
    'is backup off' and 'is there a runtimeVersion' are answered across both files."""
    out: list[tuple[str, str]] = []
    by_dir: dict[Path, list[Path]] = {}
    for p in paths:
        by_dir.setdefault(p.parent, []).append(p)
    for d, ps in sorted(by_dir.items()):
        flags = {p: _expo_flags(p) for p in sorted(ps)}
        rel_main = next((p for p in flags if p.name != "app.json"), min(ps)).relative_to(root).as_posix()
        for p, f in flags.items():
            rel = p.relative_to(root).as_posix()
            if "invalid" in f:
                out.append(("MOB000", f"{rel}: invalid JSON ({f['invalid']})"))
            if f.get("cleartext"):
                out.append(("MOB002", f"{rel}: expo-build-properties usesCleartextTraffic: true (HTTPS only)"))
            if f.get("ats_off"):
                out.append(("MOB006", f"{rel}: ios.infoPlist NSAppTransportSecurity.NSAllowsArbitraryLoads is true"))
            out += [("MOB007", f"{rel}: {n}") for n in _public_secret_names(f["text"], cfg["public_env_prefixes"])]
        valid = [f for f in flags.values() if "invalid" not in f]
        if valid and any(f["android"] for f in valid) and not any(f["backup_off"] for f in valid):
            out.append(("MOB001", (f"{rel_main}: set android.allowBackup to false (Expo keeps Android's default,"
                        " true), or allow MOB001 with a reason and back up only safe data")))  # fmt: skip
        if valid and "expo-updates" in _pkg_deps(root, ps[0]) and not any(f["runtime"] for f in valid):
            out.append(("MOB008", (f'{rel_main}: expo-updates is installed but no runtimeVersion'
                        ' (e.g. {"policy": "appVersion"})')))  # fmt: skip
    return out


def _public_secret_names(text: str, prefixes: list[str]) -> list[str]:
    names = set()
    for pre in prefixes:
        for m in re.finditer(rf"\b({re.escape(pre)}[A-Z0-9_]+)", text):
            if SECRET_ENV_RX.search(m.group(1)[len(pre) :]):
                names.add(m.group(1))
    return [f"{n} is inlined into the app bundle; keep secrets on your server" for n in sorted(names)]


def _pkg_deps(root: Path, near: Path) -> dict:
    for d in [near.parent, *near.parents]:
        pj = d / "package.json"
        if pj.is_file():
            try:
                pkg = json.loads(read(pj))
            except (OSError, ValueError):
                return {}
            return {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if d == root:
            break
    return {}


def mobile_problems(root: Path, cfg: dict | None = None, only: list[str] | None = None) -> dict:
    """Findings → errors (or warnings for MOB008/MOB009), minus rules allowed with a reason in config.
    `only`: relative paths to restrict to (changed files); None = everything."""
    cfg = cfg or mobile_cfg(root)
    files = mobile_files(root)
    raw: list[tuple[str, str]] = []
    checked = 0

    def want(p: Path) -> bool:
        return only is None or p.relative_to(root).as_posix() in only

    for p in files["manifest"]:
        if want(p):
            checked += 1
            raw += _manifest_findings(root, p)
    for p in files["netsec"]:
        if want(p):
            checked += 1
            raw += _netsec_findings(root, p)
    for p in files["plist"]:
        if want(p):
            checked += 1
            try:
                if _plist_ats(read(p)):
                    raw.append(("MOB006", f"{p.relative_to(root).as_posix()}: NSAllowsArbitraryLoads is true"))
            except (OSError, UnicodeDecodeError):
                pass
    expo = [p for p in _expo_configs(files["expo"]) if want(p)]
    checked += len(expo)
    raw += _expo_findings(root, expo, cfg)
    for p in files["env"]:
        if want(p):
            try:
                text = read(p)
            except (OSError, UnicodeDecodeError):
                continue
            checked += 1
            rel = p.relative_to(root).as_posix()
            raw += [("MOB007", f"{rel}: {n}") for n in _public_secret_names(text, cfg["public_env_prefixes"])]
    errs, warns, allowed = [], [], []
    for rid, reason in cfg["allow"].items():
        if rid not in MOBILE_RULES:
            warns.append(f"mobile.allow: unknown rule {rid}")
        elif not str(reason).strip():
            errs.append(f"mobile.allow.{rid}: give a reason (who reviewed it and why the app needs it)")
    for rid, msg in raw:
        if str(cfg["allow"].get(rid, "")).strip():
            allowed.append(rid)
            continue
        line = f"{rid} {msg}"
        (warns if rid in MOBILE_WARN_ONLY else errs).append(line)
    return {"errors": errs, "warnings": warns, "files": checked, "allowed": sorted(set(allowed))}


MOBILE_CHANGE_RX = _lazy_rx(
    r"(^|/)(AndroidManifest\.xml|Info\.plist|app\.json|app\.config\.[cm]?[jt]s|eas\.json|\.env[^/]*)$|/res/xml/[^/]+\.xml$"
)


def app_size_measure(root: Path, cfg: dict) -> dict[str, dict]:
    """Newest artefact per kind (aab, apk, ipa) with its size and the biggest parts inside the zip."""
    import zipfile

    best: dict[str, Path] = {}
    for g in cfg["artifacts"]:
        for p in root.glob(g):
            parts = set(p.relative_to(root).parts)
            if not p.is_file() or p.is_symlink() or parts & {"node_modules", ".git", "Pods"}:
                continue
            kind = p.suffix.lstrip(".").lower()
            if kind not in ("aab", "apk", "ipa"):
                continue
            if kind not in best or p.stat().st_mtime > best[kind].stat().st_mtime:
                best[kind] = p
    out: dict[str, dict] = {}
    for kind, p in best.items():
        groups: dict[str, int] = {}
        try:
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    n = info.filename
                    if kind == "ipa":
                        segs = n.split("/")
                        key = "/".join(segs[2:3]) if len(segs) > 2 else n  # Payload/X.app/<part>
                    elif n.startswith(("lib/", "base/lib/")):
                        segs = n.split("/")
                        key = "/".join(segs[: 3 if n.startswith("base/") else 2])  # per ABI
                    elif re.search(r"(^|/)classes\d*\.dex$", n) or n.startswith("base/dex/"):
                        key = "dex (code)"
                    else:
                        key = "/".join(n.split("/")[: 2 if n.startswith("base/") else 1])
                    groups[key] = groups.get(key, 0) + info.compress_size
        except (zipfile.BadZipFile, OSError):
            groups = {}
        out[kind] = {
            "path": p.relative_to(root).as_posix(),
            "bytes": p.stat().st_size,
            "mtime": p.stat().st_mtime,
            "top": sorted(groups.items(), key=lambda kv: -kv[1])[:6],
        }
    return out


def app_size_problems(root: Path, cfg: dict, measured: dict[str, dict]) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    lines: list[str] = []
    base: dict = {}
    bpath = root / cfg["size_baseline"]
    if bpath.is_file():
        try:
            base = json.loads(read(bpath))
        except ValueError as exc:
            errs.append(f"{cfg['size_baseline']}: invalid JSON ({exc})")
    budgets = cfg["size_budget_mb"] if isinstance(cfg["size_budget_mb"], dict) else {}
    tol = float(cfg["max_growth_pct"])
    for kind, m in sorted(measured.items()):
        now = m["bytes"]
        msg = f"{kind}: {now / 1e6:,.2f} MB ({m['path']})"
        old = (base.get(kind) or {}).get("bytes") if isinstance(base.get(kind), dict) else None
        if isinstance(old, int) and old > 0:
            pct = (now - old) / old * 100
            msg += f" {pct:+.1f}% vs baseline {old / 1e6:,.2f} MB"
            if pct > tol and now - old > float(cfg["min_growth_kb"]) * 1000:
                errs.append(
                    f"{kind} grew {pct:.1f}% (> {tol:g}% allowed): check the size breakdown and new dependencies,"
                    " or accept it in review with `eos mobile size --update`"
                )
        budget = budgets.get(kind)
        if _num(budget) and now > float(budget) * 1e6:
            errs.append(f"{kind}: {now / 1e6:,.2f} MB > budget {budget} MB")
        lines.append(msg)
        lines += [f"    {k:<28} {v / 1e6:8.2f} MB (compressed)" for k, v in m["top"]]
    if "aab" in measured:
        lines.append("note: an .aab is not the download size; Play serves per-device APKs (bundletool get-size total)")
    if not base and measured:
        lines.append("no baseline yet: run `eos mobile size --update` after review to start the ratchet")
    return errs, lines


def cmd_mobile(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = mobile_cfg(root)
    if args.action == "check":
        res = mobile_problems(root, cfg)
        if args.json:
            print(json.dumps(res, indent=1))
            return 1 if res["errors"] or (args.strict and res["warnings"]) else 0
        for w in res["warnings"]:
            print("  warn: " + w)
        for e in res["errors"]:
            print("  error: " + e)
        failed = bool(res["errors"]) or (args.strict and bool(res["warnings"]))
        allowed = f"; allowed by config: {', '.join(res['allowed'])}" if res["allowed"] else ""
        print(
            f"eos mobile check: {'FAILED' if failed else 'OK'} ({res['files']} files; {len(res['errors'])} errors,"
            f" {len(res['warnings'])} warnings{allowed})"
        )
        if not res["files"]:
            print("  no mobile config found (AndroidManifest.xml, Info.plist, Expo app.json/app.config.*)")
        elif res["errors"] or res["warnings"]:
            print("  rules: `eos mobile rules`; refs: .eos/packs/ref/mobile/security-masvs.md")
        return 1 if failed else 0
    if args.action == "rules":
        for rid, what in MOBILE_RULES.items():
            print(f"  {rid}{' (warn)' if rid in MOBILE_WARN_ONLY else ''}  {what}")
        print('  allow one with a reason: "mobile": {"allow": {"MOB001": "why, reviewed by whom"}} in .eos/config.json')
        return 0
    measured = app_size_measure(root, cfg)
    if not measured:
        print("eos mobile size: no .aab/.apk/.ipa found (build a release first; config mobile.artifacts)")
        return 2 if args.update else 0
    if args.update:
        out = root / cfg["size_baseline"]
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {k: {"bytes": v["bytes"], "path": v["path"]} for k, v in measured.items()}
        out.write_text(
            json.dumps({**data, "updated": _today().isoformat()}, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(
            f"wrote {out.relative_to(root).as_posix()}: "
            + ", ".join(f"{k} {v['bytes'] / 1e6:,.2f} MB" for k, v in data.items())
        )
        return 0
    errs, lines = app_size_problems(root, cfg, measured)
    print("eos mobile size:")
    for ln in lines:
        print("  " + ln)
    for e in errs:
        print("  error: " + e)
    return 1 if errs else 0


def mobile_extras(root: Path, m: dict, c: dict, full: bool) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for mobile apps. standard+: the manifest/app-config check (in-process, ms) when a
    mobile config file changed (all files on risky or --full). risky/--full: the app-size ratchet, only when a
    built package is newer than the changed files; otherwise a note. Trivial and spike lanes add nothing."""
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return [], []
    changed = [f for f in c["files"] if MOBILE_CHANGE_RX.search(f)]
    if not changed and not full:
        return [], []
    cfg = mobile_cfg(root)
    t0 = time.time()
    wide = full or c["risk"] in ("risky", "one-way-door")
    res = mobile_problems(root, cfg, None if wide else changed)
    results: list[tuple[str, int, str, float]] = []
    notes = [f"mobile: {w}" for w in res["warnings"][:6]]
    if res["files"]:
        results.append(("mobile config (MASVS)", 1 if res["errors"] else 0, "\n".join(res["errors"]), time.time() - t0))
    if not wide:
        return results, notes
    t0 = time.time()
    measured = app_size_measure(root, cfg)
    newest = max(((root / f).stat().st_mtime for f in changed if (root / f).is_file()), default=0.0)
    if not measured:
        if res["files"]:
            notes.append("mobile: build a release package, then `eos mobile size` (app-size budget/ratchet)")
    elif min(v["mtime"] for v in measured.values()) < newest:
        notes.append("mobile: the built package is older than your changes: rebuild, then `eos mobile size`")
    else:
        errs, lines = app_size_problems(root, cfg, measured)
        results.append(("app size (ratchet)", 1 if errs else 0, "\n".join(errs + lines), time.time() - t0))
    return results, notes


# ----------------------------------------------------------------------------- llm: prompt files, eval regression gate
LLM_DEFAULTS = {
    "prompts": [],  # globs; [] = every *.prompt.md, plus *.md under a prompts/ folder (README.md excluded)
    "require": ["id", "version", "model", "owner", "evals", "max_output_tokens"],
    "gate": "evals/llm/gate.json",  # thresholds for `eos llm gate`
    "results": "evals/llm/results.json",  # where the eval runner writes per-case results
    "allow": {},  # {"LLM011": "why, reviewed by whom"}
}
LLM_RULES = {
    "LLM001": "prompt file without a valid frontmatter block (--- id/version/model/owner/evals/max_output_tokens ---)",
    "LLM002": "required frontmatter key missing (config llm.require)",
    "LLM003": "version is not a positive integer",
    "LLM004": "evals points to a file that does not exist",
    "LLM005": "max_output_tokens is not a positive integer",
    "LLM006": "template variable {{x}} not declared in inputs (or a declared input never used: warning)",
    "LLM007": "untrusted input not inside a delimiting tag such as <document>{{x}}</document>",
    "LLM008": "secret-like value in a prompt file (API key, private key)",
    "LLM009": "two prompt files share one id",
    "LLM010": "prompt text or settings changed but version not bumped (vs the base branch)",
    "LLM011": "floating model alias (-latest / no snapshot): pin a version for reproducible evals",
}
LLM_WARN_ONLY = {"LLM011"}
LLM_SKIP_DIRS = {
    "node_modules", ".git", ".next", "dist", "build", "out", "coverage", ".expo", ".turbo", ".eos", "vendor",
    "__pycache__", ".venv", "venv", "site-packages",
}  # fmt: skip
LLM_VAR_RX = _lazy_rx(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
LLM_TAG_RX = _lazy_rx(r"<(/?)([A-Za-z][\w.-]*)(?:\s[^<>]*)?(/?)>")
LLM_SECRET_RX = _lazy_rx(
    r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}|\bAIza[0-9A-Za-z_-]{35}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:xox[abp]|ghp|gho|github_pat)_[A-Za-z0-9_]{20,}"
)
LLM_CHANGE_RX = _lazy_rx(r"\.prompt\.md$|(^|/)prompts/[^/]+|(^|/)evals/llm/")


def llm_cfg(root: Path) -> dict:
    d = _load_cfg(root).get("llm", {})
    return {**LLM_DEFAULTS, **(d if isinstance(d, dict) else {})}


def llm_prompt_files(root: Path, cfg: dict) -> list[Path]:
    if cfg["prompts"]:
        out: list[Path] = []
        for g in cfg["prompts"]:
            out += [p for p in sorted(root.glob(g)) if p.is_file() and not p.is_symlink()]
        return sorted(set(out))
    found = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in LLM_SKIP_DIRS and not d.startswith("."))
        in_prompts = "prompts" in Path(dp).relative_to(root).parts
        for fn in sorted(fns):
            if fn.endswith(".prompt.md") or (in_prompts and fn.endswith(".md") and fn.lower() != "readme.md"):
                p = Path(dp) / fn
                if not p.is_symlink():
                    found.append(p)
    return found


def has_llm_files(root: Path) -> bool:
    return bool(llm_prompt_files(root, llm_cfg(root)))


def llm_prompt_meta(text: str) -> tuple[dict, str]:
    """Prompt-file frontmatter: the pack subset plus trailing `# comments` on unquoted values."""
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter (the file must start with ---)")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    lines = []
    for ln in text[4:end].splitlines():
        key, sep, val = ln.partition(":")
        if sep and not val.strip().startswith('"'):
            val = re.sub(r"\s+#.*$", "", val)
        lines.append(key + sep + val)
    return parse_frontmatter("---\n" + "\n".join(lines) + "\n---\n" + text[end + 5 :])


def _pos_int(v: object) -> bool:
    return isinstance(v, str) and v.isdigit() and int(v) > 0


def _untrusted_outside_tags(body: str, var: str) -> int:
    """Occurrences of {{var}} not enclosed by an open XML-style tag (e.g. <invoice>…</invoice>)."""
    bad = 0
    for m in re.finditer(r"\{\{\s*" + re.escape(var) + r"\s*\}\}", body):
        stack: list[str] = []
        for t in LLM_TAG_RX.finditer(body[: m.start()]):
            if t.group(3):  # self-closing
                continue
            if t.group(1):
                if t.group(2) in stack:
                    while stack and stack.pop() != t.group(2):
                        pass
            else:
                stack.append(t.group(2))
        after = body[m.end() :]
        if not any(re.search(r"</" + re.escape(tag) + r">", after) for tag in stack):
            bad += 1
    return bad


def _llm_file_findings(root: Path, p: Path, cfg: dict) -> tuple[list[tuple[str, str]], dict]:
    rel = p.relative_to(root).as_posix()
    try:
        text = read(p)
    except (OSError, UnicodeDecodeError) as exc:
        return [("LLM001", f"{rel}: unreadable ({exc})")], {}
    out: list[tuple[str, str]] = []
    if LLM_SECRET_RX.search(text):
        out.append(("LLM008", f"{rel}: looks like a credential; load secrets from the environment, never prompts"))
    try:
        meta, body = llm_prompt_meta(text)
    except ValueError as exc:
        return out + [("LLM001", f"{rel}: {exc}")], {}
    for k in cfg["require"]:
        if not str(meta.get(k, "")).strip():
            out.append(("LLM002", f"{rel}: missing `{k}`"))
    if "version" in meta and not _pos_int(meta["version"]):
        out.append(("LLM003", f"{rel}: version {meta['version']!r} (use 1, 2, 3 …; bump on every change)"))
    ev = str(meta.get("evals", "")).strip()
    if ev and not (root / ev).exists() and not (p.parent / ev).exists():
        out.append(("LLM004", f"{rel}: evals file {ev} not found"))
    if "max_output_tokens" in meta and not _pos_int(meta["max_output_tokens"]):
        out.append(("LLM005", f"{rel}: max_output_tokens {meta['max_output_tokens']!r}"))
    inputs = meta.get("inputs", [])
    inputs = inputs if isinstance(inputs, list) else [x.strip() for x in str(inputs).split(",") if x.strip()]
    used = set(LLM_VAR_RX.findall(body))
    for v in sorted(used - set(inputs)):
        out.append(("LLM006", f"{rel}: {{{{{v}}}}} is not listed in inputs"))
    untrusted = meta.get("untrusted", [])
    untrusted = untrusted if isinstance(untrusted, list) else [str(untrusted)]
    for v in untrusted:
        n = _untrusted_outside_tags(body, v)
        if n:
            out.append(("LLM007", f"{rel}: {{{{{v}}}}} appears {n}× outside a tag; wrap it, e.g. <{v}>…</{v}>"))
    model = str(meta.get("model", ""))
    if model and (model.endswith("-latest") or model in ("latest", "default")):
        out.append(("LLM011", f"{rel}: model {model}"))
    meta["_unused"] = sorted(set(inputs) - used)
    return out, meta


def _llm_base_meta(root: Path, base: str, rel: str) -> tuple[dict, str] | None:
    rc, old = run(["git", "show", f"{base}:{rel}"], cwd=root, timeout=10)
    if rc != 0:
        return None  # new file
    try:
        return llm_prompt_meta(old)
    except ValueError:
        return None


def llm_problems(root: Path, cfg: dict | None = None, only: list[str] | None = None, base: str = "") -> dict:
    """Prompt-file findings → errors (LLM011 and unused inputs: warnings), minus rules allowed with a reason.
    `only`: relative paths to restrict to; `base`: git ref for the version-bump rule (LLM010), "" = skip it."""
    cfg = cfg or llm_cfg(root)
    files = llm_prompt_files(root, cfg)
    raw: list[tuple[str, str]] = []
    warns: list[str] = []
    ids: dict[str, str] = {}
    checked = 0
    for p in files:
        rel = p.relative_to(root).as_posix()
        f, meta = _llm_file_findings(root, p, cfg)
        if meta.get("id"):
            if meta["id"] in ids:
                raw.append(("LLM009", f"{rel}: id {meta['id']} also used by {ids[meta['id']]}"))
            ids.setdefault(meta["id"], rel)
        if only is not None and rel not in only:
            continue
        checked += 1
        raw += f
        warns += [f"{rel}: input `{v}` is declared but never used" for v in meta.get("_unused", [])]
        if base and meta:
            old = _llm_base_meta(root, base, rel)
            if old is not None:
                om, ob = old
                nm = {k: v for k, v in meta.items() if not k.startswith("_")}
                changed = ob.strip() != llm_prompt_meta(read(p))[1].strip() or {
                    k: v for k, v in om.items() if k != "version"
                } != {k: v for k, v in nm.items() if k != "version"}
                if changed and str(om.get("version", "")) == str(meta.get("version", "")):
                    raw.append(
                        ("LLM010", f"{rel}: changed since {base[:12]} but version is still {meta.get('version')}")
                    )
    raw = [(r, m) for r, m in raw if only is None or m.split(":")[0] in only]
    errs, allowed = [], []
    for rid, reason in cfg["allow"].items():
        if rid not in LLM_RULES:
            warns.append(f"llm.allow: unknown rule {rid}")
        elif not str(reason).strip():
            errs.append(f"llm.allow.{rid}: give a reason (who reviewed it and why)")
    for rid, msg in raw:
        if str(cfg["allow"].get(rid, "")).strip():
            allowed.append(rid)
            continue
        (warns if rid in LLM_WARN_ONLY else errs).append(f"{rid} {msg}")
    return {"errors": errs, "warnings": warns, "files": checked, "allowed": sorted(set(allowed))}


def _rate(cases: list[dict]) -> float:
    return sum(1 for c in cases if c.get("pass") is True) / len(cases) if cases else 0.0


def llm_gate_problems(results: dict, gate: dict, baseline: dict | None) -> tuple[list[str], list[str], dict]:
    """Eval regression gate: thresholds overall and per tag, max drop vs a committed baseline, no vanished cases.
    results = {"cases": [{"id", "pass": bool, "tags": [...]}, …]}; returns (errors, info lines, summary)."""
    errs: list[str] = []
    cases = results.get("cases") if isinstance(results, dict) else None
    if not isinstance(cases, list) or not all(isinstance(c, dict) and "id" in c for c in cases):
        return ['results: expected {"cases": [{"id": …, "pass": true|false, "tags": […]}, …]}'], [], {}
    ids = [str(c["id"]) for c in cases]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append(f"duplicate case ids: {', '.join(dup[:5])}")
    bad = [str(c["id"]) for c in cases if not isinstance(c.get("pass"), bool)]
    if bad:
        errs.append(f"`pass` must be true or false: {', '.join(bad[:5])}")
    by_tag: dict[str, list[dict]] = {}
    for c in cases:
        for t in c.get("tags") or []:
            by_tag.setdefault(str(t), []).append(c)
    rate = _rate(cases)
    summary = {
        "pass_rate": round(rate, 4),
        "by_tag": {t: round(_rate(cs), 4) for t, cs in sorted(by_tag.items())},
        "cases": sorted(ids),
    }
    info = [f"pass rate {rate:.2f} ({sum(1 for c in cases if c.get('pass') is True)}/{len(cases)})"]
    min_cases = int(gate.get("min_cases", 1))
    if len(cases) < min_cases:
        errs.append(f"{len(cases)} cases < min_cases {min_cases}")
    if "min_pass_rate" not in gate:
        errs.append("gate config: set min_pass_rate (e.g. 0.9)")
    elif rate < float(gate["min_pass_rate"]):
        errs.append(f"pass rate {rate:.2f} < {float(gate['min_pass_rate']):.2f}")
    for t, need in sorted((gate.get("min_by_tag") or {}).items()):
        cs = by_tag.get(t, [])
        if not cs:
            errs.append(f"tag {t}: no cases (min {float(need):.2f} configured)")
        elif _rate(cs) < float(need):
            n = sum(1 for c in cs if c.get("pass") is True)
            errs.append(f"tag {t} pass rate {_rate(cs):.2f} < {float(need):.2f} ({n}/{len(cs)})")
    if baseline:
        drop = float(gate.get("max_drop", 0.03))
        old = float(baseline.get("pass_rate", 0))
        if old - rate > drop + 1e-9:
            errs.append(f"pass rate dropped {old:.2f} → {rate:.2f} (max drop {drop:.2f})")
        for t, o in sorted((baseline.get("by_tag") or {}).items()):
            if t in summary["by_tag"] and float(o) - summary["by_tag"][t] > drop + 1e-9:
                errs.append(f"tag {t} dropped {float(o):.2f} → {summary['by_tag'][t]:.2f} (max drop {drop:.2f})")
        gone = sorted(set(baseline.get("cases") or []) - set(ids))
        if gone:
            errs.append(
                f"{len(gone)} baseline case(s) missing from results ({', '.join(gone[:5])}): removing hard cases"
                " is not a fix; restore them, or update the baseline in a reviewed commit"
            )
        info.append(f"baseline {old:.2f} ({baseline.get('updated', '?')})")
    return errs, info, summary


def cmd_llm(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = llm_cfg(root)
    if args.action == "rules":
        for rid, what in LLM_RULES.items():
            print(f"  {rid}{' (warn)' if rid in LLM_WARN_ONLY else ''}  {what}")
        print('  allow one with a reason: "llm": {"allow": {"LLM011": "why, reviewed by whom"}} in .eos/config.json')
        return 0
    if args.action == "check":
        base = ""
        if args.base:
            base, _ = lane_base(root, args.base)
        res = llm_problems(root, cfg, None, base)
        if args.json:
            print(json.dumps(res, indent=1))
            return 1 if res["errors"] or (args.strict and res["warnings"]) else 0
        for w in res["warnings"]:
            print("  warn: " + w)
        for e in res["errors"]:
            print("  error: " + e)
        failed = bool(res["errors"]) or (args.strict and bool(res["warnings"]))
        allowed = f"; allowed by config: {', '.join(res['allowed'])}" if res["allowed"] else ""
        print(
            f"eos llm check: {'FAILED' if failed else 'OK'} ({res['files']} prompt files; {len(res['errors'])} errors,"
            f" {len(res['warnings'])} warnings{allowed})"
        )
        if not res["files"]:
            print("  no prompt files found (*.prompt.md or prompts/*.md; `eos scaffold llm-evals` adds an example)")
        elif res["errors"] or res["warnings"]:
            print("  rules: `eos llm rules`; refs: .eos/packs/ref/llm/prompts-structured-output.md")
        return 1 if failed else 0
    # gate
    rpath = root / (args.results or cfg["results"])
    gpath = root / (args.config or cfg["gate"])
    try:
        results = json.loads(read(rpath))
    except (OSError, ValueError) as exc:
        eprint(
            f"eos llm gate: cannot read results {rpath.relative_to(root) if rpath.is_relative_to(root) else rpath}: {exc}"
        )
        return 2
    try:
        gate = json.loads(read(gpath))
    except (OSError, ValueError) as exc:
        eprint(
            f"eos llm gate: cannot read gate config {gpath.relative_to(root).as_posix()}: {exc} (`eos scaffold llm-evals`)"
        )
        return 2
    bpath = root / gate["baseline"] if gate.get("baseline") else None
    baseline = None
    if bpath and bpath.exists():
        try:
            baseline = json.loads(read(bpath))
        except ValueError as exc:
            eprint(f"eos llm gate: invalid baseline {bpath.relative_to(root).as_posix()}: {exc}")
            return 2
    errs, info, summary = llm_gate_problems(results, gate, None if args.update else baseline)
    if args.update:
        if errs:
            for e in errs:
                print("  error: " + e)
            print("eos llm gate --update: refused (fix the thresholds first; the baseline only records passing runs)")
            return 1
        if not bpath:
            eprint('eos llm gate --update: set "baseline" in the gate config (e.g. "evals/llm/baseline.json")')
            return 2
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(
            json.dumps({**summary, "updated": _today().isoformat()}, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        print(
            f"wrote {bpath.relative_to(root).as_posix()}: pass rate {summary['pass_rate']:.2f}, {len(summary['cases'])} cases"
        )
        print("  commit it in its own reviewed change (like a snapshot update)")
        return 0
    for ln in info:
        print("  " + ln)
    for e in errs:
        print("  error: " + e)
    if bpath and baseline is None:
        print("  no baseline yet: after a reviewed passing run, `eos llm gate --update`")
    print(f"eos llm gate: {'FAILED' if errs else 'OK'} ({len(summary.get('cases', []))} cases)")
    return 1 if errs else 0


def llm_extras(
    root: Path, m: dict, c: dict, full: bool, base: str | None = None
) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for LLM features. standard+: the prompt-file check (in-process, ms) on changed prompt
    files, including the version-bump rule against the lane base. risky/one-way-door/--full: every prompt file, and
    the eval gate when a results file newer than the changed files exists; otherwise a note. Trivial/spike: nothing."""
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return [], []
    changed = [f for f in c["files"] if LLM_CHANGE_RX.search(f)]
    if not changed and not full:
        return [], []
    cfg = llm_cfg(root)
    wide = full or c["risk"] in ("risky", "one-way-door")
    t0 = time.time()
    ref = lane_base(root, base)[0] if (root / ".git").exists() else ""
    res = llm_problems(root, cfg, None if wide else changed, ref)
    results: list[tuple[str, int, str, float]] = []
    notes = [f"llm: {w}" for w in res["warnings"][:6]]
    if res["files"]:
        results.append(("prompt files (llm)", 1 if res["errors"] else 0, "\n".join(res["errors"]), time.time() - t0))
    if not wide:
        if changed:
            notes.append("llm: prompt/eval change: run your evals, then `eos llm gate` (CI runs it on the PR)")
        return results, notes
    rpath, gpath = root / cfg["results"], root / cfg["gate"]
    newest = max(((root / f).stat().st_mtime for f in changed if (root / f).is_file()), default=0.0)
    if not gpath.exists():
        if res["files"]:
            notes.append("llm: no eval gate config: `eos scaffold llm-evals`")
    elif not rpath.exists() or rpath.stat().st_mtime < newest:
        notes.append("llm: eval results are missing or older than your changes: run the evals, then `eos llm gate`")
    else:
        t0 = time.time()
        try:
            gate = json.loads(read(gpath))
            bp = root / gate["baseline"] if gate.get("baseline") else None
            baseline = json.loads(read(bp)) if bp and bp.exists() else None
            errs, info, _ = llm_gate_problems(json.loads(read(rpath)), gate, baseline)
        except (OSError, ValueError) as exc:
            errs, info = [f"cannot read eval gate files: {exc}"], []
        results.append(("eval gate (llm)", 1 if errs else 0, "\n".join(errs + info), time.time() - t0))
    return results, notes


# ----------------------------------------------------------------------------- data: ODCS contracts, notebooks, split leakage
DATA_DEFAULTS = {
    "contracts": [],  # globs; [] = *.odcs.yaml|yml|json anywhere + YAML under contracts/ with `kind: DataContract`
    "notebooks": [],  # globs; [] = every git-tracked *.ipynb (all *.ipynb outside build folders without git)
    "notebook_max_kb": 500,  # NB004 warning above this (pre-commit check-added-large-files blocks >500 KB)
    "allow": {},  # {"NB002": "why, reviewed by whom"}
}
DATA_RULES = {
    "DAT001": "contract file is not valid YAML/JSON or not a mapping",
    "DAT002": "ODCS fundamentals missing or wrong (apiVersion vX.Y.Z, kind: DataContract, id, version)",
    "DAT003": "contract version is not a semantic version string (1.2.0; quote it in YAML)",
    "DAT004": "schema malformed: objects need a name and properties a name and a valid logicalType (missing type: warning)",
    "DAT005": "property named like personal data (email, phone, msisdn, national_id, dob…) without a classification",
    "DAT006": "breaking change vs the base branch (removed object/property, type change, now required, narrower enum) without a major version bump",
    "DAT007": "two contract files share one id",
    "DAT008": "no team/owner in the contract",
    "NB000": "notebook is not valid JSON",
    "NB001": "notebook committed with outputs (strip them: nbstripout)",
    "NB002": "notebook committed with execution counts",
    "NB003": "secret-like value in a notebook",
    "NB004": "notebook file larger than data.notebook_max_kb",
}
DATA_WARN_ONLY = {"DAT005", "DAT008", "NB004"}
ODCS_LOGICAL_TYPES = {
    "string",
    "date",
    "timestamp",
    "time",
    "number",
    "integer",
    "object",
    "array",
    "boolean",
    "map",
    "vector",
}
DATA_PII_RX = _lazy_rx(
    r"(?i)(^|_)(e_?mail|phone(_?number)?|msisdn|mobile_number|national_?id|id_?number|passport(_?number)?"
    r"|date_?of_?birth|dob|birth_?date|first_?name|last_?name|full_?name|surname|address|gps|latitude|longitude)($|_)"
)
DATA_SECRET_RX = _lazy_rx(LLM_SECRET_RX.pattern + r"|\bAKIA[0-9A-Z]{16}\b|\bxox[a-z]-[A-Za-z0-9-]{10,}")
DATA_CHANGE_RX = _lazy_rx(r"\.ipynb$|\.odcs\.(ya?ml|json)$|(^|/)contracts/[^/]+\.(ya?ml|json)$")
DBT_CHANGE_RX = _lazy_rx(r"(^|/)(models|seeds|snapshots|macros)/.+\.(sql|ya?ml|csv)$|(^|/)dbt_project\.yml$")
SEMVER_RX = _lazy_rx(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def data_cfg(root: Path) -> dict:
    d = _load_cfg(root).get("data", {})
    return {**DATA_DEFAULTS, **(d if isinstance(d, dict) else {})}


# --- a small YAML subset (block mappings/sequences, flow [..] {..}, scalars, block scalars) for ODCS files when
# PyYAML is not installed. Anchors, tags and multi-document files are refused with a clear message.
class YamlSubsetError(ValueError):
    pass


def _yaml_strip_comment(s: str) -> str:
    q = ""
    for i, ch in enumerate(s):
        if q:
            if ch == q and not (q == '"' and i and s[i - 1] == "\\"):
                q = ""
        elif ch in "'\"" and (i == 0 or s[i - 1] in " \t[{,:-"):
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def _yaml_scalar(s: str, ln: int) -> object:
    s = s.strip()
    if not s:
        return None
    if s[0] in "&*!" or s.startswith(("|", ">")) and len(s) > 2 and s[1] not in "-+":
        raise YamlSubsetError(f"line {ln}: anchors, aliases and tags are not supported here (install PyYAML)")
    if s[0] == '"':
        if not s.endswith('"') or len(s) < 2:
            raise YamlSubsetError(f"line {ln}: unterminated string")
        try:
            return json.loads(s)
        except ValueError:
            return s[1:-1]
    if s[0] == "'":
        if not s.endswith("'") or len(s) < 2:
            raise YamlSubsetError(f"line {ln}: unterminated string")
        return s[1:-1].replace("''", "'")
    if s in ("null", "Null", "NULL", "~"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", s):
        return float(s)
    return s


def _yaml_flow(s: str, ln: int) -> object:
    pos = 0

    def ws() -> None:
        nonlocal pos
        while pos < len(s) and s[pos] in " \t":
            pos += 1

    def plain(stop: str) -> str:
        nonlocal pos
        if s[pos] in "'\"":
            q, start = s[pos], pos
            pos += 1
            while pos < len(s) and not (s[pos] == q and (q == "'" or s[pos - 1] != "\\")):
                pos += 1
            pos += 1
            return s[start:pos]
        start = pos
        while pos < len(s) and s[pos] not in stop and not (s[pos] == ":" and s[pos + 1 : pos + 2] in (" ", "")):
            pos += 1
        return s[start:pos].strip()

    def value() -> object:
        nonlocal pos
        ws()
        if pos >= len(s):
            raise YamlSubsetError(f"line {ln}: unterminated flow collection")
        if s[pos] == "[":
            pos += 1
            out: list = []
            ws()
            if s[pos : pos + 1] == "]":
                pos += 1
                return out
            while True:
                out.append(value())
                ws()
                if s[pos : pos + 1] == ",":
                    pos += 1
                    ws()
                    if s[pos : pos + 1] == "]":
                        pos += 1
                        return out
                    continue
                if s[pos : pos + 1] == "]":
                    pos += 1
                    return out
                raise YamlSubsetError(f"line {ln}: expected , or ] in a flow sequence")
        if s[pos] == "{":
            pos += 1
            obj: dict = {}
            ws()
            if s[pos : pos + 1] == "}":
                pos += 1
                return obj
            while True:
                ws()
                k = _yaml_scalar(plain(",}"), ln)
                ws()
                if s[pos : pos + 1] != ":":
                    raise YamlSubsetError(f"line {ln}: expected key: value in a flow mapping")
                pos += 1
                obj[str(k)] = value()
                ws()
                if s[pos : pos + 1] == ",":
                    pos += 1
                    ws()
                    if s[pos : pos + 1] == "}":
                        pos += 1
                        return obj
                    continue
                if s[pos : pos + 1] == "}":
                    pos += 1
                    return obj
                raise YamlSubsetError(f"line {ln}: expected , or }} in a flow mapping")
        return _yaml_scalar(plain(",]}"), ln)

    v = value()
    ws()
    if pos != len(s):
        raise YamlSubsetError(f"line {ln}: unexpected text after a flow collection")
    return v


def _yaml_value(s: str, ln: int) -> object:
    s = s.strip()
    return _yaml_flow(s, ln) if s[:1] in "[{" else _yaml_scalar(s, ln)


def _yaml_key_split(text: str) -> tuple[str, str] | None:
    """`key: rest` (or `key:` at end) outside quotes/brackets → (key, rest); None if the line is not a mapping entry."""
    q, depth = "", 0
    for i, ch in enumerate(text):
        if q:
            if ch == q:
                q = ""
        elif ch in "'\"" and i == 0:
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(text) or text[i + 1] == " "):
            return text[:i].strip(), text[i + 1 :].strip()
    return None


def yaml_subset_load(text: str) -> object:
    raw = text.replace("\r\n", "\n").split("\n")
    if any(ln.strip() == "---" for ln in raw[1:]) or any(ln.startswith("\t") for ln in raw):
        raise YamlSubsetError("multi-document files and tab indentation are not supported (install PyYAML)")
    lines: list[list] = []  # [indent, text, lineno]
    i = 0
    while i < len(raw):
        ln = raw[i]
        body = _yaml_strip_comment(ln)
        if body.strip() in ("", "---"):
            i += 1
            continue
        ind = len(body) - len(body.lstrip(" "))
        t = body.strip()
        start = i
        while t.count("[") + t.count("{") > t.count("]") + t.count("}") and i + 1 < len(raw):  # multi-line flow
            i += 1
            t += " " + _yaml_strip_comment(raw[i]).strip()
        lines.append([ind, t, start + 1])
        i += 1

    def block_scalar(idx: int, parent_ind: int, style: str) -> tuple[str, int]:
        start_line = lines[idx][2]  # 1-based line of the key; content follows in raw
        chunk: list[str] = []
        j = start_line
        while j < len(raw) and (raw[j].strip() == "" or len(raw[j]) - len(raw[j].lstrip(" ")) > parent_ind):
            chunk.append(raw[j])
            j += 1
        while chunk and not chunk[-1].strip():
            chunk.pop()
        pad = min((len(c) - len(c.lstrip(" ")) for c in chunk if c.strip()), default=0)
        body = [c[pad:] for c in chunk]
        out = "\n".join(body) if style.startswith("|") else " ".join(b.strip() for b in body if b.strip())
        nxt = idx + 1
        while nxt < len(lines) and lines[nxt][2] <= j:
            nxt += 1
        return out + ("" if style.endswith("-") else "\n"), nxt

    def node(idx: int, ind: int) -> tuple[object, int]:
        if lines[idx][1].startswith("- ") or lines[idx][1] == "-":
            return seq(idx, ind)
        return mapping(idx, ind)

    def seq(idx: int, ind: int) -> tuple[list, int]:
        out: list = []
        while idx < len(lines) and lines[idx][0] == ind and (lines[idx][1].startswith("- ") or lines[idx][1] == "-"):
            rest = lines[idx][1][1:].strip()
            if not rest:
                if idx + 1 < len(lines) and lines[idx + 1][0] > ind:
                    v, idx = node(idx + 1, lines[idx + 1][0])
                else:
                    v, idx = None, idx + 1
            elif rest[:1] not in "[{'\"" and _yaml_key_split(rest):
                lines[idx] = [ind + len(lines[idx][1]) - len(rest), rest, lines[idx][2]]
                v, idx = mapping(idx, lines[idx][0])
            else:
                v, idx = _yaml_value(rest, lines[idx][2]), idx + 1
            out.append(v)
        if idx < len(lines) and lines[idx][0] > ind:
            raise YamlSubsetError(f"line {lines[idx][2]}: unexpected indentation")
        return out, idx

    def mapping(idx: int, ind: int) -> tuple[dict, int]:
        out: dict = {}
        while idx < len(lines) and lines[idx][0] == ind and not lines[idx][1].startswith("- "):
            ent, lno = lines[idx][1], lines[idx][2]
            kv = _yaml_key_split(ent)
            if kv is None:
                raise YamlSubsetError(f"line {lno}: expected `key: value`")
            k = str(_yaml_scalar(kv[0], lno))
            if k in out:
                raise YamlSubsetError(f"line {lno}: duplicate key {k}")
            rest = kv[1]
            if rest in ("|", "|-", "|+", ">", ">-", ">+"):
                out[k], idx = block_scalar(idx, ind, rest)
            elif rest:
                out[k], idx = _yaml_value(rest, lno), idx + 1
            elif idx + 1 < len(lines) and lines[idx + 1][0] > ind:
                out[k], idx = node(idx + 1, lines[idx + 1][0])
            elif idx + 1 < len(lines) and lines[idx + 1][0] == ind and lines[idx + 1][1].startswith("- "):
                out[k], idx = seq(idx + 1, ind)
            else:
                out[k], idx = None, idx + 1
        if idx < len(lines) and lines[idx][0] > ind:
            raise YamlSubsetError(f"line {lines[idx][2]}: unexpected indentation")
        return out, idx

    if not lines:
        return None
    v, idx = node(0, lines[0][0])
    if idx != len(lines):
        raise YamlSubsetError(f"line {lines[idx][2]}: unexpected content (check indentation)")
    return v


def _plain_data(v: object) -> object:
    if isinstance(v, dict):
        return {str(k): _plain_data(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain_data(x) for x in v]
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def load_yaml_or_json(text: str, name: str = "") -> object:
    """JSON for .json; YAML via PyYAML when installed, else the subset parser above. Dates become ISO strings."""
    if name.endswith(".json"):
        return json.loads(text)
    try:
        import yaml  # type: ignore[import-untyped]  # optional
    except ImportError:
        return yaml_subset_load(text)
    try:
        return _plain_data(yaml.safe_load(text))
    except yaml.YAMLError as exc:  # same contract as the subset parser: callers catch ValueError
        raise ValueError(" ".join(str(exc).split())) from None


def data_contract_files(root: Path, cfg: dict) -> list[Path]:
    if cfg["contracts"]:
        out: list[Path] = []
        for g in cfg["contracts"]:
            out += [p for p in sorted(root.glob(g)) if p.is_file() and not p.is_symlink()]
        return sorted(set(out))
    found = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in LLM_SKIP_DIRS and not d.startswith("."))
        in_contracts = "contracts" in Path(dp).relative_to(root).parts
        for fn in sorted(fns):
            p = Path(dp) / fn
            if p.is_symlink():
                continue
            if re.search(r"\.odcs\.(ya?ml|json)$", fn):
                found.append(p)
            elif in_contracts and re.search(r"\.(ya?ml|json)$", fn):
                try:
                    head = read(p)[:4000]
                except OSError:
                    continue
                if re.search(r"(?m)^\s*\"?kind\"?\s*:\s*\"?DataContract\b", head):
                    found.append(p)
    return found


def data_notebook_files(root: Path, cfg: dict) -> list[Path]:
    if cfg["notebooks"]:
        out: list[Path] = []
        for g in cfg["notebooks"]:
            out += [p for p in sorted(root.glob(g)) if p.is_file() and not p.is_symlink()]
        return sorted(set(out))
    if (root / ".git").exists():
        rc, outp = run(["git", "ls-files", "-z", "--", "*.ipynb"], cwd=root, timeout=20)
        if rc == 0:
            return [root / f for f in outp.split("\0") if f and (root / f).is_file() and not (root / f).is_symlink()]
    found = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in LLM_SKIP_DIRS and not d.startswith("."))
        found += [Path(dp) / f for f in sorted(fns) if f.endswith(".ipynb") and not (Path(dp) / f).is_symlink()]
    return found


def has_data_files(root: Path) -> bool:
    cfg = data_cfg(root)
    return bool(data_contract_files(root, cfg) or data_notebook_files(root, cfg))


def _contract_objects(doc: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for o in doc.get("schema") or []:
        if isinstance(o, dict) and o.get("name"):
            props = {}
            for p in o.get("properties") or []:
                if isinstance(p, dict) and p.get("name"):
                    props[str(p["name"])] = p
            out[str(o["name"])] = props
    return out


def contract_findings(rel: str, doc: object) -> list[tuple[str, str]]:
    if not isinstance(doc, dict):
        return [("DAT001", f"{rel}: top level must be a mapping (an ODCS document)")]
    out: list[tuple[str, str]] = []
    for k in ("apiVersion", "kind", "id", "version"):
        if k not in doc or doc[k] in (None, ""):
            out.append(("DAT002", f"{rel}: missing `{k}`"))
    if doc.get("kind") not in (None, "", "DataContract"):
        out.append(("DAT002", f"{rel}: kind must be DataContract, got {doc.get('kind')!r}"))
    av = doc.get("apiVersion")
    if av not in (None, "") and not re.fullmatch(r"v\d+\.\d+\.\d+", str(av)):
        out.append(("DAT002", f"{rel}: apiVersion {av!r} is not an ODCS version such as v3.2.0"))
    ver = doc.get("version")
    if ver not in (None, "") and not (isinstance(ver, str) and SEMVER_RX.match(ver)):
        out.append(("DAT003", f'{rel}: version {ver!r} (use a quoted semantic version such as "1.0.0")'))
    team = doc.get("team")
    if not team:
        out.append(("DAT008", f"{rel}: no `team` (who owns this dataset and answers consumers?)"))
    schema = doc.get("schema")
    if schema is not None and not isinstance(schema, list):
        out.append(("DAT004", f"{rel}: `schema` must be a list of objects"))
        schema = []
    for oi, o in enumerate(schema or []):
        if not isinstance(o, dict) or not o.get("name"):
            out.append(("DAT004", f"{rel}: schema[{oi}] needs a `name`"))
            continue
        props = o.get("properties") or []
        if not isinstance(props, list):
            out.append(("DAT004", f"{rel}: {o['name']}.properties must be a list"))
            continue
        seen: set[str] = set()
        for pi, p in enumerate(props):
            if not isinstance(p, dict) or not p.get("name"):
                out.append(("DAT004", f"{rel}: {o['name']}.properties[{pi}] needs a `name`"))
                continue
            pn = str(p["name"])
            if pn in seen:
                out.append(("DAT004", f"{rel}: {o['name']}.{pn} is listed twice"))
            seen.add(pn)
            lt = p.get("logicalType")
            if lt is None:
                out.append(("DAT004w", f"{rel}: {o['name']}.{pn} has no logicalType"))
            elif lt not in ODCS_LOGICAL_TYPES:
                out.append(
                    (
                        "DAT004",
                        f"{rel}: {o['name']}.{pn} logicalType {lt!r} (one of {', '.join(sorted(ODCS_LOGICAL_TYPES))})",
                    )
                )
            if DATA_PII_RX.search(pn) and not p.get("classification"):
                out.append(
                    (
                        "DAT005",
                        f"{rel}: {o['name']}.{pn} looks like personal data; set `classification` (e.g. restricted) and a pii tag",
                    )
                )
    return out


def _major(v: object) -> int:
    m = re.match(r"(\d+)\.", str(v or ""))
    return int(m.group(1)) if m else -1


def _enum_values(e: object) -> set[str] | None:
    """ODCS 3.2 enum entries are objects with a `value` (RFC 0033); plain scalars are accepted too."""
    if not isinstance(e, list):
        return None
    return {str(x.get("value") if isinstance(x, dict) else x) for x in e}


def contract_breaking(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """(breaking changes, other changes) between two ODCS documents, by object and property name."""
    brk, other = [], []
    o_objs, n_objs = _contract_objects(old), _contract_objects(new)
    for on, oprops in o_objs.items():
        if on not in n_objs:
            brk.append(f"object {on} removed")
            continue
        nprops = n_objs[on]
        for pn, op in oprops.items():
            np_ = nprops.get(pn)
            if np_ is None:
                brk.append(f"{on}.{pn} removed")
                continue
            if op.get("logicalType") != np_.get("logicalType") and op.get("logicalType") is not None:
                brk.append(f"{on}.{pn} logicalType {op.get('logicalType')} → {np_.get('logicalType')}")
            if not op.get("required") and np_.get("required"):
                brk.append(f"{on}.{pn} is now required")
            oe, ne = _enum_values(op.get("enum")), _enum_values(np_.get("enum"))
            if ne is not None and (oe is None or oe - ne):
                brk.append(f"{on}.{pn} accepted values narrowed")
        for pn in nprops:
            if pn not in oprops:
                other.append(f"{on}.{pn} added")
    for on in n_objs:
        if on not in o_objs:
            other.append(f"object {on} added")
    return brk, other


def _contract_base_doc(root: Path, base: str, rel: str) -> dict | None:
    rc, old = run(["git", "show", f"{base}:{rel}"], cwd=root, timeout=10)
    if rc != 0:
        return None
    try:
        d = load_yaml_or_json(old, rel)
    except (ValueError, YamlSubsetError):
        return None
    return d if isinstance(d, dict) else None


def notebook_findings(rel: str, text: str, size_kb: float, max_kb: float) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if size_kb > max_kb:
        out.append(("NB004", f"{rel}: {size_kb:.0f} KB > {max_kb:.0f} KB (move data and images out of the notebook)"))
    try:
        nb = json.loads(text)
    except ValueError as exc:
        return [*out, ("NB000", f"{rel}: not valid notebook JSON ({exc})")]
    cells = nb.get("cells") if isinstance(nb, dict) else None
    if not isinstance(cells, list):
        return [*out, ("NB000", f"{rel}: no cells list")]
    with_out = [i for i, c in enumerate(cells) if isinstance(c, dict) and c.get("outputs")]
    counted = [i for i, c in enumerate(cells) if isinstance(c, dict) and c.get("execution_count") is not None]
    if with_out:
        out.append(
            (
                "NB001",
                f"{rel}: {len(with_out)} cell(s) with outputs, first at cell {with_out[0] + 1} (nbstripout; outputs leak data into git)",
            )
        )
    if counted:
        out.append(("NB002", f"{rel}: {len(counted)} cell(s) with execution counts (nbstripout clears them)"))
    for i, c in enumerate(cells):
        if not isinstance(c, dict):
            continue
        src = c.get("source", "")
        blob = ("".join(src) if isinstance(src, list) else str(src)) + json.dumps(c.get("outputs") or [])
        if DATA_SECRET_RX.search(blob):
            out.append(("NB003", f"{rel}: secret-like value in cell {i + 1} (rotate it if it was ever committed)"))
            break
    return out


def data_problems(root: Path, cfg: dict | None = None, only: list[str] | None = None, base: str = "") -> dict:
    """Contract and notebook findings → errors (DAT005, DAT008, NB004, missing logicalType: warnings), minus rules
    allowed with a reason. `only`: relative paths to restrict to; `base`: git ref for DAT006 ("" = skip)."""
    cfg = cfg or data_cfg(root)
    raw: list[tuple[str, str]] = []
    ids: dict[str, str] = {}
    n_contracts = n_nb = 0
    for p in data_contract_files(root, cfg):
        rel = p.relative_to(root).as_posix()
        try:
            doc = load_yaml_or_json(read(p), rel)
        except (ValueError, YamlSubsetError) as exc:
            if only is None or rel in only:
                raw.append(("DAT001", f"{rel}: {exc}"))
                n_contracts += 1
            continue
        if isinstance(doc, dict) and doc.get("id"):
            cid = str(doc["id"])
            if cid in ids:
                raw.append(("DAT007", f"{rel}: id {cid} also used by {ids[cid]}"))
            ids.setdefault(cid, rel)
        if only is not None and rel not in only:
            continue
        n_contracts += 1
        raw += contract_findings(rel, doc)
        if base and isinstance(doc, dict):
            old = _contract_base_doc(root, base, rel)
            if old is not None:
                brk, other = contract_breaking(old, doc)
                ov, nv = old.get("version"), doc.get("version")
                if brk and _major(nv) <= _major(ov):
                    raw.append(
                        (
                            "DAT006",
                            f"{rel}: breaking vs {base[:12]} ({'; '.join(brk[:4])}) but version {ov} → {nv}: bump the major version, deprecate, tell consumers",
                        )
                    )
                elif (brk or other) and str(ov) == str(nv):
                    raw.append(
                        (
                            "DAT006w",
                            f"{rel}: schema changed vs {base[:12]} ({'; '.join((brk + other)[:3])}) but version is still {nv}",
                        )
                    )
    max_kb = float(cfg.get("notebook_max_kb", 500))
    for p in data_notebook_files(root, cfg):
        rel = p.relative_to(root).as_posix()
        if only is not None and rel not in only:
            continue
        n_nb += 1
        try:
            text = read(p)
        except (OSError, UnicodeDecodeError) as exc:
            raw.append(("NB000", f"{rel}: unreadable ({exc})"))
            continue
        raw += notebook_findings(rel, text, p.stat().st_size / 1024, max_kb)
    raw = [(r, m) for r, m in raw if only is None or m.split(":")[0] in only]
    errs, warns, allowed = [], [], []
    for rid, reason in cfg["allow"].items():
        if rid not in DATA_RULES:
            warns.append(f"data.allow: unknown rule {rid}")
        elif not str(reason).strip():
            errs.append(f"data.allow.{rid}: give a reason (who reviewed it and why)")
    for rid, msg in raw:
        base_id = rid.rstrip("w")
        if str(cfg["allow"].get(base_id, "")).strip():
            allowed.append(base_id)
            continue
        (warns if rid.endswith("w") or rid in DATA_WARN_ONLY else errs).append(f"{base_id} {msg}")
    return {
        "errors": errs,
        "warnings": warns,
        "contracts": n_contracts,
        "notebooks": n_nb,
        "allowed": sorted(set(allowed)),
    }


def _split_time(v: str) -> dt.datetime | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


SPLIT_OUTCOME_RX = _lazy_rx(
    r"(?i)(chargeback|refund(ed)?_(at|date|reason)|default(ed)?_(at|date|flag)|outcome|label|resolved|closed_at"
    r"|collections?_|write_?off|recover(ed|y)|_after_|^after_|^post_|future|days_past_due|dpd|fraud_confirmed)"
)


def split_problems(files: dict[str, Path], id_col: str = "", time_col: str = "", gap_days: float = 0,
                   target: str = "") -> dict:  # fmt: skip
    """Leakage checks across split CSV files: shared entity ids, identical rows, time order with a gap, and
    columns that (almost) determine the target or are named like outcomes. Returns errors, warnings, info."""
    errs: list[str] = []
    warns: list[str] = []
    info: list[str] = []
    order = [k for k in ("train", "val", "test") if k in files]
    ids: dict[str, set[str]] = {}
    rows: dict[str, set[str]] = {}
    times: dict[str, tuple[dt.datetime, dt.datetime]] = {}
    header: list[str] = []
    train_rows: list[dict] = []
    for name in order:
        with files[name].open(newline="", encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            cols = rd.fieldnames or []
            if not header:
                header = list(cols)
            elif list(cols) != header:
                warns.append(f"{name}: columns differ from {order[0]} ({len(cols)} vs {len(header)})")
            for c in (id_col, time_col, target):
                if c and c not in cols:
                    errs.append(f"{name}: column {c!r} not found")
                    return {"errors": errs, "warnings": warns, "info": info}
            ids[name], rows[name] = set(), set()
            dups = bad_t = n = pos = 0
            tmin = tmax = None
            for r in rd:
                n += 1
                h = hashlib.sha256("\x1f".join(str(r.get(c, "")) for c in cols).encode()).hexdigest()
                if h in rows[name]:
                    dups += 1
                rows[name].add(h)
                if id_col:
                    ids[name].add(str(r[id_col]))
                if time_col:
                    t = _split_time(str(r[time_col]))
                    if t is None:
                        bad_t += 1
                    else:
                        tmin = t if tmin is None or t < tmin else tmin
                        tmax = t if tmax is None or t > tmax else tmax
                if target and str(r[target]).strip().lower() in ("1", "true", "yes", "y", "t"):
                    pos += 1
                if name == "train" and len(train_rows) < 200000:
                    train_rows.append(r)
            line = f"{name}: {n} rows"
            if target and n:
                line += f", target rate {pos / n:.4f}"
            if tmin and tmax:
                times[name] = (tmin, tmax)
                line += f", {tmin.date()} → {tmax.date()}"
            info.append(line)
            if bad_t:
                warns.append(f"{name}: {bad_t} rows with an unparsable {time_col!r} (ISO 8601 expected)")
            if dups and name != "train":
                warns.append(f"{name}: {dups} duplicate rows inside the split (inflates or skews metrics)")
    for i, a in enumerate(order):
        for b in order[i + 1 :]:
            if id_col:
                shared = ids[a] & ids[b]
                if shared:
                    ex = ", ".join(sorted(shared)[:3])
                    errs.append(
                        f"SPL001 {len(shared)} {id_col} value(s) in both {a} and {b} (e.g. {ex}): split by entity (GroupKFold)"
                    )
            same = rows[a] & rows[b]
            if same:
                errs.append(f"SPL002 {len(same)} identical row(s) in both {a} and {b}: deduplicate before splitting")
            if a in times and b in times:
                gap = times[b][0] - times[a][1]
                need = dt.timedelta(days=gap_days)
                if gap <= dt.timedelta(0) or gap < need:
                    errs.append(
                        f"SPL003 {a} ends {times[a][1].isoformat()} but {b} starts {times[b][0].isoformat()}"
                        f" (gap {gap}; required > 0 and ≥ {gap_days:g} days): split by time with a label-delay gap"
                    )
    skip = {c for c in (id_col, time_col, target) if c}
    if target and len(train_rows) >= 50:
        n = len(train_rows)
        for c in header:
            if c in skip:
                continue
            groups: dict[str, set[str]] = {}
            for r in train_rows:
                groups.setdefault(str(r.get(c, "")), set()).add(str(r[target]))
            if len(groups) < 2 or len(groups) > n * 0.5:
                continue
            pure = sum(1 for r in train_rows if len(groups[str(r.get(c, ""))]) == 1)
            targets_seen = {str(r[target]) for r in train_rows}
            if pure / n >= 0.99 and len(targets_seen) > 1:
                warns.append(
                    f"SPL004 {c!r} alone determines {target!r} for {pure / n:.1%} of train rows: check for target leakage"
                )
    for c in header:
        if c not in skip and SPLIT_OUTCOME_RX.search(c):
            warns.append(f"SPL005 column {c!r} is named like an outcome: would it exist at prediction time?")
    return {"errors": errs, "warnings": warns, "info": info}


def cmd_data(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    cfg = data_cfg(root)
    if args.action == "rules":
        for rid, what in DATA_RULES.items():
            print(f"  {rid}{' (warn)' if rid in DATA_WARN_ONLY else ''}  {what}")
        print("  split: SPL001 shared ids · SPL002 identical rows · SPL003 time order/gap · SPL004 (warn) column"
              " determines target · SPL005 (warn) outcome-like column name")  # fmt: skip
        print('  allow one with a reason: "data": {"allow": {"NB002": "why, reviewed by whom"}} in .eos/config.json')
        return 0
    if args.action == "split":
        files = {k: Path(v) for k, v in (("train", args.train), ("val", args.val), ("test", args.test)) if v}
        if "train" not in files or "test" not in files:
            eprint("eos data split: give --train and --test (CSV with a header row); --val is optional")
            return 2
        for k, p in files.items():
            if not p.is_file():
                eprint(f"eos data split: {k} file not found: {p}")
                return 2
            if p.suffix.lower() not in (".csv", ".tsv", ".txt"):
                eprint(f"eos data split: {p.name}: export the split to CSV (e.g. duckdb -c \"COPY (...) TO 'x.csv'\")")
                return 2
        res = split_problems(files, args.id or "", args.time or "", float(args.gap_days or 0), args.target or "")
        if args.json:
            print(json.dumps(res, indent=1))
            return 1 if res["errors"] or (args.strict and res["warnings"]) else 0
        for ln in res["info"]:
            print("  " + ln)
        for w in res["warnings"]:
            print("  warn: " + w)
        for e in res["errors"]:
            print("  error: " + e)
        failed = bool(res["errors"]) or (args.strict and bool(res["warnings"]))
        print(
            f"eos data split: {'FAILED' if failed else 'OK'} ({len(res['errors'])} errors, {len(res['warnings'])} warnings)"
        )
        if not args.id and not args.time:
            print("  tip: pass --id <entity column> and --time <timestamp column> (--gap-days for label delay)")
        print(
            "  checklist: docs/ml/split-leakage-checklist.md (`eos scaffold ml`); ref: .eos/packs/ref/ml/framing-splits-leakage.md"
        )
        return 1 if failed else 0
    base = ""
    if args.base:
        base, _ = lane_base(root, args.base)
    res = data_problems(root, cfg, None, base)
    if args.json:
        print(json.dumps(res, indent=1))
        return 1 if res["errors"] or (args.strict and res["warnings"]) else 0
    for w in res["warnings"]:
        print("  warn: " + w)
    for e in res["errors"]:
        print("  error: " + e)
    failed = bool(res["errors"]) or (args.strict and bool(res["warnings"]))
    allowed = f"; allowed by config: {', '.join(res['allowed'])}" if res["allowed"] else ""
    print(
        f"eos data check: {'FAILED' if failed else 'OK'} ({res['contracts']} contracts, {res['notebooks']} notebooks;"
        f" {len(res['errors'])} errors, {len(res['warnings'])} warnings{allowed})"
    )
    if not res["contracts"] and not res["notebooks"]:
        print(
            "  no data contracts (*.odcs.yaml) or notebooks found (`eos scaffold analytics` adds an example contract)"
        )
    elif res["errors"] or res["warnings"]:
        print(
            "  rules: `eos data rules`; refs: .eos/packs/ref/analytics/quality-contracts.md, ml/notebooks-production.md"
        )
    return 1 if failed else 0


def data_extras(
    root: Path, m: dict, c: dict, full: bool, base: str | None = None
) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for data work. standard+: contract + notebook check (in-process, ms) on changed files,
    including breaking changes vs the lane base; a dbt note when models changed. risky/one-way-door/--full: every
    contract and notebook. Trivial/spike: nothing."""
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return [], []
    changed = [f for f in c["files"] if DATA_CHANGE_RX.search(f)]
    dbt_changed = [f for f in c["files"] if DBT_CHANGE_RX.search(f)]
    notes = []
    if dbt_changed:
        notes.append("data: dbt files changed: run `dbt build --select state:modified+` (CI builds and tests them)")
    if not changed and not full:
        return [], notes
    wide = full or c["risk"] in ("risky", "one-way-door")
    t0 = time.time()
    ref = lane_base(root, base)[0] if (root / ".git").exists() else ""
    res = data_problems(root, data_cfg(root), None if wide else changed, ref)
    notes += [f"data: {w}" for w in res["warnings"][:6]]
    results: list[tuple[str, int, str, float]] = []
    if res["contracts"] or res["notebooks"]:
        results.append(
            ("contracts + notebooks (data)", 1 if res["errors"] else 0, "\n".join(res["errors"]), time.time() - t0)
        )
    return results, notes


# ----------------------------------------------------------------------------- design: DTCG tokens, contrast, generic-look lint
DESIGN_DEFAULTS = {
    "tokens": [],  # token files or globs; [] = every *.tokens.json / *.tokens outside build folders
    "css": [],  # CSS files with theme variables; [] = auto (CSS in code dirs that defines --background or --*-foreground)
    "code_dirs": ["src", "app", "components", "lib", "pages", "features", "ui", "styles", "screens"],
    "contrast_min": 4.5,  # WCAG 2.2 AA body text; large-text or non-text pairs set their own "min" (3)
    "contrast_pairs": [],  # [{"fg": "color.text.muted", "bg": "color.surface", "min": 4.5}]; CSS: "--muted-foreground"
    "contrast_ignore": [],  # foreground names whose naming-convention pair is not used as text (write why in a PR)
    "raw_colors": "warn",  # literal colours in components: "warn" | "error" | "off"
    "generic": "warn",  # generic-AI-look heuristics: "warn" | "error" | "off"
    "allow_files": [],  # globs where literal colours are expected (charts, emails, OG images)
    "stock_palette_max": 25,  # stock Tailwind palette classes (bg-indigo-600 …) before a warning
}
DESIGN_SKIP_DIRS = {
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "out",
    "coverage",
    ".expo",
    ".turbo",
    ".eos",
    "vendor",
}
DTCG_TYPES = {
    "color", "dimension", "fontFamily", "fontWeight", "duration", "cubicBezier", "number",
    "strokeStyle", "border", "transition", "shadow", "gradient", "typography",
}  # fmt: skip
DTCG_GROUP_PROPS = {"$type", "$description", "$extensions", "$deprecated", "$extends", "$root", "$schema"}
DTCG_TOKEN_PROPS = {"$value", "$type", "$description", "$extensions", "$deprecated"}
DTCG_SPACES = {  # component ranges per DTCG Color Module 2025.10 (None = unbounded; hue is [0, 360))
    "srgb": [(0, 1)] * 3, "srgb-linear": [(0, 1)] * 3, "display-p3": [(0, 1)] * 3, "a98-rgb": [(0, 1)] * 3,
    "prophoto-rgb": [(0, 1)] * 3, "rec2020": [(0, 1)] * 3, "xyz-d65": [(0, 1)] * 3, "xyz-d50": [(0, 1)] * 3,
    "hsl": [(0, 360), (0, 100), (0, 100)], "hwb": [(0, 360), (0, 100), (0, 100)],
    "lab": [(0, 100), None, None], "lch": [(0, 100), (0, None), (0, 360)],
    "oklab": [(0, 1), None, None], "oklch": [(0, 1), (0, None), (0, 360)],
}  # fmt: skip
DTCG_WEIGHTS = {
    "thin", "hairline", "extra-light", "ultra-light", "light", "normal", "regular", "book", "medium",
    "semi-bold", "demi-bold", "bold", "extra-bold", "ultra-bold", "black", "heavy", "extra-black", "ultra-black",
}  # fmt: skip
DTCG_STROKES = {"solid", "dashed", "dotted", "double", "groove", "ridge", "outset", "inset"}
DTCG_COMPOSITE = {  # sub-value types; "?" marks optional keys
    "border": {"color": "color", "width": "dimension", "style": "strokeStyle"},
    "transition": {"duration": "duration", "delay": "duration", "timingFunction": "cubicBezier"},
    "shadow": {"color": "color", "offsetX": "dimension", "offsetY": "dimension", "blur": "dimension",
               "spread": "dimension", "inset?": "boolean"},
    "typography": {"fontFamily": "fontFamily", "fontSize": "dimension", "fontWeight": "fontWeight",
                   "letterSpacing": "dimension", "lineHeight": "number"},
}  # fmt: skip
ALIAS_RX = _lazy_rx(r"^\{([^{}]+)\}$")
CSS_COLOR_RX = _lazy_rx(
    r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch|color)\(",
)


def design_cfg(root: Path) -> dict:
    d = _load_cfg(root).get("design", {})
    return {**DESIGN_DEFAULTS, **(d if isinstance(d, dict) else {})}


def _design_walk(root: Path, dirs: list[str] | None = None):
    bases = [root / d for d in dirs] if dirs else [root]
    seen: set[Path] = set()
    for base in bases:
        if not base.is_dir():
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(d for d in dns if d not in DESIGN_SKIP_DIRS and not d.startswith("."))
            for fn in sorted(fns):
                p = Path(dp) / fn
                if p not in seen and not p.is_symlink():
                    seen.add(p)
                    yield p


def design_token_files(root: Path, cfg: dict) -> list[Path]:
    if cfg["tokens"]:
        out: list[Path] = []
        for g in cfg["tokens"]:
            out += [p for p in sorted(root.glob(g)) if p.is_file()]
        return out
    return [p for p in _design_walk(root) if p.name.endswith((".tokens.json", ".tokens"))]


# -- colour maths (CSS Color 4 conversions; WCAG 2 relative luminance) --------
def _mat(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(a * b for a, b in zip(row, v, strict=True)) for row in m]


_XYZ65_TO_LSRGB = [
    [3.2409699419045226, -1.537383177570094, -0.4986107602930034],
    [-0.9692436362808796, 1.8759675015077202, 0.04155505740717559],
    [0.05563007969699366, -0.20397695888897652, 1.0569715142428786],
]
_D50_TO_D65 = [
    [0.9554734527042182, -0.023098536874261423, 0.0632593086610217],
    [-0.028369706963208136, 1.0099954580058226, 0.021041398966943008],
    [0.012314001688319899, -0.020507696433477912, 1.3303659366080753],
]
_LIN_TO_XYZ = {  # linear RGB -> XYZ (D65, except ProPhoto which is D50)
    "display-p3": [[0.4865709486482162, 0.26566769316909306, 0.1982172852343625],
                   [0.2289745640697488, 0.6917385218365064, 0.079286914093745],
                   [0.0, 0.04511338185890264, 1.043944368900976]],
    "rec2020": [[0.6369580483012914, 0.14461690358620832, 0.1688809751641721],
                [0.2627002120112671, 0.6779980715188708, 0.05930171646986196],
                [0.0, 0.028072693049087428, 1.060985057710791]],
    "a98-rgb": [[0.5766690429101305, 0.1855582379065463, 0.1882286462349947],
                [0.29734497525053605, 0.6273635662554661, 0.07529145849399788],
                [0.02703136138641234, 0.07068885253582723, 0.9913375368376388]],
    "prophoto-rgb": [[0.7977604896723027, 0.13518583717574031, 0.0313493495815248],
                     [0.2880711282292934, 0.7118432178101014, 0.00008565396060525902],
                     [0.0, 0.0, 0.8251046025104601]],
}  # fmt: skip


def _srgb_to_lin(v: float) -> float:
    a = abs(v)
    return math.copysign(a / 12.92 if a <= 0.04045 else ((a + 0.055) / 1.055) ** 2.4, v)


def _lin_to_srgb(v: float) -> float:
    a = abs(v)
    return math.copysign(a * 12.92 if a <= 0.0031308 else 1.055 * a ** (1 / 2.4) - 0.055, v)


def _hsl_to_srgb(h: float, s: float, light: float) -> list[float]:
    s, light = s / 100, light / 100

    def f(n: float) -> float:
        k = (n + h / 30) % 12
        return light - s * min(light, 1 - light) * max(-1, min(k - 3, 9 - k, 1))

    return [f(0), f(8), f(4)]


def color_to_linear_srgb(space: str, comps: list) -> list[float] | None:
    """Linear-light sRGB (unclipped) for a colour in any DTCG colour space; None if it can't be converted."""
    c = [0.0 if x == "none" else float(x) for x in comps]
    if space == "srgb":
        return [_srgb_to_lin(x) for x in c]
    if space == "srgb-linear":
        return c
    if space == "hsl":
        return [_srgb_to_lin(x) for x in _hsl_to_srgb(*c)]
    if space == "hwb":
        w, b = c[1] / 100, c[2] / 100
        if w + b >= 1:
            return [_srgb_to_lin(w / (w + b))] * 3
        return [_srgb_to_lin(x * (1 - w - b) + w) for x in _hsl_to_srgb(c[0], 100, 50)]
    if space in ("oklch", "lch"):
        light, ch, hue = c
        c = [light, ch * math.cos(math.radians(hue)), ch * math.sin(math.radians(hue))]
        space = space.replace("lch", "lab")
    if space == "oklab":
        light, a, b = c
        lms = [
            (light + 0.3963377774 * a + 0.2158037573 * b) ** 3,
            (light - 0.1055613458 * a - 0.0638541728 * b) ** 3,
            (light - 0.0894841775 * a - 1.2914855480 * b) ** 3,
        ]
        return _mat(
            [
                [4.0767416621, -3.3077115913, 0.2309699292],
                [-1.2684380046, 2.6097574011, -0.3413193965],
                [-0.0041960863, -0.7034186147, 1.7076147010],
            ],
            lms,
        )
    if space == "lab":
        light, a, b = c
        kappa, eps = 24389 / 27, 216 / 24389
        fy = (light + 16) / 116
        fx, fz = a / 500 + fy, fy - b / 200
        xyz = [
            fx**3 if fx**3 > eps else (116 * fx - 16) / kappa,
            ((light + 16) / 116) ** 3 if light > kappa * eps else light / kappa,
            fz**3 if fz**3 > eps else (116 * fz - 16) / kappa,
        ]
        white = [0.3457 / 0.3585, 1.0, (1 - 0.3457 - 0.3585) / 0.3585]
        return _mat(_XYZ65_TO_LSRGB, _mat(_D50_TO_D65, [x * w for x, w in zip(xyz, white, strict=True)]))
    if space == "xyz-d65":
        return _mat(_XYZ65_TO_LSRGB, c)
    if space == "xyz-d50":
        return _mat(_XYZ65_TO_LSRGB, _mat(_D50_TO_D65, c))
    if space == "display-p3":
        return _mat(_XYZ65_TO_LSRGB, _mat(_LIN_TO_XYZ[space], [_srgb_to_lin(x) for x in c]))
    if space == "rec2020":
        al, be = 1.09929682680944, 0.018053968510807
        lin = [
            math.copysign(abs(x) / 4.5 if abs(x) < be * 4.5 else ((abs(x) + al - 1) / al) ** (1 / 0.45), x) for x in c
        ]
        return _mat(_XYZ65_TO_LSRGB, _mat(_LIN_TO_XYZ[space], lin))
    if space == "a98-rgb":
        return _mat(_XYZ65_TO_LSRGB, _mat(_LIN_TO_XYZ[space], [math.copysign(abs(x) ** (563 / 256), x) for x in c]))
    if space == "prophoto-rgb":
        lin = [math.copysign(abs(x) / 16 if abs(x) <= 16 / 512 else abs(x) ** 1.8, x) for x in c]
        return _mat(_XYZ65_TO_LSRGB, _mat(_D50_TO_D65, _mat(_LIN_TO_XYZ[space], lin)))
    return None


def _clip_hex(lin: list[float]) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, _lin_to_srgb(x))) * 255):02x}" for x in lin)


def _in_gamut(lin: list[float]) -> bool:
    return all(-0.0005 <= _lin_to_srgb(x) <= 1.0005 for x in lin)


def rel_luminance(lin: list[float]) -> float:
    """WCAG 2 relative luminance of a colour clipped to the sRGB gamut."""
    r, g, b = (_srgb_to_lin(min(1.0, max(0.0, _lin_to_srgb(x)))) for x in lin)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[list[float], float], bg: tuple[list[float], float]) -> float:
    """WCAG 2 contrast; a translucent foreground is composited over the background first (gamma space, like browsers)."""
    (f, fa), (b, _) = fg, bg
    if fa < 1:
        fs = [min(1.0, max(0.0, _lin_to_srgb(x))) for x in f]
        bs = [min(1.0, max(0.0, _lin_to_srgb(x))) for x in b]
        f = [_srgb_to_lin(x * fa + y * (1 - fa)) for x, y in zip(fs, bs, strict=True)]
    hi, lo = sorted((rel_luminance(f), rel_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


_CSS_NAMED = {"white": "#ffffff", "black": "#000000", "transparent": "#00000000"}


def parse_css_color(text: str) -> tuple[list[float], float] | None:
    """(linear sRGB, alpha) for a CSS colour: hex, rgb(), hsl(), hwb(), oklch(), oklab(), lab(), lch(), color(),
    a few keywords, and the bare "H S% L%" triplets older shadcn themes use inside hsl(var(--x))."""
    t = text.strip().lower()
    t = _CSS_NAMED.get(t, t)
    if t.startswith("#"):
        h = t[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8) or not re.fullmatch(r"[0-9a-f]+", h):
            return None
        rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        return [_srgb_to_lin(x) for x in rgb], (int(h[6:8], 16) / 255 if len(h) == 8 else 1.0)
    if re.fullmatch(r"-?[\d.]+(?:deg)?\s+[\d.]+%\s+[\d.]+%(?:\s*/\s*[\d.]+%?)?", t):
        t = f"hsl({t})"
    m = re.fullmatch(r"(rgba?|hsla?|hwb|oklch|oklab|lab|lch|color)\((.*)\)", t)
    if not m:
        return None
    fn, body = m.group(1), m.group(2).replace(",", " ")
    alpha = 1.0
    if "/" in body:
        body, a = body.split("/", 1)
        a = a.strip()
        try:
            alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        except ValueError:
            return None
    parts = body.split()
    if fn == "color":
        if not parts:
            return None
        space, parts = parts[0], parts[1:]
    elif fn in ("rgba", "hsla"):
        space = fn[:3]
    else:
        space = fn
    if fn in ("rgb", "rgba", "hsl", "hsla") and len(parts) == 4:
        parts, a = parts[:3], parts[3]
        alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
    if len(parts) != 3:
        return None
    vals: list[float] = []
    pct_scale = {"rgb": 1, "oklch": 1, "oklab": 1, "lab": 100, "lch": 100}
    for i, p in enumerate(parts):
        try:
            if p == "none":
                vals.append(0.0)
            elif p.endswith("%"):
                n = float(p[:-1])
                if space in ("hsl", "hwb"):
                    vals.append(n)
                elif space == "rgb":
                    vals.append(n / 100 * 255)
                elif i == 0:
                    vals.append(n / 100 * pct_scale.get(space, 1))
                else:
                    vals.append(n / 100 * {"oklch": 0.4, "oklab": 0.4, "lab": 125, "lch": 150}.get(space, 1))
            else:
                vals.append(float(p.removesuffix("deg")))
        except ValueError:
            return None
    if space == "rgb":
        space, vals = "srgb", [v / 255 for v in vals]
    lin = color_to_linear_srgb(space, vals)
    return (lin, alpha) if lin is not None else None


# -- DTCG validation ---------------------------------------------------------
def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _dtcg_value_problems(t: str, v: object, where: str, refs: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Errors and warnings for one value of DTCG type t. Alias strings are collected in refs, not checked here."""
    errs: list[str] = []
    warns: list[str] = []
    if isinstance(v, str) and ALIAS_RX.match(v):
        refs.append((where, ALIAS_RX.match(v).group(1)))
        return errs, warns
    if isinstance(v, dict) and set(v) == {"$ref"}:
        return errs, warns  # JSON Pointer reference, resolved by the caller
    if t == "color":
        if isinstance(v, str):
            if parse_css_color(v):
                warns.append(f"{where}: string colour {v!r} is the pre-2025.10 form; 2025.10 wants an object "
                             f"{{colorSpace, components, alpha?, hex?}} (Style Dictionary 4+ reads both)")  # fmt: skip
            else:
                errs.append(f"{where}: colour must be an object {{colorSpace, components}} (got {v!r})")
            return errs, warns
        if not isinstance(v, dict):
            return [f"{where}: colour must be an object {{colorSpace, components}}"], warns
        sp, comps = v.get("colorSpace"), v.get("components")
        if sp not in DTCG_SPACES:
            errs.append(f"{where}: colorSpace {sp!r} is not one of {', '.join(sorted(DTCG_SPACES))}")
        elif not isinstance(comps, list) or len(comps) != 3:
            errs.append(f'{where}: components must be a list of 3 numbers (or "none")')
        else:
            for i, (x, rng) in enumerate(zip(comps, DTCG_SPACES[sp], strict=True)):
                if x == "none":
                    continue
                if not _num(x):
                    errs.append(f'{where}: component {i} must be a number or "none" (got {x!r})')
                elif rng and (
                    (rng[0] is not None and x < rng[0])
                    or (rng[1] is not None and (x >= rng[1] if rng[1] == 360 else x > rng[1]))
                ):
                    errs.append(f"{where}: component {i} = {x} is outside {sp} range {rng[0]}..{rng[1]}")
        a = v.get("alpha", 1)
        if not _num(a) or not 0 <= a <= 1:
            errs.append(f"{where}: alpha must be a number from 0 to 1")
        hx = v.get("hex")
        if hx is not None:
            if not (isinstance(hx, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", hx)):
                errs.append(f"{where}: hex fallback must be 6-digit #rrggbb (got {hx!r})")
            elif not errs:
                lin = color_to_linear_srgb(sp, comps)
                if lin and _in_gamut(lin):
                    want = _clip_hex(lin)
                    if max(abs(int(want[i : i + 2], 16) - int(hx[i : i + 2], 16)) for i in (1, 3, 5)) > 3:
                        warns.append(f"{where}: hex fallback {hx} does not match the components (≈ {want})")
        extra = set(v) - {"colorSpace", "components", "alpha", "hex"}
        if extra:
            warns.append(f"{where}: unknown colour keys {sorted(extra)}")
    elif t in ("dimension", "duration"):
        units = ("px", "rem") if t == "dimension" else ("ms", "s")
        if isinstance(v, str) and re.fullmatch(r"-?[\d.]+(" + "|".join(units) + ")", v):
            warns.append(f'{where}: string {t} {v!r} is the pre-2025.10 form; use {{"value": n, "unit": "{units[0]}"}}')
        elif _num(v):
            errs.append(f'{where}: {t} needs a unit, even for 0: {{"value": {v}, "unit": "{units[0]}"}}')
        elif not (isinstance(v, dict) and _num(v.get("value")) and v.get("unit") in units):
            errs.append(f'{where}: {t} must be {{"value": number, "unit": {" or ".join(units)}}}')
    elif t == "fontFamily":
        if not (isinstance(v, str) and v.strip()) and not (
            isinstance(v, list) and v and all(isinstance(x, str) and x.strip() for x in v)
        ):
            errs.append(f"{where}: fontFamily must be a string or a non-empty list of strings")
    elif t == "fontWeight":
        if not ((_num(v) and 1 <= v <= 1000) or (isinstance(v, str) and v in DTCG_WEIGHTS)):
            errs.append(f"{where}: fontWeight must be 1–1000 or a named weight (bold, semi-bold …), got {v!r}")
    elif t == "cubicBezier":
        if not (isinstance(v, list) and len(v) == 4 and all(_num(x) for x in v)):
            errs.append(f"{where}: cubicBezier must be 4 numbers [x1, y1, x2, y2]")
        elif not (0 <= v[0] <= 1 and 0 <= v[2] <= 1):
            errs.append(f"{where}: cubicBezier x values must be within 0..1")
    elif t == "number":
        if not _num(v):
            errs.append(f"{where}: number token must be a JSON number")
    elif t == "boolean":
        if not isinstance(v, bool):
            errs.append(f"{where}: must be true or false")
    elif t == "strokeStyle":
        if isinstance(v, str):
            if v not in DTCG_STROKES:
                errs.append(f"{where}: strokeStyle must be one of {', '.join(sorted(DTCG_STROKES))}")
        elif not (
            isinstance(v, dict)
            and isinstance(v.get("dashArray"), list)
            and v.get("lineCap") in ("round", "butt", "square")
        ):
            errs.append(f"{where}: strokeStyle object needs dashArray (list) and lineCap (round|butt|square)")
        else:
            for i, d in enumerate(v["dashArray"]):
                e, w = _dtcg_value_problems("dimension", d, f"{where}.dashArray[{i}]", refs)
                errs, warns = errs + e, warns + w
    elif t == "gradient":
        if not (isinstance(v, list) and v):
            errs.append(f"{where}: gradient must be a list of {{color, position}} stops")
        else:
            for i, stop in enumerate(v):
                if not isinstance(stop, dict) or "color" not in stop or "position" not in stop:
                    errs.append(f"{where}[{i}]: gradient stop needs color and position")
                    continue
                e, w = _dtcg_value_problems("color", stop["color"], f"{where}[{i}].color", refs)
                errs, warns = errs + e, warns + w
                pos = stop["position"]
                if not (isinstance(pos, str) and ALIAS_RX.match(pos)) and not (_num(pos) and 0 <= pos <= 1):
                    errs.append(f"{where}[{i}]: position must be a number from 0 to 1")
                elif isinstance(pos, str):
                    refs.append((f"{where}[{i}].position", ALIAS_RX.match(pos).group(1)))
    elif t in DTCG_COMPOSITE:
        layers = v if t == "shadow" and isinstance(v, list) else [v]
        for li, layer in enumerate(layers):
            w0 = f"{where}[{li}]" if len(layers) > 1 or isinstance(v, list) else where
            if not isinstance(layer, dict):
                errs.append(f"{w0}: {t} must be an object")
                continue
            for key, sub in DTCG_COMPOSITE[t].items():
                k, optional = key.rstrip("?"), key.endswith("?")
                if k not in layer:
                    if not optional:
                        errs.append(f"{w0}: {t} is missing {k}")
                    continue
                e, w = _dtcg_value_problems(sub, layer[k], f"{w0}.{k}", refs)
                errs, warns = errs + e, warns + w
    return errs, warns


def dtcg_collect(doc: object, fname: str) -> tuple[dict[str, dict], list[str], list[str]]:
    """Walk one DTCG file: {path: {"type", "value", "file"}} plus errors and warnings (names, types, values)."""
    toks: dict[str, dict] = {}
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(doc, dict):
        return toks, [f"{fname}: top level must be a JSON object (a group)"], warns

    def walk(node: dict, path: list[str], inherited: str | None) -> None:
        gtype = node.get("$type", inherited)
        if "$type" in node and node["$type"] not in DTCG_TYPES:
            errs.append(f"{fname}: {'.'.join(path) or '(root)'}: unknown $type {node['$type']!r}")
        for key, val in node.items():
            if key.startswith("$") and key != "$root":
                if key not in DTCG_GROUP_PROPS:
                    warns.append(
                        f"{fname}: {'.'.join(path) or '(root)'}: unknown property {key!r} ($ names are reserved)"
                    )
                continue
            p = [*path, key]
            dotted = ".".join(p)
            if key != "$root" and any(ch in key for ch in "{}."):
                errs.append(f"{fname}: {dotted}: names must not contain '{{', '}}' or '.'")
            if not isinstance(val, dict):
                errs.append(f"{fname}: {dotted}: must be an object (a token with $value, or a group)")
                continue
            if "$value" in val:
                t = val.get("$type", gtype)
                if "$type" in val and val["$type"] not in DTCG_TYPES:
                    errs.append(f"{fname}: {dotted}: unknown $type {val['$type']!r}")
                    t = None
                children = [k for k in val if not k.startswith("$")]
                if children:
                    errs.append(f"{fname}: {dotted}: a token can't contain child tokens or groups ({children[0]})")
                for k in val:
                    if k.startswith("$") and k not in DTCG_TOKEN_PROPS:
                        warns.append(f"{fname}: {dotted}: unknown token property {k!r}")
                if "$deprecated" in val and not isinstance(val["$deprecated"], (bool, str)):
                    errs.append(f"{fname}: {dotted}: $deprecated must be true/false or an explanation string")
                toks[dotted] = {
                    "type": t,
                    "value": val["$value"],
                    "file": fname,
                    "explicit": "$type" in val or bool(gtype),
                }
            elif key == "$root":
                errs.append(f"{fname}: {dotted}: $root must be a token (needs $value)")
            else:
                walk(val, p, gtype)

    walk(doc, [], None)
    return toks, errs, warns


def _json_pointer(doc: object, ptr: str) -> object:
    cur = doc
    for part in ptr.lstrip("#").strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(ptr)
    return cur


def dtcg_problems(files: list[tuple[str, object]]) -> tuple[dict[str, dict[str, dict]], list[str], list[str]]:
    """Validate DTCG documents together (aliases may cross files; a later file may override a path, e.g. a
    dark theme). Returns per-file resolved tokens {file: {path: {"type", "value"}}}, errors, warnings."""
    errs: list[str] = []
    warns: list[str] = []
    per_file: dict[str, dict[str, dict]] = {}
    for fname, doc in files:
        toks, e, w = dtcg_collect(doc, fname)
        per_file[fname] = toks
        errs += e
        warns += w
        for path, tk in toks.items():
            v = tk["value"]
            if isinstance(v, dict) and set(v) == {"$ref"}:
                try:
                    target = _json_pointer(doc, str(v["$ref"]))
                    tk["value"] = target["$value"] if isinstance(target, dict) and "$value" in target else target
                except (KeyError, TypeError):
                    errs.append(f"{fname}: {path}: $ref {v['$ref']!r} does not resolve")
                    continue
    merged: dict[str, dict] = {}
    for toks in per_file.values():
        merged.update(toks)
    out: dict[str, dict[str, dict]] = {}
    for fname, toks in per_file.items():
        view = {**merged, **toks}  # a file sees its own definitions first (theme overrides)
        resolved: dict[str, dict] = {}
        for path, tk in toks.items():
            seen = [path]
            cur = tk
            ok = True
            while isinstance(cur["value"], str) and ALIAS_RX.match(cur["value"]):
                ref = ALIAS_RX.match(cur["value"]).group(1)
                if ref in seen:
                    errs.append(f"{fname}: {path}: alias cycle {' -> '.join(seen + [ref])}")
                    ok = False
                    break
                nxt = view.get(ref) or view.get(ref + ".$root")
                if nxt is None:
                    errs.append(f"{fname}: {path}: alias {{{ref}}} does not point to a token")
                    ok = False
                    break
                seen.append(ref)
                cur = nxt
            if not ok:
                continue
            t = tk["type"] if tk["type"] else cur["type"]
            if tk["type"] and cur["type"] and tk["type"] != cur["type"] and cur is not tk:
                errs.append(f"{fname}: {path}: $type {tk['type']} but its alias resolves to a {cur['type']} token")
                continue
            if not t:
                errs.append(f"{fname}: {path}: no $type (set it on the token or a parent group; tools must not guess)")
                continue
            if cur is tk:
                refs: list[tuple[str, str]] = []
                e, w = _dtcg_value_problems(t, tk["value"], f"{fname}: {path}", refs)
                errs += e
                warns += w
                for where, ref in refs:
                    if ref not in view and ref + ".$root" not in view:
                        errs.append(f"{where}: alias {{{ref}}} does not point to a token")
            resolved[path] = {"type": t, "value": cur["value"]}
        out[fname] = resolved
    return out, errs, warns


def _dtcg_color(v: object) -> tuple[list[float], float] | None:
    if isinstance(v, str):
        return parse_css_color(v)
    if isinstance(v, dict) and v.get("colorSpace") in DTCG_SPACES and isinstance(v.get("components"), list):
        try:
            lin = color_to_linear_srgb(v["colorSpace"], v["components"])
        except (TypeError, ValueError):
            return None
        a = v.get("alpha", 1)
        return (lin, float(a) if _num(a) else 1.0) if lin else None
    return None


def _auto_pairs(names: list[str], sep: str) -> list[tuple[str, str]]:
    """Foreground/background pairs by naming convention: X + X-foreground, X + on-X, background + foreground."""
    have = set(names)
    pairs = []
    for n in names:
        head, _, leaf = n.rpartition(sep) if sep in n else ("", "", n)
        pre = head + sep if head else ""
        low = leaf.lower()
        cand = None
        if low == "foreground":
            cand = pre + "background"
        elif low.endswith("-foreground") or low.endswith("foreground") and leaf[:-10].endswith(("-", "_")):
            cand = pre + leaf[: -len("foreground")].rstrip("-_")
        elif leaf.endswith("Foreground") and len(leaf) > 10:
            cand = pre + leaf[:-10]
        elif low.startswith("on-") or (leaf.startswith("on") and len(leaf) > 2 and leaf[2].isupper()):
            rest = leaf[3:] if low.startswith("on-") else leaf[2].lower() + leaf[3:]
            cand = pre + rest
        if cand and cand in have and cand != n:
            pairs.append((n, cand))
    return pairs


def css_theme_vars(text: str) -> dict[str, dict[str, str]]:
    """Custom properties per theme block: {"base": {...}, ".dark": {...}, "@media (prefers-color-scheme: dark)
    :root": {...}}. "base" is :root / html / @theme outside any @media; @layer wrappers are ignored."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    themes: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    pos = 0
    for m in re.finditer(r"[{}]", text):
        chunk = text[pos : m.start()]
        pos = m.end()
        if m.group() == "{":
            stack.append(" ".join(chunk.rsplit(";", 1)[-1].split()))
            continue
        if not stack:
            continue
        sel = stack.pop()
        decls = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)", chunk))
        if not decls:
            continue
        ctx = [x for x in stack if not x.startswith("@layer")]
        root_like = re.fullmatch(r"(:root|html|@theme(\s+\w+)*|:host)(\s*,\s*(:root|html|:host))*", sel)
        key = "base" if root_like and not ctx else " ".join([*ctx, sel])
        themes.setdefault(key, {}).update(decls)
    return themes


def _css_resolve(name: str, env: dict[str, str], depth: int = 0) -> str | None:
    v = env.get(name)
    if v is None or depth > 10:
        return None
    for _ in range(10):
        m = re.search(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)", v)
        if not m:
            break
        sub = _css_resolve(m.group(1), env, depth + 1)
        if sub is None:
            sub = (m.group(2) or "").strip()
            if not sub:
                return None
        v = v[: m.start()] + sub + v[m.end() :]
    return v


def design_css_files(root: Path, cfg: dict) -> list[Path]:
    if cfg["css"]:
        return [p for g in cfg["css"] for p in sorted(root.glob(g)) if p.is_file()]
    dirs = [px + d for px in _app_prefixes(root) for d in cfg["code_dirs"]]
    out = []
    for p in _design_walk(root, dirs):
        if p.suffix in (".css", ".scss"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"--(?:[\w-]*-)?(?:background|foreground)\s*:", t):
                out.append(p)
    return out


def design_contrast(root: Path, cfg: dict, resolved: dict[str, dict[str, dict]]) -> tuple[list[str], list[str], int]:
    """WCAG 2 contrast for token pairs (configured pairs + naming convention), in DTCG files and CSS themes."""
    errs: list[str] = []
    notes: list[str] = []
    checked = 0
    default_min = float(cfg.get("contrast_min", 4.5))
    conf = [p for p in cfg.get("contrast_pairs", []) if isinstance(p, dict) and p.get("fg") and p.get("bg")]
    ignore = set(cfg.get("contrast_ignore", []))

    def judge(where: str, fg_n: str, bg_n: str, fg: object, bg: object, need: float) -> None:
        nonlocal checked
        if fg is None or bg is None:
            notes.append(f"{where}: {fg_n} on {bg_n}: colour not parseable, not checked")
            return
        if bg[1] < 1:
            notes.append(f"{where}: {bg_n} is translucent, contrast depends on what is behind it (not checked)")
            return
        checked += 1
        r = contrast_ratio(fg, bg)
        if r < need:  # WCAG thresholds are not rounded: 4.499:1 fails 4.5:1
            errs.append(
                f"{where}: {fg_n} on {bg_n} contrast {math.floor(r * 100) / 100:.2f}:1 < {need:g}:1 (WCAG 2.2 AA)"
            )

    all_paths = sorted({p for toks in resolved.values() for p in toks})
    for fname, toks in resolved.items():
        colors = {p: tk["value"] for p, tk in toks.items() if tk["type"] == "color"}
        merged = {p: tk["value"] for f2, t2 in resolved.items() for p, tk in t2.items() if tk["type"] == "color"}
        merged.update(colors)
        pairs = [
            (a, b, default_min) for a, b in _auto_pairs([p for p in all_paths if p in merged], ".") if a not in ignore
        ]
        pairs += [(p["fg"].strip("{}"), p["bg"].strip("{}"), float(p.get("min", default_min))) for p in conf]
        for fg_n, bg_n, need in pairs:
            if fg_n not in colors and bg_n not in colors:
                continue  # judged in the file that defines them
            if fg_n not in merged or bg_n not in merged:
                if not fg_n.startswith("--"):
                    notes.append(f"{fname}: contrast pair {fg_n} / {bg_n}: token not found")
                continue
            judge(fname, fg_n, bg_n, _dtcg_color(merged[fg_n]), _dtcg_color(merged[bg_n]), need)
    for p in design_css_files(root, cfg):
        rel = p.relative_to(root).as_posix()
        themes = css_theme_vars(p.read_text(encoding="utf-8", errors="replace"))
        base = themes.get("base", {})
        for theme, decls in themes.items():
            env = base if theme == "base" else {**base, **decls}
            names = sorted(env)
            pairs = [(a, b, default_min) for a, b in _auto_pairs([n[2:] for n in names], "\x00")]
            pairs = [("--" + a, "--" + b, need) for a, b, need in pairs if "--" + a not in ignore]
            pairs += [
                (c["fg"], c["bg"], float(c.get("min", default_min))) for c in conf if str(c["fg"]).startswith("--")
            ]
            seen: set[tuple[str, str]] = set()
            for fg_n, bg_n, need in pairs:
                if theme != "base" and fg_n not in decls and bg_n not in decls:
                    continue
                if fg_n not in env or bg_n not in env:
                    continue
                fv, bv = _css_resolve(fg_n, env), _css_resolve(bg_n, env)
                if (fv or fg_n, bv or bg_n) in seen:
                    continue  # --color-primary-foreground: var(--primary-foreground) repeats a pair already judged
                seen.add((fv or fg_n, bv or bg_n))
                where = f"{rel} [{':root' if theme == 'base' else theme}]"
                judge(where, fg_n, bg_n, parse_css_color(fv) if fv else None, parse_css_color(bv) if bv else None, need)
    return errs, notes, checked


# -- generic-AI-look lint ----------------------------------------------------
TW_PALETTE = (
    "red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|"
    "slate|gray|zinc|neutral|stone|mauve|olive|mist|taupe"
)
TW_UTIL = r"(?:bg|text|border(?:-[trblxy])?|ring|from|via|to|fill|stroke|outline|decoration|divide|accent|caret|shadow|placeholder)"
TW_STOCK_RX = _lazy_rx(r"(?<![\w-])" + TW_UTIL + r"-(?:" + TW_PALETTE + r")-(?:50|[1-9]00|950)(?![\w-])")
TW_ARBITRARY_COLOR_RX = _lazy_rx(r"(?<![\w-])" + TW_UTIL + r"-\[(?:#|rgba?\(|hsla?\(|oklch\(|oklab\(|color:)[^\]\s]*\]")
PURPLE_GRADIENT_RX = _lazy_rx(
    r"(?:bg-(?:gradient-to|linear-to|radial|conic)[\w-]*|linear-gradient)[^\n]{0,200}?"
    r"(?:(?:from|via|to)-(?:indigo|violet|purple|fuchsia)-\d{2,3}|--color-(?:indigo|violet|purple))"
    r"|(?:from|via|to)-(?:indigo|violet|purple|fuchsia)-\d{2,3}[^\n]{0,200}?bg-(?:gradient-to|linear-to)"
)
CSS_GRADIENT_RX = _lazy_rx(r"(?:linear|radial|conic)-gradient\(")
CSS_COLOR_LIT_RX = _lazy_rx(r"#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?|oklch|oklab|lch|lab|hwb)\([^()]*\)")


def is_violet(lin: list[float] | None) -> bool:
    """OKLCH hue 270-330 with real chroma: the indigo/violet/purple family our refs call a generic AI tell (blue
    tops out near 266, e.g. Tailwind blue-800)."""
    if not lin:
        return False
    _, c, h = _oklch_of([max(0.0, x) for x in lin])
    return c > 0.08 and 270 <= h <= 330


def violet_css_gradient(line: str) -> bool:
    """A CSS gradient with a literal purple/indigo/violet stop (the class-based check misses raw CSS)."""
    if not CSS_GRADIENT_RX.search(line):
        return False
    for m in CSS_COLOR_LIT_RX.finditer(line[CSS_GRADIENT_RX.search(line).start() :]):
        pc = parse_css_color(m.group(0))
        if pc and is_violet(pc[0]):
            return True
    return False


HEX_LITERAL_RX = _lazy_rx(
    r"""["'`]#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})["'`]|(?:color|fill|stroke|background(?:Color)?|borderColor)\s*[:=]\s*\{?\s*["'`](?:#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|oklch\()"""
)
EMOJI_RX = _lazy_rx(
    "[\U0001f300-\U0001f5ff\U0001f600-\U0001f64f\U0001f680-\U0001f6ff\U0001f900-\U0001f9ff\U0001fa70-\U0001faff\u2705\u2728\u274c\u26a1\u2b50\u23f3\u231b]"
)
MOTION_RX = _lazy_rx(
    r"@keyframes|(?<![\w-])animation\s*:|(?<![\w-])animate-(?!none\b)[\w-]+|transition(?:-property)?\s*:\s*[^;]*\b(?:transform|all)\b|"
    r"(?<![\w-])transition-(?:transform|all)(?![\w-])|from\s+[\"'](?:framer-motion|motion/react|motion|gsap|react-native-reanimated|lottie-react|lottie-react-native)[\"']|"
    r"scroll-behavior\s*:\s*smooth"
)
REDUCED_MOTION_RX = _lazy_rx(
    r"prefers-reduced-motion|motion-reduce:|motion-safe:|useReducedMotion|reducedMotion\s*=|ReduceMotion\.|isReduceMotionEnabled|"
    r"MotionConfig[^>]*reducedMotion"
)
DEFAULT_FONTS = {
    "inter", "roboto", "arial", "helvetica", "helvetica neue", "open sans", "lato", "geist", "geist sans",
    "geist mono", "space grotesk", "system-ui", "-apple-system", "blinkmacsystemfont", "segoe ui",
    "ui-sans-serif", "ui-serif", "ui-monospace", "sans-serif", "serif", "monospace", "inter variable",
}  # fmt: skip
UI_EXT = (".tsx", ".jsx", ".ts", ".js", ".mjs", ".vue", ".svelte", ".astro", ".html", ".css", ".scss", ".mdx")


def _font_families(rel: str, text: str) -> list[str]:
    fams: list[str] = []
    for names in re.findall(r"import\s*\{([^}]*)\}\s*from\s*[\"']next/font/google[\"']", text):
        fams += [n.split(" as ")[0].strip().replace("_", " ") for n in names.split(",") if n.strip()]
    if re.search(r"from\s*[\"'](?:next/font/local|expo-font)[\"']", text) or "localFont(" in text:
        fams.append("(local font)")
    fams += [m.replace("-", " ") for m in re.findall(r"from\s*[\"']@expo-google-fonts/([\w-]+)[\"']", text)]
    fams += [m.replace("-", " ").lower() for m in re.findall(r"from\s*[\"']geist/font/([\w-]+)[\"']", text)]
    fams += [m.replace("+", " ") for m in re.findall(r"fonts\.googleapis\.com/css2?\?family=([\w+]+)", text)]
    fams += [m.replace("+", " ") for m in re.findall(r"&family=([\w+]+)", text)]
    for decl in re.findall(r"(?:font-family|--font-[\w-]+)\s*:\s*([^;}{]+)", text):
        first = decl.split(",")[0].strip().strip("\"'")
        if first and not first.startswith("var("):
            fams.append(first)
    if re.search(r"tailwind\.config\.", rel):
        for decl in re.findall(r"fontFamily\s*:\s*\{([^}]*)\}", text, flags=re.DOTALL):
            fams += [m for m in re.findall(r"\[\s*[\"']([^\"']+)[\"']", decl)]
    if "@font-face" in text:
        fams.append("(local font)")
    return fams


def design_lint(root: Path, cfg: dict, only: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Generic-AI-look heuristics. Returns (raw-colour findings, generic-look findings), one line each.
    only = repo-relative files to scan (the lane's changed files); None = every UI file in the code dirs."""
    raw: list[str] = []
    gen: list[str] = []
    dirs = [px + d for px in _app_prefixes(root) for d in cfg["code_dirs"]]
    files: list[Path] = []
    if only is None:
        files = list(_design_walk(root, dirs))
        files += [p for p in root.glob("tailwind.config.*") if p.is_file()]
    else:
        files = [root / f for f in only if (root / f).is_file()]
    allow = [*cfg.get("allow_files", []), "**/*.tokens.json", "**/*.stories.*", "**/*.test.*", "**/*.spec.*"]
    fams: list[tuple[str, str]] = []
    motion_at: str | None = None
    reduced = False
    stock: list[str] = []
    css_seen = False
    for p in files:
        rel = p.relative_to(root).as_posix()
        if not rel.endswith(UI_EXT) and "tailwind.config." not in rel:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        is_css = p.suffix in (".css", ".scss")
        css_seen = css_seen or is_css
        skip_raw = any(fnmatch.fnmatch(rel, g) for g in allow)
        fams += [(rel, f) for f in _font_families(rel, text)]
        if REDUCED_MOTION_RX.search(text):
            reduced = True
        if motion_at is None and (m := MOTION_RX.search(text)):
            motion_at = f"{rel}:{text.count(chr(10), 0, m.start()) + 1}"
        if is_css and "--radius: 0.625rem" in text and re.search(r"--primary:\s*oklch\(0\.205 0 0\)", text):
            gen.append(
                f"{rel}: stock shadcn/ui theme (neutral base, --radius 0.625rem) left unchanged: set your own palette and radius"
            )
        emoji = 0
        in_block = False
        for i, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if is_css:
                in_block = in_block or "/*" in s
                if in_block:
                    in_block = "*/" not in s
                    continue
            if s.startswith(("//", "*", "/*", "<!--", "{/*")):
                continue
            if not skip_raw:
                if is_css:
                    for m in re.finditer(r"(?:^|[;{])\s*(-*[a-z-]+)\s*:\s*([^;{}]+)", line):
                        if not m.group(1).startswith("--") and CSS_COLOR_RX.search(
                            re.sub(r"var\([^)]*\)", "", m.group(2))
                        ):
                            raw.append(f"{rel}:{i}: literal colour in `{m.group(1)}`: use a token (var(--color-…))")
                            break
                else:
                    m = TW_ARBITRARY_COLOR_RX.search(line) or HEX_LITERAL_RX.search(line)
                    if m:
                        raw.append(f"{rel}:{i}: literal colour {m.group(0)[:40]!r}: use a semantic token class")
            if PURPLE_GRADIENT_RX.search(line) or violet_css_gradient(line):
                gen.append(
                    f"{rel}:{i}: purple/indigo/violet gradient, the most cited AI default: pick a colour from your direction"
                )
            stock += TW_STOCK_RX.findall(line) if not is_css else []
            if p.suffix in (".tsx", ".jsx", ".vue", ".svelte", ".astro", ".html", ".mdx") and EMOJI_RX.search(line):
                emoji += len(EMOJI_RX.findall(line))
        if emoji:
            gen.append(
                f"{rel}: {emoji} emoji in UI code: emoji render differently per platform; use an icon set with text labels"
            )
    limit = int(cfg.get("stock_palette_max", 25))
    if len(stock) > limit:
        top = sorted(set(stock), key=lambda x: -stock.count(x))[:3]
        gen.append(
            f"{len(stock)} stock Tailwind palette classes (e.g. {', '.join(top)}): map roles to semantic tokens in @theme"
        )
    named = [f for _, f in fams if f != "(local font)"]
    if fams and named and len(named) == len(fams) and all(f.lower() in DEFAULT_FONTS for f in named):
        uniq = sorted({f for f in named}, key=str.lower)
        gen.append(
            f"only default/AI-typical font families ({', '.join(uniq[:4])}): choose a typeface with character for display text (check its licence and French/Latin Extended coverage)"
        )
    elif only is None and css_seen and not fams:
        gen.append("no font family declared anywhere: the UI falls back to the browser/Tailwind system stack")
    if motion_at and not reduced:
        gen.append(
            f"{motion_at}: animation without any prefers-reduced-motion handling (CSS media query, motion-reduce:, useReducedMotion)"
        )
    return raw, gen


def design_problems(root: Path, cfg: dict | None = None, only: list[str] | None = None) -> dict:
    """Everything `eos design check` reports: errors fail the gate; warnings are advice unless the config
    raises raw_colors/generic to "error"."""
    cfg = cfg or design_cfg(root)
    errs: list[str] = []
    warns: list[str] = []
    notes: list[str] = []
    files = design_token_files(root, cfg)
    docs: list[tuple[str, object]] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            docs.append((rel, json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as exc:
            errs.append(f"{rel}: not valid JSON ({exc})")
    resolved, e, w = dtcg_problems(docs)
    errs += e
    warns += w
    ce, cn, checked = design_contrast(root, cfg, resolved)
    errs += ce
    notes += cn
    raw, gen = ([], []) if (cfg["raw_colors"] == "off" and cfg["generic"] == "off") else design_lint(root, cfg, only)
    for level, items in ((cfg["raw_colors"], raw), (cfg["generic"], gen)):
        if level == "error":
            errs += items
        elif level != "off":
            warns += items
    n_tokens = sum(len(t) for t in resolved.values())
    return {
        "errors": errs, "warnings": warns, "notes": notes, "token_files": len(files), "tokens": n_tokens,
        "pairs": checked, "css": len(design_css_files(root, cfg)),
    }  # fmt: skip


def has_design_files(root: Path, cfg: dict | None = None) -> bool:
    cfg = cfg or design_cfg(root)
    return "design" in _load_cfg(root) or bool(design_token_files(root, cfg)) or bool(design_css_files(root, cfg))


def cmd_design(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    if args.action == "ab":
        return cmd_design_ab(args)
    if args.action == "contrast":
        if len(args.colors) != 2:
            eprint('usage: eos design contrast "<foreground>" "<background>"   (hex, rgb(), hsl(), oklch() …)')
            return 2
        fg, bg = parse_css_color(args.colors[0]), parse_css_color(args.colors[1])
        if not fg or not bg:
            eprint("could not parse a colour (hex, rgb(), hsl(), hwb(), oklch(), oklab(), lab(), lch(), color())")
            return 2
        r = contrast_ratio(fg, bg)
        shown = math.floor(r * 100) / 100
        verdict = ", ".join(f"{name} {'pass' if r >= need else 'FAIL'}" for name, need in (
            ("text 4.5:1", 4.5), ("large text / UI 3:1", 3.0), ("AAA text 7:1", 7.0)))  # fmt: skip
        print(f"{shown:.2f}:1 ({_clip_hex(fg[0])} on {_clip_hex(bg[0])}): {verdict}")
        print("  WCAG 2 ratio. APCA (advisory, not a standard) needs a separate tool.")
        return 0 if r >= 4.5 else 1
    cfg = design_cfg(root)
    res = design_problems(root, cfg)
    if args.json:
        print(json.dumps(res, indent=1))
        return 1 if res["errors"] or (args.strict and res["warnings"]) else 0
    for n in res["notes"]:
        print("  note: " + n)
    for w in res["warnings"]:
        print("  warn: " + w)
    for e in res["errors"]:
        print("  error: " + e)
    failed = bool(res["errors"]) or (args.strict and bool(res["warnings"]))
    print(
        f"eos design check: {'FAILED' if failed else 'OK'} ({res['token_files']} token files, {res['tokens']} tokens, "
        f"{res['css']} theme CSS files, {res['pairs']} contrast pairs; {len(res['errors'])} errors, "
        f"{len(res['warnings'])} warnings)"
    )
    if not res["token_files"] and not res["css"]:
        print("  no design tokens found: `eos scaffold design-tokens` starts a DTCG token set")
    return 1 if failed else 0


def design_extras(root: Path, m: dict, c: dict, full: bool) -> tuple[list[tuple[str, int, str, float]], list[str]]:
    """What `eos verify` adds for design: standard+ when UI, CSS or token files changed. Token schema and
    contrast run over all token/theme files (fast, in-process); the generic-look lint scans only the changed
    files (all files on risky or --full). Lint findings are notes unless the config makes them errors."""
    if (c["lane"] == "spike" or c["risk"] == "trivial") and not full:
        return [], []
    changed = [f for f in c["files"] if f.endswith(UI_EXT) or f.endswith((".tokens.json", ".tokens"))]
    if not changed and not full:
        return [], []
    cfg = design_cfg(root)
    t0 = time.time()
    wide = full or c["risk"] in ("risky", "one-way-door")
    res = design_problems(root, cfg, None if wide else changed)
    if not (res["token_files"] or res["css"] or res["errors"] or res["warnings"]):
        return [], []
    label = f"design (tokens, contrast{', lint' if cfg['generic'] != 'off' else ''})"
    notes = [f"design: {w}" for w in res["warnings"][:8]]
    if len(res["warnings"]) > 8:
        notes.append(f"design: …{len(res['warnings']) - 8} more (`eos design check`)")
    return [(label, 1 if res["errors"] else 0, "\n".join(res["errors"]), time.time() - t0)], notes


# ----------------------------------------------------------------------------- design A/B (studio evaluation)
AB_SPECS_DIR = "core/templates/design/ab"
AB_GATE_ROWS = (5, 7, 9, 10)
AB_RULE = (
    "Keep the studio only if ALL hold: (1) arm B's mean critique total is at least 2 points (of 24) above arm A's; "
    "(2) B scores higher on at least 2 of the 3 screens; (3) B has no 0 on gate rows 5, 7, 9 or 10 where A scored "
    "above 0 on the same screen; (4) B's total `eos design check` errors are not higher than A's. Otherwise drop it "
    "(`eos studio off`; do not sign off the sources). Ties and small wins are a drop: the studio must earn its place."
)
AB_LEAK_RX = _lazy_rx(r"impeccable|ui-ux-pro-max|uupm|\.eos/studio|design studio|review-animations", re.IGNORECASE)
AB_DESIGN_PACKS = ("phases/design-direction.md", "phases/ux-design.md", "phases/frontend.md")


def ab_specs(home: Path) -> list[Path]:
    return sorted(p for p in (home / AB_SPECS_DIR).glob("[0-9]*.md"))


def _ab_eos(home: Path) -> str:
    return f"python3 {home / 'bin/eos.py'}"


def ab_init(home: Path, ws: Path, allow_pending: bool = False) -> tuple[int, list[str]]:
    """Two identical arms; arm-b also gets the studio. Both get our design packs and refs."""
    if ws.exists() and any(ws.iterdir()):
        return 2, [f"{ws} exists and is not empty"]
    specs = ab_specs(home)
    prompt = read(home / AB_SPECS_DIR / "PROMPT.md").replace("{{EOS}}", _ab_eos(home))
    contexts = {
        "arm-a": "Use the design guidance in `.eos/packs/` (start with `phases/design-direction.md`; its deep "
        "references are in `.eos/packs/ref/design/`).",
        "arm-b": "Use the design guidance in `.eos/packs/` (start with `phases/design-direction.md`; its deep "
        "references are in `.eos/packs/ref/design/`). An opt-in design studio is also available: read "
        f"`.eos/studio/README.md` and use it as it describes (`{_ab_eos(home)} studio find|palette|run "
        "--dir .`). Follow the precedence rule in that README.",
    }
    for arm, ctx in contexts.items():
        d = ws / arm
        for s in specs:
            write(d / "specs" / s.name, read(s))
        for rel in AB_DESIGN_PACKS:
            write(d / ".eos/packs" / rel, read(home / "packs" / rel))
        for p in sorted((home / "packs/ref/design").glob("*.md")):
            write(d / ".eos/packs/ref/design" / p.name, read(p))
        write(d / "PROMPT.md", prompt.replace("{{CONTEXT}}", ctx))
        (d / "screens").mkdir(parents=True, exist_ok=True)
    rc, msgs = studio_install(home, ws / "arm-b", allow_pending=allow_pending)
    if rc:
        shutil.rmtree(ws)
        return rc, [
            *msgs,
            "(an evaluation workspace may use pending sources only with --allow-pending, a human decision)",
        ]
    meta = {"created": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "allow_pending": allow_pending,
            "specs": [s.stem for s in specs], "rule": AB_RULE}  # fmt: skip
    write(ws / "ab.json", json.dumps(meta, indent=1) + "\n")
    write(ws / "README.md", read(home / AB_SPECS_DIR / "README.md").replace("{{EOS}}", _ab_eos(home)))
    return 0, msgs


def _ab_check(d: Path) -> dict:
    if not d.is_dir():
        return {"missing": True}
    res = design_problems(d)
    return {"errors": len(res["errors"]), "warnings": len(res["warnings"]), "pairs": res["pairs"],
            "tokens": res["tokens"], "error_list": res["errors"][:20]}  # fmt: skip


def ab_score(home: Path, ws: Path, seed: str | None = None, shoot: bool = False) -> tuple[int, list[str]]:
    """Automatic metrics per arm and screen, then blinded copies (X/Y per screen, random) with critique sheets."""
    import random

    meta = json.loads(read(ws / "ab.json"))
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    sc = ws / "scoring"
    if sc.exists():
        shutil.rmtree(sc)
    msgs: list[str] = []
    auto: dict = {"arm-a": {}, "arm-b": {}}
    key: dict = {}
    sheet = read(home / "core/templates/design/critique.md")
    shots: list[str] = ["#!/bin/sh", "# Screenshots for blinded scoring (needs Node + Playwright browsers).", "set -e",
                        'cd "$(dirname "$0")"']  # fmt: skip
    for spec in meta["specs"]:
        flip = rng.random() < 0.5
        key[spec] = {"X": "arm-b" if flip else "arm-a", "Y": "arm-a" if flip else "arm-b"}
        for label, arm in key[spec].items():
            src = ws / arm / "screens" / spec
            auto[arm][spec] = _ab_check(src)
            dst = sc / spec / label
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".eos", "node_modules"))
                for p in dst.rglob("*"):
                    if p.is_file() and p.suffix in (".md", ".html", ".css", ".json") and AB_LEAK_RX.search(read(p)):
                        msgs.append(
                            f"blinding leak: {p.relative_to(sc).as_posix()} names the studio; hide that text before scoring"
                        )
            else:
                msgs.append(f"missing: {arm}/screens/{spec}")
            write(sc / spec / f"{label}-critique.md", sheet.replace("<screen>", f"{spec} / {label}"))
            for w, h, scheme in ((360, 800, "light"), (360, 800, "dark"), (1280, 900, "light"), (320, 700, "light")):
                shots.append(
                    f"npx --yes playwright screenshot --full-page --viewport-size={w},{h} --color-scheme={scheme} "
                    f'"file://$PWD/{spec}/{label}/src/index.html" "{spec}/{label}-{w}-{scheme}.png"'
                )
    write(sc / "shoot.sh", "\n".join(shots) + "\n", mode=0o755)
    write(ws / ".ab-key.json", json.dumps(key, indent=1) + "\n")
    write(ws / "auto.json", json.dumps(auto, indent=1) + "\n")
    if (ws / "arm-b" / STUDIO_DIR).is_dir() and studio_backend() != "none":
        # secondary signal: impeccable's own detector (may favour arm B, which read its rules)
        rc, _ = studio_install(home, sc, allow_pending=meta.get("allow_pending", False))
        if not rc:
            for spec in meta["specs"]:
                for label in ("X", "Y"):
                    if (sc / spec / label).is_dir():
                        r, out = studio_run(sc, "impeccable", ["detect", "--json", f"{spec}/{label}"])
                        try:
                            n = len(json.loads(out)) if r in (0, 2) else None
                        except ValueError:
                            n = None
                        auto[key[spec][label]][spec]["impeccable_findings"] = n
            write(ws / "auto.json", json.dumps(auto, indent=1) + "\n")
            shutil.rmtree(sc / STUDIO_DIR, ignore_errors=True)
            shutil.rmtree(sc / ".eos", ignore_errors=True)
    if shoot:
        if shutil.which("npx"):
            rc, out = run(["sh", str(sc / "shoot.sh")], timeout=900)
            msgs.append("screenshots taken" if rc == 0 else "screenshots failed:\n" + out[-800:])
        else:
            msgs.append("npx not found: run scoring/shoot.sh on a machine with Node")
    msgs.append(
        f"blinded copies and critique sheets in {sc}; the arm key is in {ws / '.ab-key.json'} (scorer: do not open)"
    )
    return 0, msgs


def _ab_sheet_scores(p: Path) -> dict[int, int] | None:
    rows: dict[int, int] = {}
    for line in read(p).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].isdigit() and 1 <= int(cells[0]) <= 12:
            if cells[2] not in ("0", "1", "2"):
                return None
            rows[int(cells[0])] = int(cells[2])
    return rows if len(rows) == 12 else None


def ab_report(ws: Path) -> tuple[int, str]:
    meta = json.loads(read(ws / "ab.json"))
    key = json.loads(read(ws / ".ab-key.json"))
    auto = json.loads(read(ws / "auto.json")) if (ws / "auto.json").exists() else {}
    scores: dict[str, dict[str, dict[int, int]]] = {"arm-a": {}, "arm-b": {}}
    missing: list[str] = []
    for spec in meta["specs"]:
        for label, arm in key[spec].items():
            s = _ab_sheet_scores(ws / "scoring" / spec / f"{label}-critique.md")
            if s is None:
                missing.append(f"scoring/{spec}/{label}-critique.md")
            else:
                scores[arm][spec] = s
    if missing:
        return 2, "critique sheets not fully scored (every row needs 0, 1 or 2):\n  " + "\n  ".join(missing)
    tot = {arm: {spec: sum(r.values()) for spec, r in v.items()} for arm, v in scores.items()}
    mean = {arm: sum(t.values()) / len(t) for arm, t in tot.items()}
    wins = sum(1 for spec in meta["specs"] if tot["arm-b"][spec] > tot["arm-a"][spec])
    gate_reg = [f"{spec} row {r}" for spec in meta["specs"] for r in AB_GATE_ROWS
                if scores["arm-b"][spec][r] == 0 and scores["arm-a"][spec][r] > 0]  # fmt: skip
    errs = {arm: sum(int(v.get("errors", 0) or 0) for v in auto.get(arm, {}).values()) for arm in ("arm-a", "arm-b")}
    checks = [
        (f"mean total B {mean['arm-b']:.1f} >= A {mean['arm-a']:.1f} + 2", mean["arm-b"] >= mean["arm-a"] + 2),
        (f"B wins {wins} of {len(meta['specs'])} screens (need >= 2)", wins >= 2),
        ("no new 0 on gate rows 5/7/9/10" + (f" ({', '.join(gate_reg)})" if gate_reg else ""), not gate_reg),
        (f"`eos design check` errors B {errs['arm-b']} <= A {errs['arm-a']}", errs["arm-b"] <= errs["arm-a"]),
    ]
    keep = all(ok for _, ok in checks)
    lines = ["# Design studio A/B report", "", (f"Workspace created {meta['created']}; scored "
             f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')}."), "", "| Screen | A (baseline) | B (studio) |", "|---|---|---|"]  # fmt: skip
    for spec in meta["specs"]:
        lines.append(f"| {spec} | {tot['arm-a'][spec]} / 24 | {tot['arm-b'][spec]} / 24 |")
    lines += ["", "## Decision rule", AB_RULE, ""]
    lines += [f"- [{'x' if ok else ' '}] {txt}" for txt, ok in checks]
    lines += ["", f"**Decision: {'KEEP the studio' if keep else 'DROP the studio (eos studio off)'}**", ""]
    imp = {arm: [v.get("impeccable_findings") for v in auto.get(arm, {}).values()] for arm in ("arm-a", "arm-b")}
    if any(x is not None for v in imp.values() for x in v):
        lines += [("Secondary (not in the rule; favours B, which read its rules): impeccable detect findings "
                  f"A {imp['arm-a']} vs B {imp['arm-b']}."), ""]  # fmt: skip
    text = "\n".join(lines)
    write(ws / "REPORT.md", text + "\n")
    return (0 if keep else 1), text


def cmd_design_ab(args: argparse.Namespace) -> int:
    home = find_eos_home()
    sub = args.colors[0] if args.colors else ""
    ws = Path(args.colors[1] if len(args.colors) > 1 else "design-ab").resolve()
    if sub == "init":
        rc, msgs = ab_init(home, ws, allow_pending=args.allow_pending)
        for m in msgs:
            print(("  " if rc == 0 else "") + m)
        if rc == 0:
            print(f"A/B workspace ready: {ws}\n  next: run one fresh agent session in arm-a and one in arm-b with "
                  "their PROMPT.md, same model and settings; then `eos design ab score`")  # fmt: skip
        return rc
    if sub == "score":
        if not (ws / "ab.json").exists():
            eprint(f"not an A/B workspace: {ws} (eos design ab init)")
            return 2
        rc, msgs = ab_score(home, ws, seed=args.seed, shoot=args.shoot)
        for m in msgs:
            print("  " + m)
        return rc
    if sub == "report":
        if not (ws / ".ab-key.json").exists():
            eprint("score first: eos design ab score")
            return 2
        rc, text = ab_report(ws)
        print(text)
        return 0 if rc in (0, 1) else rc
    eprint("usage: eos design ab init|score|report [<workspace>] [--allow-pending] [--shoot] [--seed S]")
    return 2


# ----------------------------------------------------------------------------- design studio (opt-in)
STUDIO_DIR = ".eos/studio"
STUDIO_BACKENDS = ("docker", "podman", "bwrap", "none")
STUDIO_DETECT_FLAGS = {
    "--help",
    "--json",
    "--quiet",
    "--no-config",
    "--no-advisory",
    "--no-design-system",
    "--no-inline-ignores",
}


def studio_lock(home: Path) -> dict:
    return json.loads(read(home / "core/studio/studio.json"))


def studio_cache_dir() -> Path:
    env = os.environ.get("EOS_STUDIO_CACHE")
    return Path(env) if env else Path.home() / ".cache/engineering-os/studio"


def host_platform() -> str | None:
    osn = {"Linux": "linux", "Darwin": "darwin"}.get(platform.system())
    arch = {"x86_64": "x64", "amd64": "x64", "AMD64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine()
    )
    return f"{osn}-{arch}" if osn and arch else None


def studio_backend() -> str:
    """Sandbox to run third-party code in: Docker or Podman (no network, read-only), bubblewrap on Linux, or none
    (knowledge-only). EOS_STUDIO_SANDBOX forces one."""
    want = os.environ.get("EOS_STUDIO_SANDBOX", "").strip().lower()
    if want:
        return want if want in STUDIO_BACKENDS else "none"
    for eng in ("docker", "podman"):
        if shutil.which(eng) and run([eng, "info"], timeout=20)[0] == 0:
            return eng
    if platform.system() == "Linux" and shutil.which("bwrap"):
        rc, _ = run(["bwrap", "--ro-bind", "/", "/", "--unshare-all", "--die-with-parent", "true"], timeout=20)
        if rc == 0:
            return "bwrap"
    return "none"


def studio_sandbox_platform(backend: str) -> str | None:
    """The binary platform the sandbox needs: containers run Linux on the engine's architecture."""
    if backend in ("docker", "podman"):
        rc, out = run([backend, "info", "--format", "{{.Architecture}}"], timeout=20)
        arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(out.strip())
        return f"linux-{arch}" if rc == 0 and arch else None
    if backend == "bwrap":
        return host_platform()
    return None


def studio_binary(tool: dict, plat: str) -> Path:
    return studio_cache_dir() / "impeccable" / tool["version"] / plat / "impeccable"


def _file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def studio_fetch_binary(tool: dict, plat: str) -> tuple[bool, str]:
    """Download the engine for `plat`, then require BOTH our pinned sha256 (reviewed) and the upstream sidecar to
    match. Anything else is deleted. Never on PATH; executable only inside the sandbox."""
    import urllib.request

    asset = tool["assets"].get(plat)
    if not asset:
        return False, f"no pinned impeccable asset for {plat}"
    dest = studio_binary(tool, plat)
    if dest.exists() and _file_sha256(dest) == asset["sha256"]:
        return True, f"{dest} (already verified)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{tool['release']}/{asset['name']}"
    part = dest.with_name(".impeccable.part")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, part.open("wb") as f:
            shutil.copyfileobj(r, f)
        with urllib.request.urlopen(url + ".sha256", timeout=60) as r:
            sidecar = r.read().decode().split()[0].strip().lower()
    except OSError as exc:
        part.unlink(missing_ok=True)
        return False, f"download failed ({exc}); knowledge-only mode still works"
    got = _file_sha256(part)
    if got != asset["sha256"] or sidecar != asset["sha256"]:
        part.unlink(missing_ok=True)
        return False, (
            f"checksum mismatch for {asset['name']}: pinned {asset['sha256'][:12]}, sidecar {sidecar[:12]}, "
            f"downloaded {got[:12]}; refusing it (re-review upstream before changing core/studio/studio.json)"
        )
    os.chmod(part, 0o555)
    os.replace(part, dest)
    return True, f"{dest} (sha256 {got[:12]}… matches pinned and upstream sidecar)"


def studio_sources(lock: dict) -> list[tuple[str, str]]:
    """(vendor id, kind) for everything `eos studio on` copies."""
    out = [(sid, "knowledge") for sid in lock["knowledge"]]
    out += [(t["code"], "code") for t in lock["tools"].values() if t.get("code")]
    return out


def studio_install(home: Path, root: Path, allow_pending: bool = False) -> tuple[int, list[str]]:
    """Copy studio sources into <root>/.eos/studio/. Pending sources are refused unless allow_pending (used only by
    `eos design ab init --allow-pending`, an evaluation workspace a human asked for)."""
    lock = studio_lock(home)
    vlock = _vendor_lock(home)["sources"]
    msgs: list[str] = []
    missing = [sid for sid, _ in studio_sources(lock) if sid not in vlock]
    if missing:
        return 2, [f"not vendored: {', '.join(missing)}"]
    pending = [sid for sid, _ in studio_sources(lock) if vendor_pending(vlock[sid])]
    if pending and not allow_pending:
        return 1, [
            (
                f"pending human sign-off: {', '.join(pending)}. A human reviews packs/vendor/<id>/ and runs "
                "`eos vendor review <id> --by <name> --note ...`; until then the studio stays off (quarantine)."
            )
        ]
    dest = root / STUDIO_DIR
    if dest.exists():
        shutil.rmtree(dest)
    for sid, kind in studio_sources(lock):
        sub = "vendor" if kind == "knowledge" else "code"
        for rel in vlock[sid]["files"]:
            src = home / "packs/vendor" / sid / rel
            out = dest / sub / sid / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
    write(dest / "README.md", read(home / "core/templates/design/studio.md"))
    write(dest / "studio.json", read(home / "core/studio/studio.json"))
    write(dest / "out/.gitignore", "*\n")
    if pending:
        write(
            dest / "PENDING-SIGN-OFF.txt",
            "Evaluation copy: these sources are not signed off yet: " + ", ".join(pending) + "\n",
        )
        msgs.append("evaluation copy with sources pending sign-off: " + ", ".join(pending))
    return 0, msgs


def studio_paths(root: Path) -> dict:
    d = root / STUDIO_DIR
    lock = json.loads(read(d / "studio.json"))
    imp, uu = lock["tools"]["impeccable"], lock["tools"]["uupm"]
    return {
        "lock": lock,
        "out": d / "out",
        "skill": d / "vendor" / imp["knowledge"] / imp["skill_dir"],
        "uupm_scripts": d / "code" / uu["code"] / uu["scripts"],
        "uupm_data": d / "vendor" / uu["knowledge"] / uu["data"],
    }


def studio_sandbox_cmd(backend: str, image: str, mounts: list[tuple[Path, str, bool]], env: dict[str, str],
                       argv: list[str]) -> list[str]:  # fmt: skip
    """No network, no secrets (empty environment), project read-only, writes only to the scratch mount."""
    env = {"HOME": "/out", "PATH": "/usr/local/bin:/usr/bin:/bin", **env}
    if backend in ("docker", "podman"):
        cmd = [backend, "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "1g",
               "--tmpfs", "/tmp:rw,size=64m", "-w", "/out"]  # fmt: skip
        if hasattr(os, "getuid"):
            cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        for src, dst, rw in mounts:
            cmd += ["-v", f"{Path(src).as_posix()}:{dst}:{'rw' if rw else 'ro'}"]  # Docker Desktop takes C:/x
        return [*cmd, image, *argv]
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]  # fmt: skip
    for sysdir in ("/usr", "/lib", "/lib64", "/bin"):
        cmd += ["--ro-bind-try", sysdir, sysdir]
    for src, dst, rw in mounts:
        cmd += ["--bind" if rw else "--ro-bind", Path(src).as_posix(), dst]  # bwrap is Linux-only: POSIX paths
    for k, v in env.items():
        cmd += ["--setenv", k, v]
    return [*cmd, "--chdir", "/out", *argv]


def _studio_project_path(root: Path, arg: str) -> str | None:
    p = (root / arg).resolve()
    try:
        rel = p.relative_to(root.resolve())
    except ValueError:
        return None
    return "/project/" + rel.as_posix() if str(rel) != "." else "/project"


def studio_build_run(root: Path, backend: str, tool: str, args: list[str]) -> tuple[list[str] | None, str]:
    """The sandboxed command for an allowed verb, or (None, why)."""
    sp = studio_paths(root)
    lock = sp["lock"]
    if tool not in lock["tools"]:
        return None, f"unknown tool {tool!r} (impeccable, uupm)"
    t = lock["tools"][tool]
    if not args or args[0] not in t["verbs"]:
        return None, f"{tool}: allowed verbs are {', '.join(t['verbs'])}"
    mounts: list[tuple[Path, str, bool]] = [(root.resolve(), "/project", False), (sp["out"].resolve(), "/out", True)]
    if tool == "impeccable":
        plat = studio_sandbox_platform(backend)
        binp = studio_binary(t, plat) if plat else None
        if not binp or not binp.exists():
            return None, f"engine for {plat or 'this sandbox'} not fetched: run `eos studio fetch`"
        if _file_sha256(binp) != t["assets"][plat]["sha256"]:
            return None, f"{binp} does not match the pinned sha256; delete it and run `eos studio fetch`"
        argv = ["/opt/impeccable", args[0]]
        it = iter(args[1:])
        for a in it:
            if a.startswith(("http://", "https://")):
                return None, "URL scans need a browser and network; scan files instead"
            if a == "--scope":
                argv += [a, next(it, "")]
            elif a.startswith("-"):
                if a not in STUDIO_DETECT_FLAGS:
                    return None, f"flag {a} is not allowed in the studio sandbox"
                argv.append(a)
            else:
                mapped = _studio_project_path(root, a)
                if not mapped:
                    return None, f"{a} is outside the project"
                argv.append(mapped)
        mounts += [(binp, "/opt/impeccable", False), (sp["skill"].resolve(), "/skill", False)]
        env = {**t["env"], "IMPECCABLE_SKILL_DIR": "/skill"}
    else:
        rest = list(args[1:])
        if any(a in ("--output-dir", "-o") or a.startswith("--output-dir=") for a in rest):
            return None, "--output-dir is fixed to the scratch folder (.eos/studio/out)"
        if "--persist" in rest:
            rest += ["--output-dir", "/out"]
        argv = ["python3", "/uupm/scripts/search.py", *rest]
        mounts += [
            (sp["uupm_scripts"].resolve(), "/uupm/scripts", False),
            (sp["uupm_data"].resolve(), "/uupm/data", False),
        ]
        env = dict(t["env"])
    return studio_sandbox_cmd(backend, lock["image"], mounts, env, argv), ""


def studio_run(root: Path, tool: str, args: list[str], backend: str | None = None) -> tuple[int, str]:
    backend = backend or studio_backend()
    if backend == "none":
        return 3, (
            "no sandbox available (Docker, Podman or bubblewrap): third-party code does not run outside one.\n"
            'Knowledge-only mode: `eos studio find "<query>"` and read .eos/studio/README.md.'
        )
    cmd, why = studio_build_run(root, backend, tool, args)
    if cmd is None:
        return 2, why
    out_dir = root / STUDIO_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    rc, out = run(cmd, timeout=300, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    write(out_dir / f"{stamp}-{tool}-{args[0].lstrip('-')}.txt", out)
    return rc, out


def _studio_terms(q: str) -> list[str]:
    return [w[:6] for w in re.findall(r"[a-zà-ÿ0-9]+", q.lower()) if len(w) >= 3]


def studio_find(root: Path, query: str, n: int = 8, source: str | None = None) -> list[tuple[int, str, str]]:
    """eos's own read-only search over the studio text and CSV catalogs (no third-party code): rows and
    paragraphs ranked by how many query terms they contain."""
    terms = _studio_terms(query)
    hits: list[tuple[int, str, str]] = []
    base = root / STUDIO_DIR / "vendor"
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".csv"):
            continue
        rel = p.relative_to(root / STUDIO_DIR).as_posix()
        if source and f"vendor/{source}/" not in rel + "/":
            continue
        text = read(p)
        if p.suffix == ".csv":
            rows = list(csv.reader(io.StringIO(text)))
            head = rows[0] if rows else []
            units = [(i + 1, " | ".join(f"{h}: {c}" for h, c in zip(head, r) if c)) for i, r in enumerate(rows[1:], 1)]
        else:
            units, buf, start = [], [], 1
            for i, ln in enumerate(text.splitlines() + [""], 1):
                if ln.strip():
                    buf.append(ln)
                    continue
                if buf:
                    units.append((start, " ".join(buf)))
                buf, start = [], i + 1
        for line, unit in units:
            low = unit.lower()
            score = sum(1 for t in set(terms) if t in low)
            if score:
                hits.append((score * 100 - min(len(unit), 2000) // 100, f"{rel}:{line}", unit))
    hits.sort(key=lambda h: -h[0])
    return hits[:n]


def studio_palette_tokens(ds: dict) -> dict:
    """ui-ux-pro-max design-system colours as a DTCG 2025.10 draft (role names kebab-cased: on_primary ->
    on-primary, card_foreground -> card-foreground) so eos's schema and contrast checks apply."""
    group: dict[str, object] = {"$type": "color"}
    for role, hexv in (ds.get("colors") or {}).items():
        if not isinstance(hexv, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", hexv.strip()):
            continue
        h = hexv.strip().lower()
        comps = [round(int(h[i : i + 2], 16) / 255, 4) for i in (1, 3, 5)]
        group[role.replace("_", "-")] = {"$value": {"colorSpace": "srgb", "components": comps, "hex": h}}
    return {"color": group}


def studio_palette_review(tokens_doc: dict, ds: dict) -> tuple[list[str], list[str]]:
    """Contrast and schema via design_problems on a temp copy, plus the generic-look hints our refs care about."""
    with tempfile.TemporaryDirectory() as td:
        write(Path(td) / "design/tokens/draft.tokens.json", json.dumps(tokens_doc))
        res = design_problems(Path(td), {**DESIGN_DEFAULTS, "raw_colors": "off", "generic": "off"})
    errs, warns = res["errors"], list(res["warnings"])
    for role, tok in tokens_doc["color"].items():
        if role.startswith("$"):
            continue
        lin = color_to_linear_srgb("srgb", tok["$value"]["components"])
        if is_violet(lin):
            lab = _oklch_of(lin)
            warns.append(
                f"color.{role} {tok['$value']['hex']} is violet/purple (hue {lab[2]:.0f}): a generic AI tell in our refs"
            )
    fonts = " ".join(str(v) for v in (ds.get("typography") or {}).values() if isinstance(v, str))
    used = [f for f in DEFAULT_FONTS if re.search(rf"\b{re.escape(f)}\b", fonts, re.IGNORECASE)]
    if used:
        warns.append(f"suggested fonts include default/AI-typical families ({', '.join(used)}): choose on purpose")
    return errs, warns


def _oklch_of(lin: list[float]) -> tuple[float, float, float]:
    r, g, b = lin
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _pop_opt(rest: list[str], names: tuple[str, ...], default: str | None = None) -> str | None:
    for i, a in enumerate(rest):
        for n in names:
            if a == n and i + 1 < len(rest):
                val = rest[i + 1]
                del rest[i : i + 2]
                return val
            if a.startswith(n + "="):
                del rest[i]
                return a.split("=", 1)[1]
    return default


def cmd_studio(args: argparse.Namespace) -> int:
    if args.action == "run" and args.rest[:1] == ["--dir"] and len(args.rest) > 1:  # only before the tool name
        args.dir = args.rest[1]
        args.rest = args.rest[2:]
    if args.action != "run":  # run passes its flags to the tool; the others take eos options anywhere
        args.dir = _pop_opt(args.rest, ("--dir",), args.dir)
        args.source = _pop_opt(args.rest, ("--source",))
        args.n = int(_pop_opt(args.rest, ("-n",), "8") or 8)
        args.name = _pop_opt(args.rest, ("--name", "-p"))
    root = Path(args.dir).resolve()
    home = find_eos_home()
    on = (root / STUDIO_DIR / "studio.json").exists()
    act = args.action
    if act == "status":
        backend = studio_backend()
        print(f"design studio: {'ON' if on else 'off'} ({root / STUDIO_DIR if on else 'eos studio on to enable'})")
        print(f"  sandbox: {backend}{'  (knowledge-only mode: code will not run)' if backend == 'none' else ''}")
        if home:
            lock, vl = studio_lock(home), _vendor_lock(home)["sources"]
            for sid, kind in studio_sources(lock):
                s = vl.get(sid)
                st = (
                    "not vendored"
                    if not s
                    else ("pending sign-off" if vendor_pending(s) else f"signed off by {s['reviewed_by']}")
                )
                print(f"  {sid:<28} {kind:<9} {st}")
            t = lock["tools"]["impeccable"]
            plat = studio_sandbox_platform(backend) or host_platform()
            binp = studio_binary(t, plat) if plat else None
            ok = bool(
                binp and binp.exists() and plat in t["assets"] and _file_sha256(binp) == t["assets"][plat]["sha256"]
            )
            print(
                f"  impeccable engine {t['version']} ({plat}): {'fetched, sha256 verified' if ok else 'not fetched (eos studio fetch)'}"
            )
        print("  always-on cost: none (no skill, rule or AGENTS.md change; read .eos/studio/README.md on demand)")
        return 0
    if act == "on":
        if not home:
            eprint("needs the engineering-os repo (set EOS_HOME)")
            return 2
        rc, msgs = studio_install(home, root)
        for m in msgs:
            (eprint if rc else print)(("  " if not rc else "") + m)
        if rc:
            return rc
        print(f"design studio ON: {STUDIO_DIR}/README.md (precedence, sources, commands). Zero always-on tokens.")
        print(f"  sandbox: {studio_backend()}; `eos studio fetch` gets the pinned impeccable engine (optional)")
        return 0
    if act == "off":
        if on:
            shutil.rmtree(root / STUDIO_DIR)
        print("design studio off (removed .eos/studio; vendored sources stay in engineering-os)")
        return 0
    if act == "fetch":
        if not home:
            eprint("needs the engineering-os repo (set EOS_HOME)")
            return 2
        lock = studio_lock(home)
        t = lock["tools"]["impeccable"]
        backend = studio_backend()
        plats = {p for p in (studio_sandbox_platform(backend), host_platform() if backend == "bwrap" else None) if p}
        if not plats:
            print("no sandbox here, so the engine would never run: skipped (knowledge-only mode)")
            return 0
        rc = 0
        for plat in sorted(plats):
            ok, msg = studio_fetch_binary(t, plat)
            print(("  ok   " if ok else "  FAIL ") + msg)
            rc |= 0 if ok else 1
        if backend in ("docker", "podman"):
            prc, out = run([backend, "pull", lock["image"]], timeout=600)
            print(
                ("  ok   " if prc == 0 else "  FAIL ")
                + f"image {lock['image']}"
                + ("" if prc == 0 else f": {out[-300:]}")
            )
            rc |= 0 if prc == 0 else 1
        return rc
    if not on:
        eprint("design studio is off here: `eos studio on` (after human sign-off of the studio sources)")
        return 2
    if act == "find":
        q = " ".join(args.rest)
        if not q:
            eprint('usage: eos studio find "<query>" [--source <vendor id>] [-n 8]')
            return 2
        hits = studio_find(root, q, args.n, args.source)
        for _, where, unit in hits:
            print(f"{where}\n    {unit[:240]}")
        if not hits:
            print("no matches")
        return 0
    if act == "run":
        if len(args.rest) < 2:
            eprint(
                'usage: eos studio run impeccable detect <paths> | eos studio run uupm search "<query>" [--domain …]'
            )
            return 2
        rc, out = studio_run(root, args.rest[0], args.rest[1:])
        print(out.rstrip())
        return rc
    if act == "palette":
        q = " ".join(args.rest)
        if not q:
            eprint('usage: eos studio palette "<product words>"')
            return 2
        rc, out = studio_run(root, "uupm", ["search", q, "--design-system", "--json", "-p", args.name or "Draft"])
        if rc != 0:
            print(out.rstrip())
            return rc
        try:
            ds = json.loads(out[out.index("{") :])["design_system"]
        except (ValueError, KeyError):
            eprint("could not read the design-system JSON; raw output is in .eos/studio/out/")
            return 1
        doc = studio_palette_tokens(ds)
        slug = _slug(q)[:40] or "draft"
        dest = root / STUDIO_DIR / "out" / f"{slug}.tokens.json"
        write(dest, json.dumps(doc, indent=1) + "\n")
        errs, warns = studio_palette_review(doc, ds)
        print(f"draft tokens: {dest.relative_to(root).as_posix()} ({len(doc['color']) - 1} colours; style: "
              f"{(ds.get('style') or {}).get('name', '?')}; type: {(ds.get('typography') or {}).get('heading', '?')})")  # fmt: skip
        for e in errs:
            print("  error: " + e)
        for w in warns:
            print("  warn: " + w)
        print(
            "  next: adapt the roles you agree with into design/tokens/*.tokens.json (OKLCH ramps), then `eos design check`."
        )
        return 0
    return 2


# ----------------------------------------------------------------------------- bootstrap (machine setup)
def global_state_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".config/engineering-os/state.json"


def load_global_state(home: Path | None = None) -> dict:
    try:
        return json.loads(read(global_state_path(home)))
    except (OSError, ValueError):
        return {}


def profile_file(home: Path) -> Path:
    """personal/PROFILE.user.md (git-ignored, your own preferences) wins over the committed generic template."""
    user = home / "personal/PROFILE.user.md"
    return user if user.exists() else home / "personal/PROFILE.md"


def upsert_block(path: Path, content: str, style: str, dry: bool) -> str:
    if style == "md":
        b, e = "<!-- eos:begin (managed by engineering-os; edit personal/PROFILE.user.md) -->", "<!-- eos:end -->"
    else:
        b, e = "# >>> engineering-os (managed; edit mcp/servers.json) >>>", "# <<< engineering-os <<<"
    cur = read(path) if path.exists() else ""
    region = f"{b}\n{content.strip()}\n{e}"
    if b in cur and e in cur:
        new = re.sub(re.escape(b) + r".*?" + re.escape(e), lambda _m: region, cur, flags=re.DOTALL)
    else:
        new = (cur.rstrip("\n") + "\n\n" if cur.strip() else "") + region + "\n"
    if new == cur:
        return "unchanged"
    if not dry:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".eos-bak"))
        write(path, new)
    return "updated" if cur else "created"


def parse_env_file(p: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if p.exists():
        for ln in read(p).splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                vals[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return vals


VAR_RX = _lazy_rx(r"\$\{([A-Z0-9_]+)\}")


def editor_user_dir(home: Path, app: str) -> Path:
    """A VS Code-family editor's User folder: ~/Library/Application Support/<app>/User on macOS,
    %APPDATA%\\<app>\\User on Windows, ~/.config/<app>/User elsewhere. %APPDATA% is only used for the
    real home, so `--home <dir>` (and the tests) never touch the real profile."""
    sysname = platform.system()
    if sysname == "Darwin":
        return home / "Library" / "Application Support" / app / "User"
    if sysname == "Windows":
        appdata = os.environ.get("APPDATA")
        same_home = home.expanduser().resolve() == Path.home().resolve()
        return (Path(appdata) if appdata and same_home else home / "AppData" / "Roaming") / app / "User"
    return home / ".config" / app / "User"


def editor_globalstorage_files(home: Path) -> list[Path]:
    """Cline's MCP settings file inside each installed VS Code-family editor (Cursor, VS Code)."""
    out = []
    for app in ("Cursor", "Code"):
        base = editor_user_dir(home, app)
        if base.is_dir():
            out.append(base / "globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
    return out


def _merge_servers(
    path: Path, entries: dict, prev_managed: list[str], dry: bool, notes: list[str], mode: int | None = None
) -> None:
    try:
        cur = json.loads(read(path)) if path.exists() else {}
    except ValueError:
        notes.append(f"SKIPPED {path}: invalid JSON (fix it by hand)")
        return
    servers = cur.setdefault("mcpServers", {})
    for n in prev_managed:  # servers we managed before but which are now disabled/removed
        if n not in entries:
            servers.pop(n, None)
    servers.update(entries)
    new = json.dumps(cur, indent=2) + "\n"
    if path.exists() and read(path) == new:
        notes.append(f"unchanged {path}")
        return
    if not dry:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".eos-bak"))
            if mode is not None and not IS_WINDOWS:
                os.chmod(path.with_name(path.name + ".eos-bak"), mode)
        write(path, new, mode)
    notes.append(f"wrote {path} ({len(entries)} eos servers; your other servers kept)")


def for_client(enabled: dict, tool: str) -> dict:
    """Servers for one client: `clients` (optional) in servers.json limits a server to some tools."""
    return {n: s for n, s in enabled.items() if tool in s.get("clients", TOOLS_ALL)}


def load_mcp_spec(eos_home: Path) -> dict:
    return json.loads(read(eos_home / "mcp/servers.json"))


def resolve_profile(spec: dict, name: str) -> str:
    """A profile name, or a phase id mapped through `phase_profiles` (e.g. ux-design -> design)."""
    profiles = spec.get("profiles", {})
    if name in profiles:
        return name
    mapped = spec.get("phase_profiles", {}).get(name)
    if mapped in profiles:
        return mapped
    raise SystemExit(
        f"unknown MCP profile or phase '{name}'. Profiles: {', '.join(profiles)}. "
        f"Phases: {', '.join(spec.get('phase_profiles', {}))}"
    )


def tool_profiles(spec: dict, state: dict, tools: list[str]) -> dict[str, str]:
    default = spec.get("default_profile", "build")
    chosen = state.get("mcp_profiles", {})
    return {t: chosen.get(t, default) for t in tools}


def profile_servers(spec: dict, profile: str | None, tool: str) -> dict:
    """Server specs that are ON for `tool` under `profile` (legacy servers.json without profiles: `enabled`)."""
    servers = spec["servers"]
    if "profiles" not in spec or profile is None:
        on = {k: v for k, v in servers.items() if v.get("enabled")}
    else:
        names = spec["profiles"].get(profile, {}).get("servers", [])
        on = {k: servers[k] for k in names if k in servers and servers[k].get("enabled", True)}
    return for_client(on, tool)


def profile_tokens(spec: dict, names) -> tuple[int, list[str]]:
    """Measured per-request schema tokens (what Cline pays); unmeasured servers are listed separately."""
    total, unknown = 0, []
    for n in names:
        t = spec["servers"].get(n, {}).get("tokens")
        if t is None:
            unknown.append(n)
        else:
            total += t
    return total, unknown


# --- eos-launched MCP servers (`"launcher": "eos"` in servers.json) -------------------------------------
# The client config runs `python eos.py mcp run <name>`; the guard below then starts the pinned upstream
# server. Secrets (POSTGRES_MCP_URL) are read here from the environment or secrets.env, so no client config
# ever holds them, and GUI editors that lack your shell environment still work.

PG_DEFAULT_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal", "postgres", "db", "database", "pg")
PG_PROD_HINT = _lazy_rx(r"prod|\blive\b|rds\.amazonaws\.com|azure\.com|supabase\.co|neon\.tech|cloudsql", re.IGNORECASE)
BROWSER_DEFAULT_ORIGINS = ("http://localhost:*", "http://127.0.0.1:*", "https://localhost:*", "https://127.0.0.1:*")


def eos_secrets(home: Path | None = None) -> dict[str, str]:
    return parse_env_file((home or Path.home()) / ".config/engineering-os/secrets.env")


def secret_or_env(name: str, home: Path | None = None) -> str:
    return os.environ.get(name) or eos_secrets(home).get(name, "")


def _kv_dsn(dsn: str) -> dict[str, str]:
    """libpq key=value connection string -> dict (handles 'quoted values' and \\' escapes)."""
    out = {}
    for m in re.finditer(r"(\w+)\s*=\s*('(?:[^'\\]|\\.)*'|\S+)", dsn):
        v = m.group(2)
        if v.startswith("'"):
            v = re.sub(r"\\(.)", r"\1", v[1:-1])
        out[m.group(1).lower()] = v
    return out


def pg_url_hosts(url: str) -> tuple[list[str], dict[str, str]]:
    """Hosts a libpq URL/DSN would connect to ('' = default Unix socket) and its parameters.

    Covers postgres:// URIs with several hosts, ?host= / ?hostaddr= overrides (they win over the
    authority part in libpq), percent-encoded socket paths and key=value strings."""
    from urllib.parse import parse_qsl, unquote

    url = url.strip()
    m = re.match(r"^postgres(?:ql)?://([^/?#]*)([^?#]*)(?:\?([^#]*))?", url, re.IGNORECASE)
    if not m:
        params = _kv_dsn(url)
        hosts = params.get("hostaddr") or params.get("host") or ""
        return [h.strip() for h in hosts.split(",")], params
    netloc, _path, query = m.group(1), m.group(2), m.group(3) or ""
    params = {k.lower(): v for k, v in parse_qsl(query, keep_blank_values=True)}
    if "user" not in params and "@" in netloc:
        params["user"] = unquote(netloc.rsplit("@", 1)[0].split(":", 1)[0])
    hostpart = netloc.rsplit("@", 1)[-1]
    hosts = []
    for h in hostpart.split(",") if hostpart else [""]:
        h = unquote(h)
        if h.startswith("["):
            h = h[1 : h.find("]")]
        elif h.count(":") == 1:
            h = h.split(":", 1)[0]
        hosts.append(h)
    over = params.get("hostaddr") or params.get("host")
    if over is not None:
        hosts = [h.strip() for h in over.split(",")]
    return hosts, params


def pg_allowed_hosts(server: dict, home: Path | None = None) -> list[str]:
    extra = secret_or_env("EOS_MCP_PG_ALLOWED_HOSTS", home)
    hosts = list(server.get("allowed_hosts") or PG_DEFAULT_HOSTS)
    return [h.lower() for h in hosts + [x.strip() for x in extra.split(",") if x.strip()]]


def pg_guard(url: str, allowed: list[str]) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors refuse to start: only allow-listed hosts or local Unix sockets."""
    errs, warns = [], []
    if not url:
        return ["POSTGRES_MCP_URL is empty (set it in ~/.config/engineering-os/secrets.env)"], warns
    hosts, params = pg_url_hosts(url)
    if params.get("service"):
        errs.append("service= is not allowed (a pg_service.conf entry can point anywhere); give host= explicitly")
    for h in hosts:
        if h == "" or h.startswith(("/", "@")):
            continue  # Unix-domain socket on this machine
        if not any(fnmatch.fnmatch(h.lower(), pat) for pat in allowed):
            errs.append(
                f"host '{h}' is not in the dev allow-list ({', '.join(allowed)}). This server is for local/dev "
                "databases only; if this really is a dev host, add it to EOS_MCP_PG_ALLOWED_HOSTS in secrets.env"
            )
        elif PG_PROD_HINT.search(h):
            warns.append(f"host '{h}' looks like a production or cloud database; it is allow-listed, so continuing")
    if params.get("user", "").lower() in ("postgres", "root", "admin", "rdsadmin"):
        warns.append(
            f"user '{params['user']}' looks like a superuser/owner: use the read-only role "
            "(mcp/postgres-readonly-role.sql); read-only is still forced per session"
        )
    return errs, warns


def pg_readonly_url(url: str, timeout: str) -> str:
    """Add session options libpq sends at connect: read-only transactions + statement timeout."""
    from urllib.parse import quote

    opts = f"-c default_transaction_read_only=on -c statement_timeout={timeout}"
    if re.match(r"^postgres(?:ql)?://", url, re.IGNORECASE):
        base, _, frag = url.partition("#")
        _hosts, params = pg_url_hosts(base)
        if "options" in params:
            from urllib.parse import parse_qsl, urlencode

            head, _, q = base.partition("?")
            pairs = [
                (k, f"{v} {opts}" if k.lower() == "options" else v) for k, v in parse_qsl(q, keep_blank_values=True)
            ]
            base = head + "?" + urlencode(pairs, quote_via=quote)
        else:
            base += ("&" if "?" in base else "?") + "options=" + quote(opts, safe="")
        if "application_name" not in params:
            base += "&application_name=eos-mcp"
        return base + (("#" + frag) if frag else "")
    params = _kv_dsn(url)
    merged = (params.get("options", "") + " " + opts).strip()
    out = re.sub(r"\boptions\s*=\s*('(?:[^'\\]|\\.)*'|\S+)", "", url).strip()
    out += " options='" + merged.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if "application_name" not in params:
        out += " application_name=eos-mcp"
    return out


def _find_up(start: Path, rel: str) -> Path | None:
    for d in [start, *start.parents]:
        if (d / rel).is_file():
            return d / rel
        if (d / ".git").exists():
            return None
    return None


def mcp_launch_cmd(
    name: str, server: dict, eos_home: Path, cwd: Path, home: Path | None = None
) -> tuple[list[str], dict[str, str], list[str]]:
    """(argv, env, notes) for an eos-launched server; raises SystemExit with the reason when it must refuse."""
    env = dict(os.environ)
    notes: list[str] = []
    argv = [
        str(eos_home.joinpath(*a[len("{EOS_HOME}/") :].split("/"))) if a.startswith("{EOS_HOME}/") else a
        for a in server["run"]
    ]  # native separators on Windows (no mixed D:\\x/mcp/...)
    argv = [a.replace("{EOS_HOME}", str(eos_home)) for a in argv]
    guard = server.get("guard")
    if guard == "postgres":
        url = secret_or_env("POSTGRES_MCP_URL", home)
        errs, warns = pg_guard(url, pg_allowed_hosts(server, home))
        if errs:
            raise SystemExit("eos mcp: postgres refused: " + "; ".join(errs))
        notes += warns
        timeout = secret_or_env("EOS_MCP_PG_STATEMENT_TIMEOUT", home) or server.get("statement_timeout", "30s")
        if not re.fullmatch(r"\d+(ms|s|min)?", timeout):
            raise SystemExit(f"eos mcp: EOS_MCP_PG_STATEMENT_TIMEOUT '{timeout}' must look like 30s, 5000ms or 1min")
        for k in ("PGHOST", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS", "POSTGRES_MCP_URL"):
            env.pop(k, None)  # libpq fallbacks must not redirect the guarded connection
        env["DATABASE_URI"] = pg_readonly_url(url, timeout)  # env, not argv: not visible in `ps`
    elif guard == "browser":
        extra = secret_or_env("EOS_MCP_BROWSER_ORIGINS", home)
        origins = list(server.get("allowed_origins") or BROWSER_DEFAULT_ORIGINS)
        origins += [o.strip() for o in re.split(r"[;,]", extra) if o.strip()]
        if extra.strip() != "*":
            argv += ["--allowed-origins", ";".join(origins)]
        if secret_or_env("EOS_MCP_BROWSER_HEADED", home) in ("1", "true", "yes"):
            argv = [a for a in argv if a != "--headless"]
        out = (
            (cwd / ".eos/state/playwright")
            if (cwd / ".eos").is_dir()
            else (home or Path.home()) / ".cache/eos-playwright"
        )
        argv += ["--output-dir", str(out)]
        axe = _find_up(cwd, "node_modules/axe-core/axe.min.js")
        if axe:
            argv += ["--init-script", str(axe)]
            notes.append(f"axe-core injected from {axe} (call axe.run() with browser_evaluate)")
    exe = shutil.which(argv[0])
    if not exe:
        raise SystemExit(f"eos mcp: '{argv[0]}' not found on PATH (needed by MCP server '{name}'; see `eos doctor`)")
    return [exe, *argv[1:]], env, notes


def cmd_mcp_run(name: str, eos_home: Path) -> int:
    spec = load_mcp_spec(eos_home)
    server = spec["servers"].get(name)
    if not server or server.get("launcher") != "eos":
        eprint(f"eos mcp run: '{name}' is not an eos-launched server")
        return 2
    try:
        argv, env, notes = mcp_launch_cmd(name, server, eos_home, Path.cwd())
    except SystemExit as e:
        eprint(str(e))  # stderr: shows in the client's MCP log; stdout stays clean for JSON-RPC
        return 3
    for n in notes:
        eprint(f"eos mcp {name}: {n}")
    if IS_WINDOWS:
        return subprocess.call(argv, env=env)
    os.execve(argv[0], argv, env)
    return 0  # not reached


def cline_settings_files(home: Path) -> list[Path]:
    out = editor_globalstorage_files(home)
    if (home / ".cline/data").is_dir():  # Cline CLI (docs.cline.bot/mcp/mcp-overview)
        out.append(home / ".cline/data/settings/cline_mcp_settings.json")
    return out


def windows_python() -> str:
    """The real python.exe that runs eos (a venv's base interpreter outlives the venv); `python` as a fallback."""
    py = sys.executable
    if sys.prefix != sys.base_prefix:
        py = getattr(sys, "_base_executable", None) or py
    return py or "python"


def stdio_command(name: str, s: dict) -> tuple[str, list[str]]:
    """(command, args) a client should run. eos-launched servers go through the guard in `eos mcp run`,
    called with this Python and an absolute path, so GUI apps without your shell PATH can start it."""
    if s.get("launcher") == "eos":
        py = sys.executable
        if sys.prefix != sys.base_prefix:  # bootstrap ran inside a venv: use its base Python, which outlives it
            py = getattr(sys, "_base_executable", None) or py
        return py or ("python" if IS_WINDOWS else "python3"), [str(SELF), "mcp", "run", name]
    return s["command"], list(s.get("args", []))


def server_needs(s: dict) -> list[str]:
    """Secret names a server needs: ${VAR} placeholders plus `needs` (read at launch by `eos mcp run`)."""
    return sorted(
        set(VAR_RX.findall(json.dumps({k: v for k, v in s.items() if k != "needs"}))) | set(s.get("needs", []))
    )


def render_mcp(
    home: Path, eos_home: Path, tools: list[str], dry: bool, prev: list[str], profiles: dict[str, str] | None = None
) -> tuple[list[str], list[str]]:
    full = load_mcp_spec(eos_home)
    spec = full["servers"]
    profiles = profiles or {}

    def active(tool: str) -> dict:
        return profile_servers(full, profiles.get(tool, full.get("default_profile")), tool)

    secrets_file = home / ".config/engineering-os/secrets.env"
    secrets = parse_env_file(secrets_file)
    notes: list[str] = []
    managed = sorted(set(prev) | set(spec))
    if "cursor" in tools:  # Cursor expands ${env:VAR} itself: no values on disk
        entries = {}
        for n, s in active("cursor").items():
            if s["type"] == "http":
                e: dict = {"url": s["url"]}
                if s.get("headers"):
                    e["headers"] = {k: VAR_RX.sub(r"${env:\1}", v) for k, v in s["headers"].items()}
            else:
                cmd, cargs = stdio_command(n, s)
                e = {
                    "command": cmd,
                    "args": cargs,
                    "env": {k: VAR_RX.sub(r"${env:\1}", v) for k, v in s.get("env", {}).items()},
                }
            entries[n] = e
        _merge_servers(home / ".cursor/mcp.json", entries, managed, dry, notes)
    if "cline" in tools:  # Cline needs real values: written only to its private settings file (chmod 600)
        on = active("cline")
        entries = {}
        # every server Cline may use is written; the profile decides `disabled`, so you can also flip one in
        # Cline's MCP panel mid-task. Disabled servers are not started and send no schemas.
        for n, s in for_client({k: v for k, v in spec.items() if v.get("enabled", True)}, "cline").items():
            missing = [v for v in server_needs(s) if not secrets.get(v)]
            if missing:
                if n in on:
                    notes.append(f"cline: skipped '{n}' (set {', '.join(missing)} in {secrets_file})")
                continue

            def sub(v: str) -> str:
                return VAR_RX.sub(lambda m: secrets[m.group(1)], v)

            if s["type"] == "http":
                e = {
                    "type": "streamableHttp",
                    "url": s["url"],
                    "headers": {k: sub(v) for k, v in s.get("headers", {}).items()},
                }
            else:
                cmd, cargs = stdio_command(n, s)
                e = {"command": cmd, "args": cargs, "env": {k: sub(v) for k, v in s.get("env", {}).items()}}
            auto = (
                s.get("safe_tools", [])
                if secrets.get("EOS_MCP_CLINE_AUTO_APPROVE_SAFE") in ("1", "true", "yes")
                else []
            )
            e.update({"disabled": n not in on, "autoApprove": list(auto)})
            entries[n] = e
        targets = cline_settings_files(home)
        if not targets:
            notes.append("cline: no Cursor/VS Code user folder found; skipped (re-run after installing the editor)")
        for t in targets:
            _merge_servers(t, entries, managed, dry, notes, 0o600)
        tok, unk = profile_tokens(full, [n for n, e in entries.items() if not e["disabled"]])
        notes.append(
            f"cline: profile '{profiles.get('cline', full.get('default_profile'))}' on: "
            f"{', '.join(n for n, e in entries.items() if not e['disabled']) or '(none)'} "
            f"(~{tok:,} schema tokens per request{', + unmeasured ' + ', '.join(unk) if unk else ''})"
        )
    if "codex" in tools:  # Codex reads env var *names* (bearer_token_env_var / env_http_headers)
        cfg_path = home / ".codex/config.toml"
        outside = (
            re.sub(r"# >>> engineering-os.*?# <<< engineering-os <<<", "", read(cfg_path), flags=re.DOTALL)
            if cfg_path.exists()
            else ""
        )
        lines: list[str] = []
        for n, s in active("codex").items():
            if re.search(rf"^\[mcp_servers\.{re.escape(n)}\]", outside, re.MULTILINE):
                notes.append(f"codex: '{n}' is already defined by you in config.toml; left alone")
                continue
            lines.append(f"[mcp_servers.{n}]")
            if s["type"] == "http":
                lines.append(f"url = {json.dumps(s['url'])}")
                envh, static = {}, {}
                for k, v in s.get("headers", {}).items():
                    m = re.fullmatch(r"Bearer \$\{([A-Z0-9_]+)\}", v)
                    if k.lower() == "authorization" and m:
                        lines.append(f"bearer_token_env_var = {json.dumps(m.group(1))}")
                    elif VAR_RX.fullmatch(v):
                        envh[k] = VAR_RX.fullmatch(v).group(1)  # type: ignore[union-attr]
                    else:
                        static[k] = v
                if envh:
                    lines.append(
                        "env_http_headers = { "
                        + ", ".join(f"{json.dumps(k)} = {json.dumps(v)}" for k, v in envh.items())
                        + " }"
                    )
                if static:
                    lines.append(
                        "http_headers = { "
                        + ", ".join(f"{json.dumps(k)} = {json.dumps(v)}" for k, v in static.items())
                        + " }"
                    )
            else:
                cmd, cargs = stdio_command(n, s)
                lines.append(f"command = {json.dumps(cmd)}")
                lines.append("args = [" + ", ".join(json.dumps(a) for a in cargs) + "]")
            lines.append("")
        notes.append(f"{upsert_block(cfg_path, chr(10).join(lines), 'toml', dry)} {cfg_path}")
    if "claude" in tools:  # Claude Code: user-scope servers via its CLI; ${VAR} kept literal, expanded at load
        cmds = [f"claude mcp remove --scope user {n} >/dev/null 2>&1 || true" for n in prev]  # only names eos added
        for n, s in active("claude").items():
            if s["type"] == "http":
                hdr = " ".join(f"--header '{k}: {v}'" for k, v in s.get("headers", {}).items())
                cmds.append(f"claude mcp add --scope user --transport http {n} {s['url']} {hdr}".rstrip())
            else:
                cmd, cargs = stdio_command(n, s)
                cmds.append(f"claude mcp add --scope user {n} -- {' '.join(shlex.quote(x) for x in [cmd, *cargs])}")
        script = home / ".config/engineering-os/claude-mcp.sh"
        body = (
            "#!/usr/bin/env sh\n# Generated by `eos bootstrap`. Run once. No secret values here: ${VAR} stays literal\n"
            "# (single quotes) and Claude Code expands it from your environment. Check with `claude mcp list`.\n"
            "# shellcheck disable=SC2016\n" + "\n".join(cmds) + "\n"
        )
        if not dry:
            write(script, body, 0o700)
        notes.append(f"claude: run {script} once")
    return sorted(spec), notes


CLINE_EXT = "saoudrizwan.claude-dev"  # Cline's id on the VS Code Marketplace and Open VSX
# Shown after bootstrap. OpenRouter prices checked on https://openrouter.ai/api/v1/models (Oct 2026).
CLINE_MODELS = (
    ("Act", "anthropic/claude-haiku-5.5", "None", "$0.10 in / $0.50 out"),
    ("Plan", "anthropic/claude-sonnet-5.5", "Low", "$2 in / $10 out"),
)


def cursor_cli(home: Path, real_home: bool) -> str | None:
    """Cursor's command-line launcher (used only to install Cline): `cursor` on PATH, then the default install
    folders. With `--home <dir>` (tests) only that folder is searched, never PATH or system folders."""
    if real_home:
        found = shutil.which("cursor")
        if found:
            return found
    sysname = platform.system()
    cands: list[Path] = []
    if sysname == "Windows":
        local = os.environ.get("LOCALAPPDATA") if real_home else None
        cands.append(
            (Path(local) if local else home / "AppData" / "Local") / "Programs/cursor/resources/app/bin/cursor.cmd"
        )
        if real_home:
            cands.append(
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "cursor/resources/app/bin/cursor.cmd"
            )
    elif sysname == "Darwin":
        cands.append(home / "Applications/Cursor.app/Contents/Resources/app/bin/cursor")
        if real_home:
            cands.append(Path("/Applications/Cursor.app/Contents/Resources/app/bin/cursor"))
    elif real_home:
        cands += [Path("/usr/share/cursor/bin/cursor"), Path("/opt/Cursor/resources/app/bin/cursor")]
    return next((str(c) for c in cands if c.is_file()), None)


def install_cline(home: Path, real_home: bool, dry: bool) -> tuple[bool, str]:
    """Install the Cline extension into Cursor through Cursor's CLI. Idempotent, never fatal:
    (installed or already there, log line). Without the CLI the log line is the manual step."""
    manual = "install it by hand: Cursor > Extensions (Ctrl+Shift+X) > search 'Cline' > Install"
    cli = cursor_cli(home, real_home)
    if not cli:
        return False, f"cline: Cursor's command-line tool not found (is Cursor installed?); {manual}"
    code, out = run([cli, "--list-extensions"], timeout=120)
    if code != 0:
        return False, f"cline: `cursor --list-extensions` failed (exit {code}); {manual}"
    if CLINE_EXT in [ln.strip().lower().split("@")[0] for ln in out.splitlines()]:
        return True, f"cline: extension {CLINE_EXT} already installed in Cursor"
    if dry:
        return False, f"cline: would install {CLINE_EXT} into Cursor ({cli})"
    code, out = run([cli, "--install-extension", CLINE_EXT], timeout=600)
    if code != 0:
        tail = out.strip().splitlines()[-1][:120] if out.strip() else ""
        return False, f"cline: install failed (exit {code}{': ' + tail if tail else ''}); {manual}"
    return True, f"cline: installed {CLINE_EXT} into Cursor (restart Cursor to see it)"


def human_checklist(
    home: Path, eos_home: Path, tools: list[str], profiles: dict[str, str], cline_ok: bool | None
) -> list[str]:
    """What only the person at the keyboard can do after bootstrap. Key names only, never values."""
    sfile = home / ".config/engineering-os/secrets.env"
    vals = parse_env_file(sfile)
    full = load_mcp_spec(eos_home)
    on = {n: sv for t, p in profiles.items() for n, sv in profile_servers(full, p, t).items()}
    need = sorted({x for sv in on.values() for x in server_needs(sv)})
    later = sorted(
        {x for n, sv in full["servers"].items() if sv.get("enabled", True) and n not in on for x in server_needs(sv)}
        - set(need)
    )
    empty = [x for x in need if not vals.get(x) and not os.environ.get(x)]
    later_empty = [x for x in later if not vals.get(x) and not os.environ.get(x)]
    steps: list[str] = []
    if empty or later_empty:
        msg = f"Keys: in {sfile}, fill " + (", ".join(empty) + " (used now)" if empty else "")
        if later_empty:
            msg += ("; later, " if empty else "") + ", ".join(later_empty) + " (only for other `eos mcp use` profiles)"
        if IS_WINDOWS:
            msg += ". Re-run bootstrap.ps1: it also copies the keys Cursor uses into your user environment variables"
        steps.append(
            msg
            + (" (then restart Cursor)" if IS_WINDOWS else ". Then re-run bootstrap")
            + ". Keep a copy in a password manager; never commit them."
        )
    if "cline" in tools:
        steps.append(
            ("Cline is installed. " if cline_ok else "Install Cline: Cursor > Extensions > search 'Cline' > Install. ")
            + "Restart Cursor, press Ctrl+Shift+P (macOS: Cmd+Shift+P), run 'Cline: Focus on View'."
        )
        steps.append(
            "In Cline pick 'Bring my own API key' > API Provider 'OpenRouter' > paste your OpenRouter key. "
            "That key lives in Cline's settings, not in secrets.env."
        )
        steps.append(
            "Models (tick 'Use different models for Plan and Act modes'; OpenRouter prices per million tokens, "
            "as of Oct 2026): "
            + "; ".join(f"{mode} = {mid} ({price}), reasoning {eff}" for mode, mid, eff, price in CLINE_MODELS)
            + ". Test: type 'say hello' in Cline."
        )
    steps.append("Check the machine: open a NEW terminal and run `eos doctor`.")
    steps.append(
        "Open a project folder in Cursor, open its terminal, run `eos adopt` (existing code) or "
        "`eos start` (new idea), then `eos next`."
    )
    return [f"{i}. {s}" for i, s in enumerate(steps, 1)]


LAUNCH_PY = "import sys; sys.path.insert(0, r{q}{d}{q}); import eos; sys.exit(eos.main())"


def cmd_bootstrap(args: argparse.Namespace) -> int:
    eos_home = find_eos_home()
    if not eos_home:
        eprint("run bootstrap from your engineering-os checkout")
        return 2
    home = Path(args.home).resolve() if args.home else Path.home()
    tools = parse_tools(args.tools)
    dry = args.dry_run
    state = load_global_state(home)
    log: list[str] = []
    # 1. `eos` launcher on PATH
    bindir = home / ".local/bin"
    # import eos (bytecode cached) instead of running the 13k-line script: ~150 ms saved per command
    if IS_WINDOWS:
        # the absolute interpreter, quoted: works from any terminal and with spaces (C:\Users\Jane Doe\...)
        code = LAUNCH_PY.format(d=SELF.parent, q="'")
        launcher, body = bindir / "eos.cmd", f'@echo off\r\n"{windows_python()}" -c "{code}" %*\r\n'
    else:
        code = LAUNCH_PY.format(d=SELF.parent, q='"')
        launcher, body = bindir / "eos", f"#!/usr/bin/env sh\nexec python3 -c '{code}' \"$@\"\n"
    if not dry:
        write(launcher, body, 0o755)
    on_path = str(bindir) in os.environ.get("PATH", "").split(os.pathsep)
    log.append(f"launcher {launcher}" + ("" if on_path else "  (not on PATH yet: `eos doctor` prints the line to add)"))
    # 2. personal profile -> each tool's global instructions (managed block; your other text is kept)
    profile = read(profile_file(eos_home))
    if "cursor" in tools:
        mdc = home / ".cursor/rules/eos-profile.mdc"
        if not dry:
            write(
                mdc,
                "---\ndescription: Personal profile and defaults (engineering-os)\nalwaysApply: true\n---\n"
                "<!-- eos-managed: edit personal/PROFILE.user.md (or PROFILE.md) in your engineering-os repo, then `eos bootstrap` -->\n"
                + profile,
            )
        log.append(
            f"cursor: {mdc} (if your Cursor version ignores user rule files, paste PROFILE.md into "
            "Settings > Rules > User Rules)"
        )
    for tool, p in (
        ("cline", home / ".agents/AGENTS.md"),
        ("codex", home / ".codex/AGENTS.md"),
        ("claude", home / ".claude/CLAUDE.md"),
    ):
        if tool in tools:
            log.append(f"{tool}: {upsert_block(p, profile, 'md', dry)} {p}")
    # 3. global skills (eos-retro, eos-handoff, eos-new-stack-pack)
    gdirs, _ = skill_dirs(tools, "global")
    for old in {".agents/skills", ".cline/skills", ".claude/skills"} - set(gdirs):  # a copy here would list twice
        for sk in sorted((eos_home / "personal/skills").iterdir()):
            dest = home / old / sk.name
            if (dest / ".eos-managed").exists():
                if not dry:
                    shutil.rmtree(dest)
                log.append(f"removed duplicate skill copy {dest}")
    for sd in sorted(home / d for d in gdirs):
        for sk in sorted((eos_home / "personal/skills").iterdir()):
            dest = sd / sk.name
            if dest.exists() and not (dest / ".eos-managed").exists():
                log.append(f"kept your own skill {dest}")
                continue
            if not dry:
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(sk, dest)
                write(dest / ".eos-managed", "managed by engineering-os; local edits are overwritten\n")
        log.append(f"skills -> {sd}")
    # 4. secrets file (outside git, owner-only) + MCP configs
    sfile = home / ".config/engineering-os/secrets.env"
    if not sfile.exists():
        if not dry:
            write(sfile, read(eos_home / "mcp/secrets.env.example"), 0o600)
        log.append(f"created {sfile} (owner-only). Fill in tokens, then re-run `eos bootstrap`.")
    elif not IS_WINDOWS and sfile.stat().st_mode & 0o077:
        if not dry:
            os.chmod(sfile, 0o600)
        log.append(f"fixed permissions on {sfile} -> 600")
    managed_mcp = state.get("mcp_servers", [])
    if not args.no_mcp:
        spec = load_mcp_spec(eos_home)
        managed_mcp, notes = render_mcp(home, eos_home, tools, dry, managed_mcp, tool_profiles(spec, state, tools))
        log += ["mcp " + n for n in notes]
    # 5. global gitignore + optional global git hooks
    genv = dict(os.environ)
    if args.home:
        genv.update(HOME=str(home), GIT_CONFIG_GLOBAL=str(home / ".gitconfig"), XDG_CONFIG_HOME=str(home / ".config"))
    _, excl = run(["git", "config", "--global", "core.excludesFile"], env=genv, timeout=10)
    excl_path = Path(excl.strip().replace("~", str(home), 1)) if excl.strip() else home / ".config/git/ignore"
    wanted = [".eos/state/", "*.eos-bak", "*.eos-new", ".env", ".env.*", "!.env.example", "*.user.toml"]
    cur = read(excl_path) if excl_path.exists() else ""
    missing = [ln for ln in wanted if ln not in cur.splitlines()]
    if missing and not dry:
        write(
            excl_path,
            cur + ("" if not cur or cur.endswith("\n") else "\n") + "# engineering-os\n" + "\n".join(missing) + "\n",
        )
    log.append(f"global gitignore {excl_path} (+{len(missing)} lines)")
    if args.global_hooks:
        hooks = eos_home / "git-hooks"
        if not dry:
            if not IS_WINDOWS:
                for f in hooks.iterdir():
                    f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            run(["git", "config", "--global", "core.hooksPath", str(hooks)], env=genv, timeout=10)
        log.append(f"git core.hooksPath -> {hooks} (gitleaks everywhere + each repo's pre-commit config)")
    if args.install_clis:
        log += install_clis(dry)
    # 6. Cline extension into Cursor (only when Cline is one of the tools; never fatal)
    cline_ok = None
    if "cline" in tools and not args.no_cline_install:
        cline_ok, line = install_cline(home, not args.home, dry)  # --home (tests): never the real Cursor
        log.append(line)
    state.update(
        {
            "eos_version": eos_version(eos_home),
            "eos_home": str(eos_home),
            "tools": tools,
            "mcp_servers": managed_mcp,
            "bootstrapped": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
    )
    if not dry:
        write(global_state_path(home), json.dumps(state, indent=2) + "\n")
    print(f"eos bootstrap ({'DRY RUN, ' if dry else ''}tools: {', '.join(tools)}, home: {home})")
    for ln in log:
        print("  " + ln)
    profs = tool_profiles(load_mcp_spec(eos_home), state, tools)
    print("\nWhat only you can do now (full guide: docs/NEW-MACHINE.md):")
    for ln in human_checklist(home, eos_home, tools, profs, cline_ok):
        print("  " + ln)
    return 0


def install_clis(dry: bool) -> list[str]:
    """Only brew is automated (no sudo). Elsewhere we print the commands: you stay in control."""
    sysname = platform.system()
    if sysname == "Darwin" and shutil.which("brew"):
        cmd = ["brew", "install", "uv", "node", "pnpm", "pre-commit", "gitleaks", "shellcheck", "actionlint", "gh"]
        if dry:
            return ["would run: " + " ".join(cmd)]
        code, _ = run(cmd, timeout=3600)
        return [f"{' '.join(cmd)} -> exit {code}"]
    if sysname == "Windows":
        return [
            (
                "windows: see docs/bootstrap.md (winget install astral-sh.uv, OpenJS.NodeJS.LTS, GitHub.cli, "
                "Gitleaks.Gitleaks; then `uv tool install pre-commit`)"
            )
        ]
    return [
        (
            "linux: see docs/bootstrap.md (apt/dnf for git, shellcheck, gh; `uv tool install pre-commit`; "
            "gitleaks and actionlint from their GitHub releases). eos never runs sudo for you."
        )
    ]


def parse_tools(s: str | None) -> list[str]:
    tools = [t.strip() for t in (s or ",".join(DEFAULT_TOOLS)).split(",") if t.strip()]
    if tools == ["all"]:
        return list(TOOLS_ALL)
    bad = [t for t in tools if t not in TOOLS_ALL]
    if bad:
        raise SystemExit(f"unknown tool(s) {bad}; choose from {', '.join(TOOLS_ALL)} or 'all'")
    return tools


def read_versions(home: Path) -> dict[str, str]:
    out = {}
    p = home / "versions.toml"
    if p.exists():
        for ln in read(p).splitlines():
            m = re.match(r'^\s*"?([\w.@/-]+)"?\s*=\s*"([^"]+)"', ln)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def cmd_mcp(args: argparse.Namespace) -> int:
    """MCP profiles: which servers are on, per tool. `use` re-renders only MCP configs."""
    eos_home = find_eos_home()
    if not eos_home:
        eprint("needs the engineering-os repo (set EOS_HOME)")
        return 2
    if args.action == "run":
        return cmd_mcp_run(args.profile or "", eos_home)
    home = Path(args.home).resolve() if getattr(args, "home", None) else Path.home()
    spec, state = load_mcp_spec(eos_home), load_global_state(home)
    tools = parse_tools(args.tools) if getattr(args, "tools", None) else list(state.get("tools", DEFAULT_TOOLS))
    profs = tool_profiles(spec, state, tools)
    if args.action == "list":
        print("MCP profiles (Cline pays the schema tokens on every request; Cursor/Claude Code/Codex load on demand)")
        sw = max((len(", ".join(p["servers"])) for p in spec.get("profiles", {}).values()), default=6) + 1
        for name, p in spec.get("profiles", {}).items():
            tok, unk = profile_tokens(spec, p["servers"])
            mark = ",".join(t for t, x in profs.items() if x == name)
            cost = f"~{tok:,}" + (f" + {'/'.join(unk)} (unmeasured)" if unk else "")
            print(
                f"  {name:<9} {', '.join(p['servers']) or '(none)':<{sw}} {cost:<29} {p.get('use', '')}"
                + (f"  [{mark}]" if mark else "")
            )
        pp = spec.get("phase_profiles", {})
        if pp:
            print("  phases -> " + ", ".join(f"{k}:{v}" for k, v in pp.items()))
        return 0
    if args.action == "status":
        for t, p in profs.items():
            on = profile_servers(spec, p, t)
            tok, unk = profile_tokens(spec, on)
            extra = f"  (~{tok:,} tokens/request{' + ' + '/'.join(unk) if unk else ''})" if t == "cline" else ""
            print(f"  {t:<7} {p:<9} {', '.join(on) or '(none)'}{extra}")
        return 0
    if not args.profile:
        eprint("usage: eos mcp use <profile|phase> [--tools cline]")
        return 2
    prof = resolve_profile(spec, args.profile)
    chosen = state.setdefault("mcp_profiles", {})
    for t in tools:
        chosen[t] = prof
    managed, notes = render_mcp(
        home, eos_home, tools, args.dry_run, state.get("mcp_servers", []), tool_profiles(spec, state, tools)
    )
    state["mcp_servers"] = sorted(set(state.get("mcp_servers", [])) | set(managed))
    if not args.dry_run:
        write(global_state_path(home), json.dumps(state, indent=2) + "\n")
    print(f"eos mcp use {prof} ({', '.join(tools)}){' DRY RUN' if args.dry_run else ''}")
    for n in notes:
        print("  " + n)
    if "cursor" in tools or "claude" in tools:
        print(
            "  reload: Cursor picks up mcp.json changes (or toggle in Settings > MCP); Cline reloads its file itself."
        )
    return 0


OPENROUTER = "https://openrouter.ai/api/v1"


def load_models_cfg(eos_home: Path) -> dict:
    """personal/models.toml, with personal/models.user.toml (git-ignored) merged over it per table."""
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        raise SystemExit("eos models needs Python 3.11+ (tomllib)") from None
    cfg: dict = {}
    for name in ("models.toml", "models.user.toml"):
        p = eos_home / "personal" / name
        if p.exists():
            for k, v in tomllib.loads(read(p)).items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k] = {**cfg[k], **v}
                else:
                    cfg[k] = v
    return cfg


def models_errors(cfg: dict) -> list[str]:
    tiers = cfg.get("tiers", {})
    errs = [f"routing.{t} -> unknown tier '{x}'" for t, x in cfg.get("routing", {}).items() if x not in tiers]
    errs += [f"tiers.{t} has no models" for t, v in tiers.items() if not v.get("models")]
    return errs


def tier_for(cfg: dict, task: str, failures: int = 0) -> str:
    order = list(cfg.get("tiers", {}))  # premium, strong, cheap (best first)
    tier = cfg.get("routing", {}).get(task, "strong")
    n = int(cfg.get("policy", {}).get("escalate_after_failures", 2))
    steps = failures // n if n > 0 else 0
    return order[max(0, order.index(tier) - steps)] if tier in order else tier


def _http_json(url: str, token: str | None = None, timeout: int = 20) -> dict:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "engineering-os"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def cmd_models(args: argparse.Namespace) -> int:
    eos_home = find_eos_home()
    if not eos_home:
        eprint("needs the engineering-os repo (set EOS_HOME)")
        return 2
    cfg = load_models_cfg(eos_home)
    errs = models_errors(cfg)
    for e in errs:
        print(f"  ERROR {e}")
    if args.task:
        t = tier_for(cfg, args.task, args.failures)
        print(f"{args.task} -> {t}: {', '.join(cfg['tiers'][t]['models'])}")
        return 1 if errs else 0
    print("model routing (personal/models.toml; Cline: Plan = premium, Act = strong)")
    for t, v in cfg.get("tiers", {}).items():
        tasks = [k for k, x in cfg.get("routing", {}).items() if x == t]
        print(f"  {t:<8} {', '.join(v.get('models', []))}\n           tasks: {', '.join(tasks)}  ({v.get('use', '')})")
    b = cfg.get("budget", {})
    caps = ", ".join(f"{k} {b[k]}" for k in ("daily", "weekly", "monthly") if b.get(k)) or "none set"
    print(f"  budget caps ({b.get('currency', 'USD')}): {caps}. Enforce with an OpenRouter per-key limit.")
    rc = 1 if errs else 0
    if args.check:
        try:
            live = {m["id"]: m for m in _http_json(f"{OPENROUTER}/models")["data"]}
        except (OSError, ValueError, KeyError) as e:  # network, proxy, JSON
            print(f"  check: could not reach OpenRouter ({e.__class__.__name__}); try again later")
            return 2
        print("  live check (USD per 1M tokens in/out, from openrouter.ai/api/v1/models):")
        for t, v in cfg.get("tiers", {}).items():
            for mid in v.get("models", []):
                m = live.get(mid)
                if not m:
                    print(f"    MISSING  {mid} ({t}): not in the catalogue any more; pick another")
                    rc = 1
                    continue
                p = m.get("pricing", {})
                try:
                    price = f"{float(p.get('prompt', 0)) * 1e6:.2f} / {float(p.get('completion', 0)) * 1e6:.2f}"
                except (TypeError, ValueError):
                    price = "?"
                tools_ok = "tools" in m.get("supported_parameters", [])
                print(
                    f"    ok       {mid:<36} {t:<8} {price:<14} ctx {m.get('context_length', '?')}"
                    + ("" if tools_ok else "  WARN no tool calling")
                )
    if args.usage:
        key = os.environ.get("OPENROUTER_API_KEY") or parse_env_file(
            Path.home() / ".config/engineering-os/secrets.env"
        ).get("OPENROUTER_API_KEY")
        if not key:
            print("  usage: set OPENROUTER_API_KEY in ~/.config/engineering-os/secrets.env (optional)")
            return rc
        try:
            k = _http_json(f"{OPENROUTER}/key", key)["data"]
        except (OSError, ValueError, KeyError) as e:
            print(f"  usage: request failed ({e.__class__.__name__})")
            return 2
        warn = float(b.get("warn_at", 0.8))
        print(f"  key limit: {k.get('limit')} (reset {k.get('limit_reset')}), remaining {k.get('limit_remaining')}")
        for period in ("daily", "weekly", "monthly"):
            used, cap = float(k.get(f"usage_{period}", 0) or 0), float(b.get(period, 0) or 0)
            flag = "  OVER" if cap and used >= cap else ("  WARN" if cap and used >= warn * cap else "")
            print(f"    {period:<8} used {used:.2f}" + (f" of cap {cap:.2f}" if cap else "") + flag)
            rc = rc or (1 if flag.strip() == "OVER" else 0)
    return rc


# ----------------------------------------------------------------------------- doctor / detect / new-stack
# name -> (level, why, brew, winget, other). Level: required | recommended | optional.
DOCTOR_TOOLS = {
    "git": ("required", "everything", "git", "Git.Git", "your package manager"),
    "uv": (
        "recommended",
        "python stacks, pre-commit install",
        "uv",
        "astral-sh.uv",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    ),
    "node": (
        "recommended",
        "node stacks, BMAD, npx MCP servers",
        "node",
        "OpenJS.NodeJS.LTS",
        "https://nodejs.org or your package manager",
    ),
    "npx": ("recommended", "BMAD, stdio MCP", "node", "OpenJS.NodeJS.LTS", "comes with node"),
    "pnpm": ("optional", "pnpm projects", "pnpm", "pnpm.pnpm", "corepack enable pnpm"),
    "pre-commit": (
        "recommended",
        "local quality gates",
        "pre-commit",
        "(uv tool install pre-commit)",
        "uv tool install pre-commit",
    ),
    "gitleaks": (
        "recommended",
        "secret scan before commit",
        "gitleaks",
        "Gitleaks.Gitleaks",
        "https://github.com/gitleaks/gitleaks/releases",
    ),
    "gh": ("recommended", "PRs and issues from the terminal and agents", "gh", "GitHub.cli", "https://cli.github.com"),
    "docker": (
        "optional",
        "testcontainers, compose, local Postgres/Redis",
        "--cask docker",
        "Docker.DockerDesktop",
        "https://docs.docker.com/engine/install/",
    ),
    "shellcheck": ("optional", "shell lint", "shellcheck", "koalaman.shellcheck", "your package manager"),
    "actionlint": (
        "optional",
        "workflow lint",
        "actionlint",
        "rhysd.actionlint",
        "https://github.com/rhysd/actionlint/releases",
    ),
    "claude": ("optional", "Claude Code", "", "", "https://docs.anthropic.com/en/docs/claude-code"),
    "codex": ("optional", "Codex CLI", "", "", "https://developers.openai.com/codex"),
}


def _fix_hint(name: str) -> str:
    _lvl, _why, brew, winget, other = DOCTOR_TOOLS[name]
    sysname = platform.system()
    if sysname == "Darwin" and brew:
        return f"brew install {brew}"
    if sysname == "Windows" and winget:
        return winget if winget.startswith("(") else f"winget install {winget}"
    return other


def memory_warnings(root: Path, max_commits: int = 25) -> list[str]:
    """Stale memory misleads agents more than no memory: warn when active-context lags far behind the code."""
    out = []
    ac = root / "memory/active-context.md"
    if not ac.exists() or not (root / ".git").exists():
        return out
    code, last = run(["git", "log", "-1", "--format=%H", "--", "memory/active-context.md"], cwd=root, timeout=10)
    if code != 0 or not last.strip():
        return out
    code, n = run(["git", "rev-list", "--count", f"{last.strip()}..HEAD"], cwd=root, timeout=10)
    if code == 0 and n.strip().isdigit() and int(n) > max_commits:
        out.append(
            f"memory/active-context.md last changed {n.strip()} commits ago: refresh it (eos-handoff) or clear it"
        )
    hp = root / "memory/handoff.md"
    if hp.exists() and "TODO" not in read(hp) and time.time() - hp.stat().st_mtime > 14 * 86400:
        out.append("memory/handoff.md is over 14 days old: delete what no longer applies")
    return out


def doctor_project(root: Path, eos_home: Path | None) -> list[tuple[str, str]]:
    """(status, message) for the project in `root`. status: ok | fix | warn | info."""
    out: list[tuple[str, str]] = []
    m = load_manifest(root)
    if not m:
        return [("info", f"{root} is not an eos project: `eos init {root}`")]
    pv, hv = m.get("eos_version", "?"), eos_version(eos_home) if eos_home else "?"
    out.append(
        ("ok" if pv == hv else "fix", f"project eos {pv}" + ("" if pv == hv else f" < {hv}: `eos update {root}`"))
    )
    hooks = root / ".git/hooks/pre-commit"
    _, hp = run(["git", "config", "core.hooksPath"], cwd=root, timeout=5)
    if (root / ".pre-commit-config.yaml").exists() and not hooks.exists() and not hp.strip():
        out.append(
            (
                "fix",
                (
                    "pre-commit hooks not installed: `pre-commit install --install-hooks` (do it while online: the first "
                    "run downloads every hook tool, so a commit on a bad connection would hang)"
                ),
            )
        )
    news = [p.relative_to(root).as_posix() for p in root.rglob("*.eos-new") if ".git" not in p.parts][:5]
    if news:
        out.append(("fix", f"unmerged eos updates: {', '.join(news)} (merge, delete .eos-new, `eos sync`)"))
    agents = read(root / "AGENTS.md") if (root / "AGENTS.md").exists() else ""
    if "<one or two lines>" in agents or "{{" in agents:
        out.append(("fix", "AGENTS.md 'Project specifics' still has placeholders: fill them (agents guess otherwise)"))
    out += [("warn", w) for w in memory_warnings(root)]
    return out


def _local_time(iso: str | None) -> str:
    try:
        return dt.datetime.fromisoformat(iso or "").astimezone().strftime("%Y-%m-%d %H:%M %Z")
    except ValueError:
        return str(iso)


def cmd_doctor(args: argparse.Namespace) -> int:
    """Every problem line ends with the command that fixes it. Exit 1 only when something required is missing."""
    py = "python" if IS_WINDOWS else "python3"
    bad, todo = 0, 0
    print("eos doctor")
    v = sys.version_info
    print(
        f"  ok       {py:<11} {v.major}.{v.minor}.{v.micro}"
        + ("" if v >= (3, 11) else "  (3.11+ needed for `eos models`)")
    )
    for name, (lvl, why, *_r) in DOCTOR_TOOLS.items():
        exe = shutil.which(name)  # honours PATHEXT: finds npx.cmd / claude.cmd on Windows
        code, out = (127, "")
        if exe:
            code, out = run([exe, "version" if name == "gitleaks" else "--version"], timeout=15)
        if exe and code != 127:
            first = out.strip().splitlines()[0][:60] if out.strip() else ""
            print(f"  ok       {name:<11} {first}")
        elif lvl == "optional":
            print(f"  -        {name:<11} optional ({why})")
        else:
            bad += lvl == "required"
            todo += 1
            print(f"  {'MISSING' if lvl == 'required' else 'fix':<8} {name:<11} {why} -> {_fix_hint(name)}")
    bindir = Path.home() / ".local/bin"
    if str(bindir) not in os.environ.get("PATH", "").split(os.pathsep):
        todo += 1
        hint = (
            f'setx PATH "%PATH%;{bindir}"'
            if IS_WINDOWS
            else f"echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.{'zshrc' if 'zsh' in os.environ.get('SHELL', '') else 'bashrc'}"
        )
        print(f"  fix      PATH        {bindir} is not on PATH -> {hint}")
    if platform.system() == "Linux" and "microsoft" in platform.release().lower():
        cwd = str(Path.cwd())
        print(
            "  info     WSL         run editors via their WSL remote; keep repos under ~/ (not /mnt/c) for speed and file watching"
        )
        if cwd.startswith("/mnt/"):
            todo += 1
            print(f"  fix      WSL         {cwd} is on the Windows drive -> clone it under ~/ inside WSL")
    st = load_global_state()
    eos_home = find_eos_home()
    if not st:
        todo += 1
        print(
            "  fix      bootstrap   never run on this machine -> `python3 bin/eos.py bootstrap` in your engineering-os checkout"
        )
    elif eos_home and st.get("eos_version") != eos_version(eos_home):
        todo += 1
        print(
            f"  fix      bootstrap   machine set up with eos {st.get('eos_version')} < {eos_version(eos_home)} -> `eos bootstrap`"
        )
    else:
        print(f"  ok       bootstrap   {_local_time(st.get('bootstrapped'))}  tools: {', '.join(st.get('tools', []))}")
    sfile = Path.home() / ".config/engineering-os/secrets.env"
    vals = parse_env_file(sfile) if sfile.exists() else {}
    if not sfile.exists():
        print("  -        secrets     not created yet (eos bootstrap creates it)")
    elif not IS_WINDOWS and sfile.stat().st_mode & 0o077:
        todo += 1
        print(f"  fix      secrets     {sfile} is readable by others -> chmod 600 {sfile}")
    if eos_home:
        full = load_mcp_spec(eos_home)
        profs = tool_profiles(full, st, list(st.get("tools", DEFAULT_TOOLS)))
        on = {n: sv for t, p in profs.items() for n, sv in profile_servers(full, p, t).items()}
        need = sorted({x for sv in on.values() for x in server_needs(sv)})
        empty = [x for x in need if not vals.get(x) and not os.environ.get(x)]
        launched = {x for sv in on.values() if sv.get("launcher") == "eos" for x in sv.get("needs", [])}
        unset = [x for x in need if not os.environ.get(x) and x not in launched]
        print(f"  ok       mcp         profiles {', '.join(f'{t}={p}' for t, p in profs.items())} (eos mcp list)")
        if empty:
            todo += 1
            print(f"  fix      secrets     empty in secrets.env: {', '.join(empty)} -> fill them, then `eos bootstrap`")
        if unset and any(t in profs for t in ("cursor", "claude", "codex")):
            print(
                f"  warn     env         not in this shell: {', '.join(unset)} (Cursor/Claude Code/Codex read env vars;"
                " see mcp/README.md 'Env vars and GUI apps')"
            )
        for n, sv in sorted(on.items()):
            if sv.get("launcher") != "eos":
                continue
            exe = sv["run"][0]
            if not shutil.which(exe):
                todo += 1
                print(
                    f"  fix      mcp         '{n}' needs `{exe}` on PATH -> {_fix_hint(exe) if exe in DOCTOR_TOOLS else exe}"
                )
            if sv.get("guard") == "postgres":
                url = secret_or_env("POSTGRES_MCP_URL")
                if url:
                    errs, warns = pg_guard(url, pg_allowed_hosts(sv))
                    for e in errs:
                        todo += 1
                        print(f"  fix      mcp         postgres: {e}")
                    for w in warns:
                        print(f"  warn     mcp         postgres: {w}")
                    if not errs:
                        hosts = ", ".join(h or "(local socket)" for h in pg_url_hosts(url)[0])
                        print(f"  ok       mcp         postgres: dev host {hosts}, read-only session forced")
    root_s = getattr(args, "dir", None) or "."
    code, top = run(["git", "rev-parse", "--show-toplevel"], cwd=Path(root_s), timeout=5)
    if code == 0 and top.strip():
        root = Path(top.strip())
        for status, msg in doctor_project(root, eos_home):
            todo += status == "fix"
            print(f"  {status:<8} project     {msg}")
    print(f"  {'all good' if not todo and not bad else f'{todo + bad} thing(s) to fix: the command is after each ->'}")
    return 1 if bad else 0


def cmd_detect(args: argparse.Namespace) -> int:
    home = find_eos_home()
    if not home:
        eprint("needs the engineering-os repo")
        return 2
    _, stacks = load_home_packs(home)
    found, unsupported = detect_stacks(Path(args.dir), stacks)
    print(json.dumps({"stacks": found, "no_pack_yet": unsupported}, indent=2))
    return 0


def cmd_new_stack(args: argparse.Namespace) -> int:
    home = find_eos_home()
    if not home:
        eprint("needs the engineering-os repo")
        return 2
    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.id):
        eprint("id must be lowercase letters, digits and dashes")
        return 2
    dest = home / "packs/stacks" / args.id
    if dest.exists():
        eprint(f"{dest} already exists")
        return 2
    shutil.copytree(home / "packs/stacks/_template", dest)
    markers = json.dumps([m.strip() for m in (args.markers or "MARKER_FILE").split(",")])
    globs = json.dumps([g.strip() for g in (args.globs or "**/*.EXT").split(",")])
    for f in dest.iterdir():
        t = read(f).replace("STACK_ID", args.id).replace("STACK_TITLE", args.title or args.id)
        t = t.replace('markers: ["MARKER_FILE"]', f"markers: {markers}").replace(
            'globs: ["**/*.EXT"]', f"globs: {globs}"
        )
        write(f, t)
    print(f"created {dest}: fill STACK.md (official docs only), pre-commit.yaml and ci.yml, then run `eos budget`.")
    return 0


# ----------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="eos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "engineering-os: AI-assisted engineering, stack-agnostic.\n\n"
            "The five you need day to day:\n"
            "  eos next            the one next step (and `eos next --skip` to skip it)\n"
            "  eos verify          the right checks for this change, sized to its risk\n"
            "  eos lane            how risky this change is and what that means (trivial/standard/risky/one-way-door)\n"
            "  eos spike|hotfix    escape hatches: throwaway prototype, or an urgent production fix\n"
            "  eos stats           how much time eos itself costs you (hooks, prompts, checks)\n"
            "First time in a folder: `eos start`. Everything else below is setup or advanced."
        ),
    )
    ap.add_argument("--version", action="version", version=f"eos {eos_version(find_eos_home())}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")

    b = sub.add_parser("bootstrap", help="set up this machine (profile, skills, MCP, git)")
    b.add_argument("--tools", default=None, help="cursor,cline,claude,codex or 'all' (default cursor,cline)")
    b.add_argument("--home", help="alternate home directory (for testing)")
    b.add_argument("--global-hooks", action="store_true", help="point git core.hooksPath at eos git-hooks")
    b.add_argument("--install-clis", action="store_true", help="install CLIs with brew; elsewhere print commands")
    b.add_argument("--no-mcp", action="store_true", help="skip MCP config rendering")
    b.add_argument("--no-cline-install", action="store_true", help="don't install the Cline extension into Cursor")
    b.add_argument("--dry-run", action="store_true")
    b.set_defaults(fn=cmd_bootstrap)

    helps = {
        "init": "add eos to a project",
        "update": "refresh eos files in a project",
        "adopt": "existing project: scan, report, merge without clobbering, ratchet gates, improvement plan",
    }
    for name in ("init", "update", "adopt"):
        p = sub.add_parser(name, help=helps[name])
        p.add_argument("dir", nargs="?", default=".")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--force", action="store_true", help="overwrite files even if you edited them")
        p.add_argument("-v", "--verbose", action="store_true")
        p.add_argument("--no-ci", action="store_true")
        p.add_argument("--no-precommit", action="store_true")
        p.add_argument("--bmad", action="store_true", help="also install BMAD (version pinned in versions.toml)")
        p.add_argument("--strict", action="store_true", help="exit 1 when a conflict (.eos-new) was written")
        p.add_argument(
            "--profile",
            choices=["web-app", "api", "mobile", "data-ml", "internal-tool", "cli-library", "full"],
            help="project type: selects packs and gates (default: guessed from stacks; asked on a terminal)",
        )
        p.add_argument(
            "--answers",
            help="questionnaire answers, e.g. money=yes,personal_data=yes,llm=no,scale=medium,low_bandwidth=yes",
        )
        p.add_argument(
            "--reconfigure",
            action="store_true",
            help="set-up project: ask the questions again (current answers as defaults; with --profile/--answers:"
            " no questions), then refresh packs and files without touching yours",
        )
        p.add_argument("--interactive", action="store_true", help="ask the questionnaire even without a terminal")
        p.add_argument("-y", "--yes", action="store_true", help="never ask; use flags, saved answers and guesses")
        p.add_argument("--teach", choices=["on", "off"], help="teaching mode: agents explain decisions (default on)")
        if name in ("init", "adopt"):
            p.add_argument("--tools", help="default: tools chosen at bootstrap, else cursor,cline")
            p.add_argument("--stacks", default="auto", help="auto | none | id[:dir],id[:dir]")
            p.add_argument("--name", help="project name for AGENTS.md")
            p.add_argument("--pm", choices=sorted(PM_INFO), help="node package manager (default: detected)")
            p.add_argument("--python", help="interpreter the hooks call (default python3; python on Windows)")
            p.add_argument(
                "--mode", help="lifecycle: greenfield | brownfield | rewrite (refonte) | maintain (default: detected)"
            )
            p.add_argument("--topology", choices=TOPOLOGIES, help="repo shape (default: detected)")
        if name == "adopt":
            p.add_argument("--scan-only", action="store_true", help="print what was found; write nothing")
            p.add_argument("--report-only", action="store_true", help="refresh the reports; install nothing")
            p.add_argument("--no-baseline", action="store_true", help="skip running linters for the ratchet baseline")
            p.set_defaults(fn=cmd_adopt)
        elif name == "init":
            p.set_defaults(fn=lambda a: cmd_init(a, update=False))
        else:
            p.set_defaults(fn=lambda a: cmd_init(a, update=True))

    s = sub.add_parser("sync", help="regenerate adapters from .eos/packs")
    s.add_argument("dir", nargs="?", default=".")
    s.add_argument("--check", action="store_true", help="only report drift (exit 1)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_sync)

    c = sub.add_parser("check", help="project gate: budgets + drift + frontmatter")
    c.add_argument("dir", nargs="?", default=".")
    c.set_defaults(fn=cmd_check)

    bu = sub.add_parser("budget", help="token budget report")
    bu.add_argument("dir", nargs="?")
    bu.set_defaults(fn=cmd_budget)

    d = sub.add_parser("detect", help="show detected stacks")
    d.add_argument("dir", nargs="?", default=".")
    d.set_defaults(fn=cmd_detect)

    m = sub.add_parser("mcp", help="MCP profiles: list | status | use <profile|phase> (run <server>: used by clients)")
    m.add_argument("action", choices=["list", "status", "use", "run"])
    m.add_argument("profile", nargs="?")
    m.add_argument("--tools", help="only these tools (default: tools chosen at bootstrap)")
    m.add_argument("--home", help="alternate home directory (for testing)")
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(fn=cmd_mcp)
    mo = sub.add_parser("models", help="model routing by task; --check verifies ids live; --usage vs caps")
    mo.add_argument("task", nargs="?", help="e.g. plan, implement, review, debug-hard, bulk")
    mo.add_argument("--failures", type=int, default=0, help="failed attempts so far (escalates the tier)")
    mo.add_argument("--check", action="store_true", help="verify ids and show prices from the OpenRouter API")
    mo.add_argument("--usage", action="store_true", help="compare your OpenRouter key spend with budget caps")
    mo.set_defaults(fn=cmd_models)
    nw = sub.add_parser(
        "new", help='from a template: eos new adr|story|plan|migration "<title>", eos new service|module <name>, design'
    )
    nw.add_argument("kind", choices=["adr", "story", "plan", "design", "critique", "migration", "service", "module"])
    nw.add_argument("title", nargs="?")
    nw.add_argument("--dir", default=".")
    nw.add_argument("--owner", help="service/module owner, e.g. @you or @org/team")
    nw.add_argument("--dry-run", action="store_true")
    nw.set_defaults(fn=cmd_new)
    sc = sub.add_parser("scaffold", help="opt-in starter files: eos scaffold list")
    sc.add_argument("kind", choices=["list", *SCAFFOLDS])
    sc.add_argument("dir", nargs="?", default=".")
    sc.add_argument("--owner", help="CODEOWNERS owner, e.g. @you or @org/team")
    sc.add_argument("--spec", help="OpenAPI spec path for api-contract (default openapi.json)")
    sc.add_argument("--dry-run", action="store_true")
    sc.set_defaults(fn=cmd_scaffold)
    un = sub.add_parser("uninstall", help="remove eos-generated files (keeps your edits, memory and docs)")
    un.add_argument("dir", nargs="?", default=".")
    un.add_argument("--dry-run", action="store_true")
    un.add_argument("--force", action="store_true", help="also remove generated files you edited")
    un.set_defaults(fn=cmd_uninstall)
    do = sub.add_parser("doctor", help="check this machine (+ the project you are in); prints a fix for each problem")
    do.add_argument("dir", nargs="?", default=".")
    do.set_defaults(fn=cmd_doctor)

    tp = sub.add_parser("topology", help="repo shape: show detected (and why) | set <shape>")
    tp.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    tp.add_argument("value", nargs="?")
    tp.add_argument("--dir", default=".")
    tp.add_argument("--json", action="store_true")
    tp.set_defaults(fn=cmd_topology)
    md = sub.add_parser("mode", help="lifecycle mode: show detected (and why) | set <mode>")
    md.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    md.add_argument("value", nargs="?")
    md.add_argument("--dir", default=".")
    md.set_defaults(fn=cmd_mode)
    te = sub.add_parser("teach", help="teaching mode for agents: on (explain decisions) | off (terse)")
    te.add_argument("value", nargs="?", choices=["on", "off"])
    te.add_argument("--dir", default=".")
    te.set_defaults(fn=cmd_teach)
    ga = sub.add_parser("gates", help="strict (every file) | ratchet (only new violations block)")
    ga.add_argument("value", nargs="?", choices=["strict", "ratchet"])
    ga.add_argument("--dir", default=".")
    ga.set_defaults(fn=cmd_gates)

    for nm, hl in (
        ("status", "where the project is: mode, phase, artefacts, gates, git"),
        ("next", "the one next step, why, and the exact command or prompt"),
    ):
        q = sub.add_parser(nm, help=hl)
        q.add_argument("dir", nargs="?", default=".")
        q.add_argument("--json", action="store_true")
        if nm == "status":
            q.add_argument(
                "--strict", action="store_true", help="exit 1 while blockers exist or the phase is unfinished"
            )
            q.set_defaults(fn=cmd_status)
        else:
            q.add_argument("--brief", action="store_true", help="one line")
            q.add_argument("--skip", action="store_true", help="skip the suggested step (recorded; `--unskip` undoes)")
            q.add_argument("--unskip", action="store_true", help="bring back every skipped step")
            q.set_defaults(fn=cmd_next)
    la = sub.add_parser("lane", help="classify this change: trivial | standard | risky | one-way-door (+ spike/hotfix)")
    la.add_argument("dir", nargs="?", default=".")
    la.add_argument("--base", help="compare with this ref (default: merge-base with origin/main or main)")
    la.add_argument("--labels", help="comma list, e.g. PR labels; 'lane:<name>' overrides (logged)")
    la.add_argument("--json", action="store_true")
    la.add_argument("--ci", action="store_true", help="write the job summary; fail only for spike/* PRs")
    la.set_defaults(fn=cmd_lane)
    ve = sub.add_parser("verify", help="run the checks this change needs (changed files, related tests, full by risk)")
    ve.add_argument("dir", nargs="?", default=".")
    ve.add_argument("--base")
    ve.add_argument("--full", action="store_true", help="everything, whatever the lane")
    ve.add_argument("--dry-run", action="store_true", help="show what would run")
    ve.set_defaults(fn=cmd_verify)
    for kind, hl in (
        ("spike", "throwaway prototype branch: no tests/plans, never merged; `eos spike done` keeps the lesson"),
        ("hotfix", "urgent fix branch from main: minimal steps, review afterwards; `eos hotfix done` writes the note"),
    ):
        sp = sub.add_parser(kind, help=hl)
        sp.add_argument("name", help="short name, or 'done'")
        sp.add_argument("--dir", default=".")
        sp.add_argument("--dry-run", action="store_true")
        if kind == "hotfix":
            sp.add_argument("--no-fetch", action="store_true", help="offline: branch from the local main")
        sp.set_defaults(fn=cmd_spike_hotfix, kind=kind)
    sa = sub.add_parser("stats", help="what eos costs you: hook latency, approval prompts, checks, escapes, lead time")
    sa.add_argument("dir", nargs="?", default=".")
    sa.add_argument("--days", type=int, default=30)
    sa.add_argument("--json", action="store_true")
    sa.set_defaults(fn=cmd_stats)
    lb = sub.add_parser("library", help="deep reference library: list | lint | index | eval <tasks.json|dir>")
    lb.add_argument("action", choices=["list", "lint", "index", "eval"], nargs="?", default="list")
    lb.add_argument("target", nargs="?", default="tests/evals", help="eval: a tasks file or folder")
    lb.add_argument("--responses", help="eval: folder of real agent answers (<task>.base.md / <task>.lib.md)")
    lb.add_argument("--strict", action="store_true", help="lint: stale refs are errors, not warnings")
    lb.add_argument("--json", action="store_true")
    lb.add_argument("--and-vendor", action="store_true", help="lint: also run `eos vendor check`")
    lb.add_argument("--home", help=argparse.SUPPRESS)
    lb.set_defaults(fn=cmd_library)
    vd = sub.add_parser("vendor", help="third-party library files: list | add | update | review | check")
    vd.add_argument("action", choices=["list", "add", "update", "review", "check"], nargs="?", default="list")
    vd.add_argument("id", nargs="?", help="source id, e.g. anthropic-frontend-design")
    vd.add_argument("--repo", help="git URL")
    vd.add_argument("--ref", help="commit SHA or tag (resolved and pinned to the full SHA)")
    vd.add_argument("--path", action="append", help="file or folder in the repo (repeat)")
    vd.add_argument("--license", help="SPDX id, e.g. Apache-2.0 (must be on the allow-list)")
    vd.add_argument("--license-file", help="licence file in the repo (default LICENSE)")
    vd.add_argument("--accept-findings", help="injection-scan hits reviewed by a human: say why they are safe")
    vd.add_argument("--by", help="review: who reviewed the vendored files")
    vd.add_argument("--note", help="review: what was checked")
    vd.add_argument("--max-age-days", type=int, default=365)
    vd.add_argument("--kind", choices=VENDOR_KINDS, help="add: knowledge (text/data, default) or code (sandbox only)")
    vd.add_argument(
        "--hold", action="store_true", help="add/update: keep files with scan findings quarantined for review"
    )
    vd.add_argument("--strict", action="store_true", help="check: sources pending sign-off are errors (releases)")
    vd.add_argument("--home", help=argparse.SUPPRESS)
    vd.set_defaults(fn=cmd_vendor)
    cm = sub.add_parser("commit-msg", help=argparse.SUPPRESS)
    cm.add_argument("file")
    cm.set_defaults(fn=cmd_commit_msg)
    hr = sub.add_parser("hook-run", help=argparse.SUPPRESS)
    hr.add_argument("--cd", default=".")
    hr.add_argument("--id")
    hr.add_argument("--files-after", action="store_true", help="files follow the second --; made relative to --cd")
    hr.add_argument("--script", help="package.json script; uses '<script>:files' with the changed files if defined")
    hr.add_argument("--pm", help="package manager for --script")
    hr.add_argument("cmd", nargs=argparse.REMAINDER)
    hr.set_defaults(fn=cmd_hook_run)
    ex = sub.add_parser("explain", help="plain-language explanation of a principle or pack: eos explain ratchet")
    ex.add_argument("topic", nargs="?")
    ex.add_argument("--dir", default=".")
    ex.set_defaults(fn=cmd_explain)

    wsp = sub.add_parser("workspace", help="multi-repo workspace: init | add | status | sync | change")
    wsp.add_argument("action", choices=["init", "add", "status", "sync", "change"])
    wsp.add_argument("target", nargs="?", help="add: path or git URL; change: title")
    wsp.add_argument("--dir", default=".")
    wsp.add_argument("--name", help="workspace name (init)")
    wsp.add_argument("--role", help="repo role (add)")
    wsp.add_argument("--owner", help="repo owner (add)")
    wsp.add_argument("--repos", help="change: comma-separated repos touched (default all)")
    wsp.add_argument("--prs", action="store_true", help="status: list your open PRs per repo (needs gh)")
    wsp.add_argument("--force", action="store_true")
    wsp.add_argument("--dry-run", action="store_true")
    wsp.set_defaults(fn=cmd_workspace)

    stt = sub.add_parser("start", help="first time here? a guided setup that picks the right path for you")
    stt.add_argument("dir", nargs="?", default=".")
    stt.add_argument("--kind", choices=["greenfield", "brownfield", "rewrite", "refonte", "maintain", "workspace"])
    stt.add_argument("--name")
    stt.add_argument("--tools")
    stt.add_argument("--teach", choices=["on", "off"])
    stt.add_argument(
        "--profile", choices=["web-app", "api", "mobile", "data-ml", "internal-tool", "cli-library", "full"]
    )
    stt.add_argument("--migration", help="rewrite: name of the migration plan")
    stt.add_argument("--no-baseline", action="store_true", help="existing code: don't run linters for the ratchet")
    stt.add_argument("-y", "--yes", action="store_true", help="accept the suggestions (no questions)")
    stt.set_defaults(fn=cmd_start)

    ra = sub.add_parser("ratchet", help="brownfield gates: baseline old violations, fail only on new ones")
    ra.add_argument("action", nargs="?", choices=["check", "init", "add", "update"], default="check")
    ra.add_argument("name", nargs="?")
    ra.add_argument("cmd", nargs="?")
    ra.add_argument("--dir", default=".")
    ra.add_argument("--cwd", help="directory the command runs in (add)")
    ra.add_argument("--parser", default="lines", choices=["lines", "eslint-json", "count", "regex"])
    ra.add_argument("--pattern", help="regex with (?P<file>) and (?P<msg>) groups (add)")
    ra.add_argument("--tighten", action="store_true", help="lower baselines that improved (CI on main)")
    ra.add_argument("--strict", action="store_true", help="skipped checks or missing baselines fail")
    ra.add_argument("--dry-run", action="store_true")
    ra.set_defaults(fn=cmd_ratchet)

    n = sub.add_parser("new-stack", help="scaffold a stack pack from the template")
    n.add_argument("id")
    n.add_argument("--title")
    n.add_argument("--markers", help="comma list of marker file names, e.g. go.mod")
    n.add_argument("--globs", help="comma list of globs, e.g. **/*.go")
    n.set_defaults(fn=cmd_new_stack)

    t = sub.add_parser("test-integrity", help="flag weakened tests vs a base ref")
    t.add_argument("dir", nargs="?", default=".")
    t.add_argument("--base", default="origin/main")
    t.add_argument("--strict", action="store_true", help="suppression comments block in every lane")
    t.set_defaults(fn=cmd_test_integrity)

    dc = sub.add_parser("diff-coverage", help="coverage of changed lines (Cobertura XML or LCOV) vs a base ref")
    dc.add_argument("reports", nargs="*", help="coverage.xml / lcov.info (default: look in the usual places)")
    dc.add_argument("--dir", default=".")
    dc.add_argument("--base", help="base ref (default: merge-base with origin/main or main)")
    dc.add_argument("--min", type=float, help="minimum %% for changed lines (config testing.diff_coverage_min, 80)")
    dc.add_argument("--risky-min", type=float, help="minimum %% on money/auth/security paths (default 90)")
    dc.add_argument("--json", action="store_true")
    dc.set_defaults(fn=cmd_diff_coverage)

    q = sub.add_parser("quarantine", help="flaky-test quarantine with expiry: check | list | add")
    q.add_argument("action", choices=["check", "list", "add"])
    q.add_argument("id", nargs="?", help="test id to add (pytest node id or Playwright title)")
    q.add_argument("--dir", default=".")
    q.add_argument("--file", help=f"quarantine file (default {QUARANTINE_FILE})")
    q.add_argument("--reason")
    q.add_argument("--owner")
    q.add_argument("--issue", help="ticket URL or #number tracking the fix")
    q.add_argument("--days", type=int, help="days until expiry (capped by the maximum)")
    q.add_argument("--max-days", type=int, help="maximum quarantine length (config testing.quarantine_max_days, 14)")
    q.set_defaults(fn=cmd_quarantine)

    mp = sub.add_parser("mutation-plan", help="mutation-testing targets for risky changed code (mutmut / Stryker)")
    mp.add_argument("--dir", default=".")
    mp.add_argument("--base")
    mp.add_argument("--labels", help="PR labels, comma separated (lane:risky mutates every changed source file)")
    mp.add_argument("--all", action="store_true", help="every tracked file on a risky path (scheduled runs)")
    mp.add_argument("--json", action="store_true")
    mp.add_argument("--github-output", action="store_true", help="write targets to $GITHUB_OUTPUT")
    mp.set_defaults(fn=cmd_mutation_plan)

    ms = sub.add_parser("mutation-score", help="judge a mutmut cicd-stats or Stryker JSON report against a minimum")
    ms.add_argument("report")
    ms.add_argument("--dir", default=".")
    ms.add_argument("--min", type=float, help="minimum score %% (config testing.mutation_min, 60)")
    ms.set_defaults(fn=cmd_mutation_score)

    op = sub.add_parser(
        "ops", help="SLOs, burn-rate alerts, runbooks, feature flags: check | alerts | budget | runbook"
    )
    op.add_argument("action", choices=["check", "alerts", "budget", "runbook"])
    op.add_argument("name", nargs="?", help="runbook: alert or SLO name")
    op.add_argument("--dir", default=".")
    op.add_argument("--out", help="alerts: output file (config ops.generated_rules)")
    op.add_argument("--check", action="store_true", help="alerts: fail if the generated rules are out of date")
    op.set_defaults(fn=cmd_ops)

    i18 = sub.add_parser("i18n", help="translation catalogs: check (missing keys, ICU arguments, plurals, code keys)")
    i18.add_argument("action", choices=["check"])
    i18.add_argument("--dir", default=".")
    i18.set_defaults(fn=cmd_i18n)

    de = sub.add_parser(
        "design",
        help="design tokens (DTCG 2025.10), WCAG contrast of token pairs, generic-AI-look lint: check | contrast | ab",
    )
    de.add_argument("action", choices=["check", "contrast", "ab"])
    de.add_argument(
        "colors", nargs="*", help='contrast: "<foreground>" "<background>"; ab: init|score|report [<workspace>]'
    )
    de.add_argument("--allow-pending", action="store_true", help="ab init: evaluation copy of unsigned studio sources")
    de.add_argument("--shoot", action="store_true", help="ab score: take Playwright screenshots (needs npx)")
    de.add_argument("--seed", help="ab score: fixed blinding seed (tests only)")
    de.add_argument("--dir", default=".")
    de.add_argument("--strict", action="store_true", help="check: warnings fail too")
    de.add_argument("--json", action="store_true")
    de.set_defaults(fn=cmd_design)

    sto = sub.add_parser(
        "studio",
        help="opt-in design studio (vendored design catalogs; third-party code only in a no-network sandbox):"
        " status | on | off | fetch | find | run | palette",
    )
    sto.add_argument("action", choices=["status", "on", "off", "fetch", "find", "run", "palette"])
    sto.add_argument("--dir", default=".")
    sto.add_argument("rest", nargs=argparse.REMAINDER, help='find/palette: "<query>"; run: <tool> <verb> [args]')
    sto.set_defaults(fn=cmd_studio, source=None, n=8, name=None)

    mo = sub.add_parser(
        "mobile", help="mobile apps: check (MASVS manifest/app config) | size (app-size budget/ratchet) | rules"
    )
    mo.add_argument("action", choices=["check", "size", "rules"])
    mo.add_argument("--dir", default=".")
    mo.add_argument("--update", action="store_true", help="size: write the current sizes as the reviewed baseline")
    mo.add_argument("--strict", action="store_true", help="check: warnings fail too")
    mo.add_argument("--json", action="store_true")
    mo.set_defaults(fn=cmd_mobile)

    ll = sub.add_parser(
        "llm", help="LLM features: check (prompt files) | gate (eval results vs thresholds + baseline) | rules"
    )
    ll.add_argument("action", choices=["check", "gate", "rules"])
    ll.add_argument("results", nargs="?", help="gate: results JSON (default llm.results, evals/llm/results.json)")
    ll.add_argument("--dir", default=".")
    ll.add_argument("--config", help="gate: thresholds JSON (default llm.gate, evals/llm/gate.json)")
    ll.add_argument("--base", help="check: git ref for the version-bump rule (e.g. origin/main)")
    ll.add_argument("--update", action="store_true", help="gate: write a passing run as the reviewed baseline")
    ll.add_argument("--strict", action="store_true", help="check: warnings fail too")
    ll.add_argument("--json", action="store_true")
    ll.set_defaults(fn=cmd_llm)

    da = sub.add_parser(
        "data", help="data & ML: check (ODCS contracts, notebooks) | split (leakage across split CSVs) | rules"
    )
    da.add_argument("action", choices=["check", "split", "rules"])
    da.add_argument("--dir", default=".")
    da.add_argument("--base", help="check: git ref for breaking-change detection (e.g. origin/main)")
    da.add_argument("--train", help="split: training CSV")
    da.add_argument("--val", help="split: validation CSV (optional)")
    da.add_argument("--test", help="split: test CSV")
    da.add_argument("--id", help="split: entity id column (customer, card, device…) that must not cross splits")
    da.add_argument("--time", help="split: event-time column (ISO 8601); splits must not overlap in time")
    da.add_argument("--gap-days", type=float, default=0, help="split: minimum days between splits (label delay)")
    da.add_argument("--target", help="split: label column (enables the determines-the-target check)")
    da.add_argument("--strict", action="store_true", help="warnings fail too")
    da.add_argument("--json", action="store_true")
    da.set_defaults(fn=cmd_data)

    bs = sub.add_parser("bundle-size", help="gzip size of emitted client JS/CSS vs a reviewed baseline (ratchet)")
    bs.add_argument("--dir", default=".")
    bs.add_argument("--update", action="store_true", help="write the current sizes as the new baseline")
    bs.set_defaults(fn=cmd_bundle_size)

    g = sub.add_parser("guard", help="agent hook entry point (JSON on stdin)")
    g.add_argument("mode", choices=GUARD_MODES)
    g.set_defaults(fn=cmd_guard)
    return ap


GUARD_MODES = (
    "cursor-shell",
    "cursor-tool",
    "cursor-read",
    "cursor-mcp",
    "cursor-stop",
    "claude-tool",
    "claude-stop",
    "cline-tool",
)


def utf8_stdio() -> None:
    """Piped stdin/stdout on Windows (agent hooks, CI, `| more`) default to the ANSI code page (cp1252), so
    printing → or … raised UnicodeEncodeError and hook JSON with non-ASCII paths was mis-decoded. The same
    happens anywhere with PYTHONIOENCODING or a non-UTF-8 locale. Use UTF-8 for every non-UTF-8 stream."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", None) or "").lower().replace("_", "-")
        if enc in ("utf-8", "utf8"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    utf8_stdio()
    if len(argv) == 2 and argv[0] == "guard" and argv[1] in GUARD_MODES:
        # hot path: every agent tool call. Building the full 48-command parser cost ~15-20 ms of each call.
        return int(cmd_guard(argparse.Namespace(mode=argv[1], fn=cmd_guard)) or 0)
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
