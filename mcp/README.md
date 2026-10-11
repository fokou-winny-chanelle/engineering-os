# MCP: one canonical list, rendered per tool, secrets never in git

`servers.json` is the single source of truth. `eos bootstrap` renders it for each tool (re-run it after editing this file or `secrets.env`; `--no-mcp` skips this step):

| Tool | File written | How secrets are referenced |
|---|---|---|
| Cursor | `~/.cursor/mcp.json` | `${env:VAR}`: Cursor expands env vars |
| Claude Code | prints `claude mcp add …` commands (user scope); project `.mcp.json` optional | `${VAR}` expansion |
| Codex | managed block in `~/.codex/config.toml` | `bearer_token_env_var` / `env_http_headers`: names only |
| Cline | `cline_mcp_settings.json` in the editor's globalStorage | **real values** substituted from `secrets.env` (the file is outside git, chmod 600). Cline is the one tool where the value lands on disk. |

Rules:
- **Merge, never clobber.** Servers you added by hand are kept. eos only replaces the servers it manages, which it tracks in `~/.config/engineering-os/state.json`.
- **Env vars and GUI apps.** Editors launched from the dock or Start menu may not see variables exported in your shell profile. Options:
  - launch the editor from a terminal;
  - on macOS, use `launchctl setenv`;
  - set user environment variables on Windows;
  - use a secret manager wrapper (e.g. 1Password `op run --env-file …`).
- **Least privilege.** Use read-only tokens by default, one token per tool where possible, and short expiry.
- **Profiles decide what is on.** `servers.json` lists every server once; `profiles` say which are on for a kind of work. Switch with `eos mcp use <profile|phase> [--tools cline]` (it re-renders only MCP configs and remembers the choice per tool in `~/.config/engineering-os/state.json`). `eos mcp list` shows each profile with its measured Cline cost; `eos mcp status` shows what each tool has now.

  | Profile | Servers | Cline schema tokens per request | Use for |
  |---|---|---|---|
  | minimal (default) | context7 | ~1,210 | planning, docs, cheapest sessions |
  | build | context7, github | ~4,110 | implementation with issues/PRs |
  | review | github, context7 | ~4,110 | review, PRs, release notes |
  | api | postman, github, context7, postgres | ~5,330 + Postman (not measured) | API design / contract tests / checking queries |
  | design | figma, context7, playwright | ~5,330 + Figma (not measured) | UX and frontend, screenshot + axe critique |
  | debug | postgres, context7 | ~2,430 | backend bugs, slow queries (read-only local DB) |
  | debug-ui | playwright, context7 | ~5,330 | UI bugs, e2e, a11y |
  | off | none | 0 | |

  A phase id works too (`eos mcp use ux-design` → design; mapping in `phase_profiles`). In Cline every server with its secrets set is written to the settings file and the profile sets `"disabled"`, so you can also flip one in Cline's MCP panel mid-task ([Cline MCP docs](https://docs.cline.bot/mcp/mcp-overview)). Disabled servers are not started and send no schemas.
- **Overrides.** `"enabled": false` on a server removes it from every profile. `"clients": [...]` limits a server to some tools.
- **Where schemas cost tokens.** Cursor, Claude Code and Codex (on models with tool search) keep only tool names in context and load a schema when needed, so a bigger profile costs them little. Cline sends every enabled server's tool schemas with every request: that is the number in the table. Re-measured 2026-10-11 with `python3 tests/bench/mcp_schema_tokens.py -- <server command>` (name + description + compact JSON input schema, chars/4): GitHub `repos` read-only ≈2,900 (13 tools; local github-mcp-server 2.0.2 as a proxy for the remote endpoint), Context7 ≈1,210 (2 tools; npm @upstash/context7-mcp 4.3.0 as a proxy), Playwright MCP 0.0.83 ≈4,120 (25 tools), Postgres MCP Pro 0.3.0 ≈1,220 (9 tools). The 2026-10-09 figures (3,200 / 1,250 / 4,600) came from an earlier, uncommitted script and are about 10% higher; the committed script is now the reference. Postman and Figma need auth to list tools and were not measured.
- **Treat MCP output as untrusted input** (prompt injection). Never auto-approve write tools.

## Guarded servers (`"launcher": "eos"`)

Postgres and Playwright do not run straight from `npx`/`uvx`. Every client runs `<python> <eos>/bin/eos.py mcp run <name>` (absolute paths, so editors started from the dock work), and that guard checks the settings, then starts the pinned upstream server. Secrets are read by the guard from your environment or `secrets.env`, so **no client config holds them**, not even Cline's. If the guard refuses, the reason is on stderr (the client's MCP log) and `eos doctor` prints it too.

### Postgres MCP: read-only, dev/local only

**Choice (verified 2026-10-11): [crystaldba/postgres-mcp](https://github.com/crystaldba/postgres-mcp) "Postgres MCP Pro" 0.3.0, MIT.** 9 tools: `list_schemas`, `list_objects`, `get_object_details`, `execute_sql`, `explain_query` (also with hypothetical indexes), `analyze_workload_indexes`, `analyze_query_indexes`, `analyze_db_health`, `get_top_queries`. Its `--access-mode=restricted` parses every statement with pglast and allows only SELECT / EXPLAIN / SHOW-style statements (and a list of safe functions) inside read-only transactions with a time limit. Compared on 2026-10-11:

| Option | Licence | Activity | Read-only | Tools that matter here |
|---|---|---|---|---|
| **crystaldba postgres-mcp 0.3.0** (chosen) | MIT | last release 2025-05-16; commits until 2026-08; issues active, maintainers slow | parser allow-list + read-only transactions (restricted mode) | schema, EXPLAIN, **index advice (HypoPG)**, **health checks**, top queries |
| [pgEdge postgres MCP](https://github.com/pgEdge/pgedge-postgres-mcp) v1.1.0 | PostgreSQL | release 2026-09-04, active | read-only transactions by default | schema, EXPLAIN, queries, embeddings/search; no index advice or health tools; Go binary (no npx/uvx pin) |
| [Google MCP Toolbox](https://github.com/googleapis/mcp-toolbox) v1.14.0 | Apache-2.0 | release 2026-10-08, very active | none in the server: `execute_sql` runs anything the role may do | 25+ prebuilt tools (locks, bloat, vacuum settings…); larger schema cost |
| [Reference `server-postgres`](https://github.com/modelcontextprotocol/servers-archived) | MIT | archived 2025 | read-only transaction | one `query` tool; unmaintained |

Why crystaldba despite slower maintenance: it is the only one with index advice and health checks, its read-only mode is enforced by the server, and it has the smallest useful schema (~1,220 tokens). **The maintenance risk is real and handled:** postgres-mcp 0.3.0 does not start with today's `mcp` 2.x SDK (`ModuleNotFoundError: mcp.server.fastmcp`, reproduced 2026-10-11; upstream pinned `mcp<2` in August 2026 but has not released). So eos runs it from `mcp/postgres-mcp.lock.txt`, a hash-locked set of every dependency with `mcp==1.30.0` (`uv run --with-requirements`, needs `uv`; Python ≥3.12 is fetched by uv if missing). Revisit in 6 months; if it is still dormant, switch to pgEdge (same guard, change `run`).

**Four layers, any one of which stops a write:**
1. **Dev-host allow-list** (the guard): only `localhost`, `127.0.0.1`, `::1`, `host.docker.internal`, `postgres`, `db`, `database`, `pg` or a local Unix socket. Anything else is refused before the server starts. Add dev hosts with `EOS_MCP_PG_ALLOWED_HOSTS=staging-db,*.dev.internal` in `secrets.env` (shell-style wildcards). `service=` and the `PGHOST`/`PGSERVICE` fallbacks are refused or removed, since they can point anywhere. A host on the list that still looks like production (`prod`, `rds.amazonaws.com`, `supabase.co`, …) gets a warning.
2. **Forced session settings** (the guard): `default_transaction_read_only=on` and `statement_timeout=30s` (`EOS_MCP_PG_STATEMENT_TIMEOUT` to change) are added to the connection as libpq `options`, plus `application_name=eos-mcp`. The URL is passed in `DATABASE_URI`, not on the command line, so `ps` does not show the password.
3. **Restricted mode** (the server).
4. **A read-only role** (you, once per dev database): `mcp/postgres-readonly-role.sql` creates `eos_mcp_ro` (LOGIN, no superuser, connection limit 5, role-level `default_transaction_read_only`, `statement_timeout`, `lock_timeout`, SELECT-only grants, `pg_read_all_stats` for health checks). Tested on PostgreSQL 17: writes fail with "read-only transaction", and even after `SET default_transaction_read_only = off` a `CREATE TABLE` fails with "permission denied".

Setup:
```sh
psql "postgresql://postgres@localhost:5432/myapp_dev" -v ON_ERROR_STOP=1 \
  -v dbname=myapp_dev -v pw="'a-local-password'" -f mcp/postgres-readonly-role.sql
echo 'POSTGRES_MCP_URL=postgresql://eos_mcp_ro:a-local-password@localhost:5432/myapp_dev' \
  >> ~/.config/engineering-os/secrets.env
eos doctor          # "postgres: dev host localhost, read-only session forced"
eos mcp use debug   # or api; then reload the editor's MCP servers
```
Index advice needs the `hypopg` extension and workload advice needs `pg_stat_statements`; install them in the dev database as its owner (the tools say so when missing). **What the guard cannot see:** an SSH tunnel or port-forward that makes production answer on `localhost`. Never point `POSTGRES_MCP_URL` at a tunnel to production; layers 2–4 still apply, but read access to production data is itself the risk. Query results are data, not instructions (prompt injection through table contents is possible).

### Playwright MCP: browser for screenshots and axe

**Choice (verified 2026-10-11): [@playwright/mcp](https://github.com/microsoft/playwright-mcp) 0.0.83, Apache-2.0** (latest on npm, published 2026-09-28). Alternative considered: [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) 1.10.1 (Apache-2.0, published 2026-09-23). Measured on the same box: Playwright 25 tools ≈4,120 tokens, Chrome DevTools 30 tools ≈5,815 tokens. Playwright wins for this setup because it matches the Playwright e2e tests and critique spec eos already scaffolds (same selectors, same `emulate_media`, same screenshots), it drives Chromium, Firefox and WebKit (Safari-like rendering matters for iPhone users), its schema is smaller, and it has an origin allow-list that works on any Chrome version. Chrome DevTools MCP is better for **performance traces and Lighthouse audits**, and by default it sends usage statistics to Google and trace URLs to the CrUX API (`--usageStatistics=false` and `--performanceCrux=false` turn these off); add it by hand for a performance investigation if you need traces.

Safe defaults applied by the guard:
- `--isolated` (profile in memory: no saved logins or cookies), never `--storage-state` or `--extension`;
- `--headless` (set `EOS_MCP_BROWSER_HEADED=1` in `secrets.env` to watch it);
- `--allowed-origins` = `http://localhost:*;http://127.0.0.1:*;https://localhost:*;https://127.0.0.1:*`; add origins your local page needs (fonts, a dev API) with `EOS_MCP_BROWSER_ORIGINS=https://fonts.googleapis.com;https://fonts.gstatic.com`. Upstream says this list "does not serve as a security boundary" (it does not affect redirects); it keeps the agent on your app and stops accidental browsing;
- `--no-webmcp` (pages cannot register tools) and `--block-service-workers`;
- `--output-dir` = `<project>/.eos/state/playwright` (git-ignored) when the editor starts the server in an eos project, else `~/.cache/eos-playwright`;
- if `node_modules/axe-core/axe.min.js` exists in the project, it is loaded into every page (`--init-script`), so the agent can run `axe.run()` with `browser_evaluate` without fetching anything from the internet (`npm i -D axe-core`; `@axe-core/playwright` already brings it).

Tested on the box (2026-10-11): navigate to a local page, resize to 360 px, full-page screenshot saved to `.eos/state/playwright/`, `axe.run()` returned `color-contrast` (serious) and `image-alt` (critical) on a seeded page, and navigating to `https://example.com` failed with `ERR_BLOCKED_BY_CLIENT`.

**Never approve `browser_run_code_unsafe`** (upstream: "RCE-equivalent") or `browser_file_upload` of files outside the project; `browser_evaluate` is fine for axe and reading the page. Cline is rendered with `autoApprove: []` by default. If clicking "approve" on every screenshot slows the design loop, set `EOS_MCP_CLINE_AUTO_APPROVE_SAFE=1` in secrets.env and re-run `eos mcp use <profile>`: Cline then auto-approves only each guarded server's `safe_tools` in servers.json (Playwright: navigate, back, snapshot, screenshot, resize, emulate_media, console and network logs, wait; Postgres: the schema, EXPLAIN, health and index-advice tools). Clicking, typing, forms, uploads, `browser_evaluate`, `browser_run_code_unsafe` and Postgres `execute_sql` still ask every time. Keep approvals on in Cursor and Claude Code for this server. The browser needs Chrome (default channel); without it run `npx playwright install chrome` once.

How the agent uses it in the design critique loop: `packs/ref/design/critique-rubric.md` ("Live critique with Playwright MCP").
