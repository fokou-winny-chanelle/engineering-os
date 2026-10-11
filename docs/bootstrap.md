# Bootstrap notes per OS

`bootstrap.sh` / `bootstrap.ps1` only need **git** and **Python ≥ 3.10**. They install **uv** (official installer) and **pre-commit** (via `uv tool`) if those are missing, then run `eos bootstrap`. Everything else is reported by `eos doctor`; it is never force-installed. eos never runs `sudo`.

| Tool | macOS (Homebrew) | Debian/Ubuntu | Windows (winget) |
|---|---|---|---|
| git, Python | `xcode-select --install`, `brew install python` | `sudo apt-get install -y git python3` | `winget install Git.Git Python.Python.3.13` |
| uv | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `winget install astral-sh.uv` |
| Node 24 LTS + pnpm | `brew install node pnpm` | NodeSource or `fnm`/`nvm`; `corepack enable pnpm` | `winget install OpenJS.NodeJS.LTS`; `corepack enable pnpm` |
| pre-commit | `uv tool install pre-commit` | same | same |
| gitleaks | `brew install gitleaks` | release tarball from github.com/gitleaks/gitleaks/releases | `winget install Gitleaks.Gitleaks` |
| shellcheck, actionlint | `brew install shellcheck actionlint` | `sudo apt-get install -y shellcheck`; actionlint from its releases | `winget install koalaman.shellcheck` |
| gh | `brew install gh` | see cli.github.com | `winget install GitHub.cli` |

`--install-clis` automates the Homebrew row only. On other systems it prints these instructions. Check winget IDs with `winget search <name>` before you rely on them.

## Native Windows (PowerShell 5.1 or 7)

```powershell
git clone https://github.com/<you>/engineering-os "$HOME\engineering-os"
powershell -ExecutionPolicy Bypass -File "$HOME\engineering-os\bootstrap.ps1" --tools "cursor,cline"
```

- **What it does:** finds a real Python 3.10+ (`python` or `py -3`; the Microsoft Store alias stub doesn't count). Installs `uv` with the official installer, or with winget if you pass `-UseWinget`. Installs `pre-commit` at the pinned version with `uv tool install`. Runs `eos bootstrap`. Adds `%USERPROFILE%\.local\bin` to your **user** PATH (no admin rights; pass `-NoPath` to skip). Open a new terminal afterwards.
- **`eos` on Windows** is `%USERPROFILE%\.local\bin\eos.cmd`. It calls the absolute path of the Python that ran bootstrap, quoted, so profile paths with spaces (`C:\Users\Jane Doe`) work. It runs from cmd and PowerShell alike.
- **Comma lists:** quote them (`--tools "cursor,cline"`). The script also re-joins unquoted lists that PowerShell turned into arrays.
- **Output encoding:** eos switches its own stdin/stdout to UTF-8 on Windows, so piped output and hook JSON with non-ASCII paths work in Windows PowerShell 5.1 too.
- **MCP servers:** Postgres MCP needs `uv` and a local Postgres (Docker Desktop is fine: allow-listed hosts include `localhost` and `host.docker.internal`). Playwright MCP needs Node (`npx`) and Chrome.
- **Not yet covered on native Windows:** Cline hooks (Cline limitation), and the Flutter stack's pre-commit hooks, which call `bash` (Git Bash must be on PATH). The repo's Windows CI job runs the unit tests; the end-to-end selftest is POSIX only.

## Where things land
| Item | Linux/macOS | Windows |
|---|---|---|
| `eos` launcher | `~/.local/bin/eos` | `%USERPROFILE%\.local\bin\eos.cmd` |
| Secrets (outside git, owner-only) | `~/.config/engineering-os/secrets.env` | `%USERPROFILE%\.config\engineering-os\secrets.env` (restrict it with NTFS permissions) |
| Personal profile | `~/.cursor/rules/eos-profile.mdc`, `~/.agents/AGENTS.md` (Cline), `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md` | same, under `%USERPROFILE%` |
| Global skills | `~/.agents/skills`, `~/.cline/skills`, `~/.claude/skills` | same |
| Cursor MCP | `~/.cursor/mcp.json` (`${env:VAR}`) | same |
| Cline MCP | `~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` (macOS: `~/Library/Application Support/Cursor/...`) | `%APPDATA%\Cursor\User\globalStorage\...` |
| Codex MCP | managed block in `~/.codex/config.toml` | same |
| Claude Code MCP | run `~/.config/engineering-os/claude-mcp.sh` once | run the `claude mcp add` lines by hand |

## Caveats
- **GUI apps and env vars.** An editor started from the Dock or Start menu may not inherit your shell's variables. Launch it from a terminal, use `launchctl setenv` on macOS, set user environment variables on Windows, or use a secret manager wrapper (e.g. `op run`).
- **Cline hooks are macOS/Linux only** (Cline v3.36 docs). On Windows the guard covers Cursor and Claude Code, and the rules still apply to Cline.
- **Windows: prefer WSL 2 for daily work.** Clone repos inside the Linux filesystem (`~/code/...`, not `/mnt/c/...`): file watching and git are much faster there, and Cline hooks, the shell guard and pre-commit behave as on Linux. Open the folder with the editor's WSL remote. `eos doctor` flags a repo on `/mnt/c`. Native Windows is supported (see above); the end-to-end selftest is POSIX only, so report anything that breaks.
- **Python version.** eos needs Python 3.10+; `eos models` needs 3.11+ (it reads TOML).
- **Cursor user rules.** Cursor's *User Rules* live in its settings UI. `~/.cursor/rules/*.mdc` files are local to the machine and may not be read by every Cursor version. If the profile doesn't show up, paste `personal/PROFILE.user.md` (or the `PROFILE.md` template) into Settings → Rules.
- **Global git hooks** (`--global-hooks`) set `core.hooksPath`. Repos that use Husky set their own local hooksPath, which takes precedence; that's fine. To opt a single repo out: `git config eos.hooks false`.
