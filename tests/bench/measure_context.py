"""Always-on context per tool, counting every folder each tool really scans (skills in .claude/.agents/.cline...).

Usage: python3 tests/bench/measure_context.py <eos_repo> <workdir>   (INIT_ARGS="--profile api" etc.;
MEASURE_STUDIO=1 also installs the design studio first)
Tokens are estimated at 4 characters per token; real tokenisers vary by about 20%.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)
proj, home = work / "proj", work / "home"
(proj / "api/app/api/routes").mkdir(parents=True)
(proj / "api/tests").mkdir(parents=True)
(proj / "web/app").mkdir(parents=True)
(proj / "api/pyproject.toml").write_text('[project]\nname="api"\ndependencies=["fastapi"]\n')
(proj / "api/app/main.py").write_text("from fastapi import FastAPI\n")
(proj / "web/package.json").write_text('{"name":"web","dependencies":{"next":"16.0.0","react":"19.0.0"}}\n')
(proj / "web/tsconfig.json").write_text("{}\n")
(proj / "web/next.config.ts").write_text("export default {}\n")
subprocess.run(["git", "init", "-q", str(proj)], check=True)
env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
eos_py = str(repo / "bin/eos.py")
subprocess.run(
    [sys.executable, eos_py, "bootstrap", "--home", str(home), "--tools", "all", "--no-mcp"],
    env=env,
    capture_output=True,
    check=False,
)
subprocess.run(
    [sys.executable, eos_py, "init", str(proj), "--tools", "cursor,cline,claude,codex"]
    + os.environ.get("INIT_ARGS", "").split(),
    env=env,
    capture_output=True,
    check=True,
)
sys.path.insert(0, str(repo / "bin"))
import eos

if os.environ.get("MEASURE_STUDIO"):  # prove the opt-in design studio adds nothing always-on
    eos.studio_install(repo, proj, allow_pending=True)


def tok(s: str) -> int:
    return len(s) // 4


def rd(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def fm(text: str) -> dict:
    try:
        return eos.parse_frontmatter(text)[0]
    except (ValueError, IndexError, AttributeError):
        return {}


def skills(*dirs: Path) -> int:
    t = 0
    for d in dirs:
        for sk in sorted(d.glob("*/SKILL.md")):
            m = fm(rd(sk))
            if str(m.get("disable-model-invocation", "")).lower() == "true":
                continue
            t += tok(f"{m.get('name', '')}: {m.get('description', '')}")
    return t


def described_rules(d: Path) -> int:  # Cursor lists description-carrying, non-always rules to the agent
    return sum(tok(fm(rd(p)).get("description", "")) for p in d.glob("*.mdc") if fm(rd(p)).get("description"))


def path_rules(d: Path, ext: str, rel: str) -> int:
    t = 0
    for p in sorted(d.glob(f"*{ext}")):
        txt = rd(p)
        m = fm(txt)
        paths = re.findall(r'^  - "(.+)"$', txt.split("\n---\n", 1)[0], re.MULTILINE)
        globs = paths or (m.get("globs", "").split(",") if isinstance(m.get("globs"), str) else m.get("globs", []))
        if any(re.match(eos.glob_to_regex(g.strip()), rel) for g in globs if g.strip()):
            t += tok(txt)
    return t


agents = tok(rd(proj / "AGENTS.md"))
full = json.loads(rd(repo / "mcp/servers.json"))
PROFILE = os.environ.get("PROFILE") or full.get("default_profile")
# measured schema sizes live in servers.json (`tokens`, tests/bench/mcp_schema_tokens.py); null = unmeasured
MEAS = {n: s["tokens"] for n, s in full["servers"].items() if s.get("tokens") is not None}


def cline_mcp() -> tuple[int, list[str]]:
    on = list(eos.profile_servers(full, PROFILE, "cline"))
    return sum(MEAS.get(n, 0) for n in on), [n for n in on if n not in MEAS]


edit, tsx = "api/app/api/routes/users.py", "web/app/page.tsx"
cursor_dirs = [
    b / d for b in (proj, home) for d in (".agents/skills", ".cursor/skills", ".claude/skills", ".codex/skills")
]
cline_dirs = [proj / ".cline/skills", proj / ".clinerules/skills", proj / ".claude/skills", home / ".cline/skills"]
rows = {}
c_start = agents + tok(rd(home / ".cursor/rules/eos-profile.mdc")) + skills(*cursor_dirs)
c_start += described_rules(proj / ".cursor/rules")
rows["Cursor"] = (
    c_start,
    path_rules(proj / ".cursor/rules", ".mdc", edit),
    path_rules(proj / ".cursor/rules", ".mdc", tsx),
)
cm, unm = cline_mcp()
cl_start = agents + tok(rd(home / ".agents/AGENTS.md")) + skills(*cline_dirs)
rows["Cline"] = (cl_start, path_rules(proj / ".clinerules", ".md", edit), path_rules(proj / ".clinerules", ".md", tsx))
cc_start = agents + tok(rd(proj / "CLAUDE.md")) + tok(rd(home / ".claude/CLAUDE.md"))
cc_start += skills(proj / ".claude/skills", home / ".claude/skills")
rows["Claude Code"] = (
    cc_start,
    path_rules(proj / ".claude/rules", ".md", edit),
    path_rules(proj / ".claude/rules", ".md", tsx),
)
cx_start = agents + tok(rd(home / ".codex/AGENTS.md")) + skills(proj / ".agents/skills", home / ".agents/skills")
rows["Codex"] = (cx_start, 0, 0)
out = {"AGENTS.md": agents, "session_start": {k: v[0] for k, v in rows.items()}}
out["path_rules_route_py"] = {k: v[1] for k, v in rows.items()}
out["path_rules_page_tsx"] = {k: v[2] for k, v in rows.items()}
out["cline_mcp_schemas"] = {"profile": PROFILE, "tokens": cm, "unmeasured": unm}
print(json.dumps(out, indent=1))
