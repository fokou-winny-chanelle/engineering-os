# Changelog
All notable changes to engineering-os. Format: Keep a Changelog · Versioning: SemVer.

## [Unreleased]
### Changed: the repo shape of a new project is decided at the architecture step
- A greenfield project without code records its shape as `undecided` and shows "not decided yet (chosen at the
  architecture step)" in init/start output, `eos status` and AGENTS.md (a 2-line block telling agents not to create
  apps/, services/ or repos yet). Mechanics (packs, CI, checks) treat it as single. The plain summary adds "Structure
  ... is decided at the architecture step; nothing is locked now." `eos update` upgrades a `single` that was only
  guessed for an empty folder (never confirmed with `eos topology set` / `--topology`, which now record `topology_set`).
- Architecture phase: new exit criterion "the repo shape chosen" (`state: shape_decided`, met by `eos topology set` or
  a workspace file). `eos next` lists the commands for each choice (monorepo, single app, separate repos in a
  workspace), a "Not sure?" prompt for the agent, and with teaching on one plain sentence on the trade-off. Lifecycle
  steps may carry `options`, `tip` and `teach`. The overview prompt asks for a "Repo shape" recommendation.
- Ideation and discovery steps add a tip: use a strong model and attach inspiration images.
- `eos update` picks up the first stacks of a project set up before it had code ("first code found").
- New concept `eos explain repo-shape`.

### Changed: output a non-engineer can follow
- Teaching mode is **on** by default for new `eos init` / `eos adopt` / `eos start` (`--teach off` or `eos teach off`
  opts out; existing projects keep their setting). With it on, `eos next` and `eos status` add a 3-6 word plain
  meaning after jargon (mode, shape, gates, ratchet, ADR, PRD, SLO...), print the sentence to paste into Cline or
  Cursor on its own line, and split `a && b` commands into one line each (Windows PowerShell 5.1 has no `&&`).
- `eos adopt`, `eos init` and `eos start` end with four lines "In plain words": what was found (e.g. "A web app with a
  Next.js frontend and a NestJS backend; 138 commits, ... few tests"), what eos set up, the documents to read, and
  `eos next`. Technical lines gloss mode, shape, gates, ASVS level, scaffolds and MCP once. A ratchet check that
  could not run says why and what to do (ESLint failing without findings: often built files like dist/ or .next/
  are being linted, add them to the ignore list). A `.clinerules` file that blocks eos's Cline rules gets a fix line.
- `--reconfigure` on `eos update` / `eos adopt` / `eos init`: ask the questionnaire again with the current answers as
  defaults (or apply `--profile/--answers` without questions), recompute packs, and prune eos's unedited copies of
  packs no longer selected (edited ones are kept and listed). A plain re-run says the answers were kept and how to
  change them. `eos update` now accepts `--profile`, `--answers`, `--interactive`, `--yes` and `--teach`.

### Added: reproducible new-machine setup
- `eos bootstrap` installs the Cline extension (`saoudrizwan.claude-dev`) into Cursor through Cursor's CLI when Cline is
  one of the tools (the default): `cursor` on PATH, else the default install folder per OS. Idempotent (skipped when
  `--list-extensions` lists it), never fatal (prints the manual step), `--no-cline-install` to skip. With `--home`
  (tests) only that folder is searched, so the real Cursor is never touched.
- Bootstrap ends with "What only you can do now": empty key names in `secrets.env` (never values), Cline provider and
  recommended Plan/Act models with OpenRouter prices (as of Oct 2026), `eos doctor`, then `eos adopt` / `eos start`.
- `bootstrap.ps1` copies the keys `~\.cursor\mcp.json` references (`${env:NAME}`) from `secrets.env` into Windows
  user environment variables, so Cursor started from the Start menu sees them (`-NoEnv` skips it).
- `docs/NEW-MACHINE.md`: one page, blank PC to Cursor + Cline + eos, linked from README and GUIDE.

### Fixed: Windows and macOS portability (first public CI run)
- UTF-8 everywhere: every `open()`, `read_text`/`write_text` and text-mode subprocess call in `bin/eos.py`, the
  scaffolds and the tests passes `encoding="utf-8"` (written files also use `newline="\n"`, so output is the same
  on every OS). eos's own generated files were already UTF-8; the CI mojibake (`Â·`, `â‰¥`) and the `0xb7` decode
  errors came from tests reading and writing with Windows' default cp1252. eos's stdio switches to UTF-8 on any
  platform whose console or `PYTHONIOENCODING` is not UTF-8.
- Command lookup honours PATHEXT: `run()` resolves bare program names with `shutil.which`, so `npx`, `claude`, `npm`
  find their `.cmd` shims on Windows (also for hook commands and the pre-commit warm-up). Command strings are split
  without eating Windows backslashes (`split_cmd`), so `C:\...\python.exe lint.py` ratchets work.
- `eos doctor`: a tool that is found but does not run is no longer reported `ok ... not found`; missing optional
  tools show `-`.
- Paths in messages and comparisons are POSIX (`app/orders/page.tsx`, not `app\orders\page.tsx`); docker/podman
  mount sources use forward slashes; MCP launcher paths under `{EOS_HOME}` use native separators.
- Editor (Cursor, VS Code) User folders per OS: `~/Library/Application Support/<app>/User` on macOS,
  `%APPDATA%\<app>\User` on Windows (only for the real home, so `--home <dir>` never touches the real profile),
  `~/.config/<app>/User` on Linux.
- `scripts/db/alembic_squawk.py` scaffold resolves `ALEMBIC`/`SQUAWK` with `shutil.which` and keeps Windows paths;
  a missing command is a clear exit 2, not a traceback.
- With PyYAML installed, malformed YAML contracts are reported like the built-in parser does (no traceback).
- Windows shell steps (`ratchet` commands, `verify` full checks, the stop check) run as one verbatim
  `cmd /d /s /c "..."` line: in a list, Python escaped quotes as `\"`, which cmd.exe does not understand, so a
  quoted `"C:\Users\Jane Doe\...\python.exe" lint.py` failed. cmd.exe's "not recognized" (9009) counts as 127.
- bubblewrap mount sources are POSIX paths.
- Test fixture repos (`make_messy`, `make_workspace`) are built in Python (`tests/fixtures/make_fixtures.py`, same git
  trees as the old shell scripts), so the suite no longer needs a POSIX `sh` on PATH on Windows. Studio tests never
  probe a real Docker/Podman. `eos models` tests skip on Python 3.10 (it needs 3.11's tomllib, as documented).
- Tests: no background git gc/maintenance in temp repos (flaky `Directory not empty: .git`); per-OS editor folders;
  quoted interpreter paths. New `Portability` tests: a static check that no I/O relies on the default encoding,
  key commands run under `PYTHONIOENCODING=cp1252` with `-X warn_default_encoding -W error::EncodingWarning`,
  simulated-Windows path rendering, `split_cmd`, PATHEXT lookup, doctor statuses, editor folders per OS.

## [0.7.1] - 2026-10-11
Two guarded MCP servers (read-only local Postgres, localhost-only browser) and an honest efficiency evaluation of
the whole system, with the fixes it found. v0.7.1 is faster than v0.6.0 on every measured path; always-on context
unchanged (session start, default `web-app`: Cursor 1,884 / Cline 1,860 / Claude Code 1,907 / Codex 1,397).
Evaluation: docs/research/v0.7.1-efficiency-evaluation.md; plain-English summary:
docs/research/v0.7.1-summary-for-you.md.

### Public release (2026-10-11)
- MIT licence; `THIRD_PARTY_NOTICES.md` lists the vendored sources (CC BY-SA 4.0, Apache-2.0, MIT) and the CC BY 4.0
  adapted API refs. New README, `docs/REFERENCE.md`, CONTRIBUTING, SECURITY (private vulnerability reporting),
  CODE_OF_CONDUCT (Contributor Covenant 3.0), issue and PR templates.
- `personal/PROFILE.md` is now a generic template; your own profile goes in `personal/PROFILE.user.md` (git-ignored,
  used instead of the template). `personal/*.user.toml` is git-ignored too, as `models.user.toml` always claimed.
- Windows: `bootstrap.ps1` rewritten for Windows PowerShell 5.1 (ASCII only, 0 PSScriptAnalyzer 5.1 compatibility
  findings): paths with spaces, comma lists re-joined, real Python detection (`python` or `py -3`), uv via the official
  installer or `-UseWinget`, pinned pre-commit via uv, `~\.local\bin` added to the user PATH (`-NoPath` to skip).
  `eos.cmd` calls the absolute, quoted Python. eos uses UTF-8 for its stdio and subprocess output on Windows.
- Repo CI: new `lint` job (ruff, shellcheck, checksummed actionlint, budgets) and `secrets` job (gitleaks over the full
  history with `.gitleaks.toml`, which allow-lists one reviewed false positive: the hashes in `PROVENANCE.json`);
  a Windows PowerShell 5.1 bootstrap smoke test into a home path with a space. The Windows job is non-blocking
  until its first green run.

### Added
- **Postgres MCP** (crystaldba `postgres-mcp` 0.3.0, MIT; 9 tools, ~1,220 schema tokens measured) in the `api` and new
  `debug` profiles, never the default. Launched through `eos mcp run postgres`: secrets come from the environment or
  `secrets.env` (never a client config); hosts outside a local allow-list (localhost, 127.0.0.1, ::1, docker
  service names, `EOS_MCP_PG_ALLOWED_HOSTS`) are refused, `service=` is refused, production-looking hosts and
  superuser-looking users warn; every session gets `default_transaction_read_only=on` and `statement_timeout`
  (default 30s); upstream restricted mode on top. Dependencies hash-locked in `mcp/postgres-mcp.lock.txt` (the
  0.3.0 release breaks with today's `mcp` 2.x, so `mcp` is pinned to 1.30.0). `mcp/postgres-readonly-role.sql`
  creates the dedicated read-only role (role-level read-only default, timeouts, no CREATE, `pg_read_all_stats`).
  Tested end to end on PostgreSQL 17: writes, `SET`, `set_config` and `pg_sleep` refused; a long query cancelled.
- **Playwright MCP** (`@playwright/mcp@0.0.83`, Apache-2.0; 25 tools, ~4,120 tokens) now also in `design`, launched
  through `eos mcp run playwright`: isolated profile, headless, service workers blocked, origins limited to
  localhost/127.0.0.1 (+ `EOS_MCP_BROWSER_ORIGINS`), screenshots in `.eos/state/playwright`, axe-core injected when
  the project has it. Chrome DevTools MCP 1.10.1 was measured as the alternative (30 tools, ~5,815 tokens,
  telemetry on by default) and not chosen. The design critique rubric describes the live loop (resize, screenshot,
  axe).
- New `debug` MCP profile (Postgres + Context7, ~2,430 Cline tokens); `performance-scale` phase maps to it.
- `EOS_MCP_CLINE_AUTO_APPROVE_SAFE=1` (opt-in): Cline auto-approves only the read-only tools of the guarded servers;
  clicks, typing, `browser_evaluate`, `browser_run_code_unsafe` and `execute_sql` still ask.
- `eos doctor` checks `uv`/`npx` and the Postgres guard; `tests/bench/mcp_schema_tokens.py`, `tests/bench/bench_lanes.py`,
  `tests/bench/results-v0.7.1.json`.

### Changed
- MCP schema token figures re-measured with the committed script (GitHub ~2,900, Context7 ~1,210); earlier figures
  could not be reproduced and were ~10% high.
- **Speed:** projects get a 13-line `.eos/bin/eos.py` stub that imports `eos_impl.py`, so Python caches the
  bytecode; the guard hook skips building the CLI parser; regular expressions compile on first use. Measured
  (v0.7.0 → v0.7.1): guard 54 → 40 ms, `eos lane`/`next`/`check` ~190–200 → ~60–65 ms, stop check 0.50 → 0.34 s.
- **Lanes:** eos-generated files byte-identical to what eos wrote no longer count as sensitive or large, so
  adoption and `eos update` PRs list only the gate configs and the manifest for review (real repo: 33+ files → 5).

## [0.7.0] - 2026-10-11
The deep knowledge library, complete: 134 expert references across 12 areas (architecture, security, data, API,
testing, operations, frontend, design, mobile, LLM applications, analytics, ML), read only when an agent does that
work, with the practices turned into `eos` gates, scaffolds and Semgrep rules wherever a machine can check them.
189 eval tasks: context coverage 41% with packs alone, 100% with the refs they point to (a proxy; see
docs/LIBRARY-STATUS.md). Always-on context unchanged across all eleven stages. Eight vendored sources remain
quarantined pending human sign-off; the consolidated human review checklist is in docs/LIBRARY-STATUS.md §4.
Blueprint section 30 describes the library. Stage notes follow, newest first.

### Release wrap-up (2026-10-11)
- `docs/LIBRARY-STATUS.md`: every area with ref counts, tokens, packs that point to it, eval coverage and the checks
  it enforces; one prioritised human review checklist (security and money code, legal items, the eight
  `eos vendor review` commands, thresholds to confirm, the design A/B test).
- Blueprint section 30 (the deep knowledge library); PDFs regenerated.
- Library lint test pins its "today" to the newest `verified:` date in the real library, so freshly verified refs
  no longer read as "in the future" in the test fixture.

Stage 1 of the deep knowledge library: agents keep short rules always on and read expert references only when doing
that work. Always-on context did not grow (session start, default `web-app`: Cursor 1,884 / Cline 1,860 / Claude
Code 1,907 / Codex 1,397 tokens, same as before the library). Design: docs/LIBRARY.md. Research:
docs/research/v0.7-native-capabilities.md and docs/research/v0.7-external-sources.md.

### Added (stage 11: data engineering and ML, 2026-10-11)
- **Analytics area, 7 refs, and ML area, 5 refs (~23k tokens, none always-on; pointers from the `data-ml` pack):**
  analytics architecture (OLTP vs OLAP separation, batch ELT vs CDC with Debezium, DuckDB and Postgres-first with
  pg_duckdb for small teams, DuckLake/Iceberg, when to adopt a cloud warehouse, cost controls without prices);
  dbt (v1 vs v2 engine and adapter support, layers, generic and unit tests, model contracts and per-platform
  constraint enforcement, incremental models, Slim CI); pipelines and orchestration (idempotent tasks, partitions,
  backfills in Airflow and Dagster, Prefect caching, late data); data quality and contracts (dbt tests, Great
  Expectations, Soda under ELv2, pandera, ODCS v3.2.0, breaking-change rules, quarantine); product events (tracking
  plan, naming, server vs client, identity, consent with CNIL sheet 16 and Cameroon Law 2024/017 s.9); metrics
  layer and dashboards; privacy and anonymisation (WP216 tests, re-identification evidence, k-anonymity limits,
  differential privacy basics with NIST SP 800-226 and OpenDP); framing, splits and leakage (Rules of ML,
  scikit-learn pitfalls, group and time splits); experiments and reproducibility (MLflow aliases, DVC, lakeFS under
  BSL 1.1, Feast, model cards, datasheets); serving and monitoring (batch vs online, shadow and canary, Evidently
  drift defaults, delayed labels, retraining gates); fintech risk (fraud validation with label delay, fairness
  incompatibility results, SHAP caveats, Cameroon s.44, EU AI Act Annex III with Digital Omnibus dates, CJEU
  SCHUFA, Regulation B, CFPB Circular 2022-03 withdrawn); notebooks to production (nbstripout, Jupytext, nbQA,
  papermill). 89 of 90 links answered 200 on 2026-10-11 (EUR-Lex serves a bot challenge; dates cross-checked on
  the Council and OEIL pages). Research: `docs/research/v0.7-data-ml-sources.md`. No third-party text vendored.
- **`eos data check`** (in-process; part of `eos check` and verify): ODCS data contracts (DAT001-DAT008:
  parseable, fundamentals, semver version, typed properties, personal-data properties classified, breaking change
  vs `--base` needs a major bump, unique ids, owning team) and tracked notebooks (NB000-NB004: valid JSON, no
  outputs, no execution counts, no secrets, size). PyYAML when installed, else a built-in YAML subset parser.
  Exceptions need a written reason (`data.allow`). `*.odcs.*` files count as public contracts in lane
  classification.
- **`eos data split`**: leakage checks across exported train/validation/test CSVs: shared entity ids, identical
  rows, time order and minimum gap, a column that alone determines the label, outcome-like column names; prints
  row counts, target rate and date range per split.
- **`eos scaffold analytics`**: dbt-core 1.12.5 + dbt-duckdb 1.11.0 project (synthetic XAF seeds, staging and
  marts, 17 data tests, a unit test, an enforced contract, a money reconciliation test, telemetry off), an ODCS
  v3.2.0 contract (validates against the official JSON schema), a CI workflow (SHA-pinned, offline dbt build,
  contract check vs the PR base) and 4 Semgrep rules against personal data in analytics events (Python, JS/TS).
- **`eos scaffold ml`**: split and leakage checklist (with the nbstripout pre-commit hook), model card and
  datasheet templates.
- Tests: 11 gate unit tests, 4 tool-contract tests (real dbt build incl. a contract failure, PyYAML parity,
  Semgrep-clean, actionlint), Semgrep fixtures, a selftest section, `tests/evals/analytics.json` (14 tasks) and
  `tests/evals/ml.json` (13 tasks), both 100% coverage with refs.

### Added (stage 10: LLM applications, 2026-10-11)
- **LLM application area, 11 refs (~20k tokens, none always-on):** when to use an LLM vs deterministic code and
  how to choose and route models by measured cost, latency and quality (official model pages only, no prices);
  prompts as versioned code, structured outputs per provider, few-shot; tool and function design and MCP servers
  for your product (2026-07-28 spec: authorization, no token passthrough, `Origin` checks); RAG done properly
  (structure-based chunking, contextual retrieval, hybrid search with RRF, pgvector limits vs dedicated vector
  databases, reranking, citations, freshness, per-tenant filters, retrieval vs answer metrics); workflows vs
  agents, orchestration patterns, memory, human approval, guardrails and hard stop conditions; evals (offline
  datasets, code graders first, LLM-as-judge biases, CI regression gates, online monitoring; OpenAI's hosted
  Evals platform retiring on 30 Nov 2026); observability with the OpenTelemetry GenAI conventions (Development
  status; current span, metric and prompt attributes; content capture opt-in); reliability and cost (explicit
  timeouts, retries with Retry-After, fallbacks, streaming errors, prompt caching, batch/flex tiers, spend
  limits, OWASP LLM10); privacy and data residency (OpenAI, Anthropic and Gemini training, retention, ZDR and
  regions; Cameroon Law 2024/017 sections quoted; PII redaction); multilingual FR/EN, local languages and Pidgin
  (IrokoBench gap, per-language evals, Whisper and MMS with its non-commercial licence), WhatsApp AI-provider
  rules and SMS/USSD fallbacks without an LLM in the session; frameworks landscape (AI SDK, LangGraph,
  LlamaIndex, Pydantic AI, OpenAI Agents SDK, Google ADK, Mastra; when to use none). Security cross-links
  `security/llm-agent-security`. All 78 unique links answered 200 on 2026-10-11. Research:
  `docs/research/v0.7-llm-sources.md`. No third-party text vendored.
- **`eos llm check`** (in-process): prompt files (`*.prompt.md`, `.md` under `prompts/`) need frontmatter with
  id, version, model, owner, evals and max_output_tokens (LLM001-LLM005), declared template inputs (LLM006),
  untrusted inputs inside delimiting tags (LLM007), no secrets (LLM008), unique ids (LLM009) and a version bump
  whenever the prompt or its settings change against `--base` (LLM010); floating `-latest` aliases warn
  (LLM011). Exceptions need a written reason (`llm.allow`). Part of `eos check`.
- **`eos llm gate`**: eval regression gate over a results file: minimum pass rate, per-tag minimums, maximum
  drop against a committed baseline, minimum case count, duplicate ids, vanished cases. `--update` will not
  record a baseline that fails the thresholds.
- **`eos scaffold llm-evals`**: a versioned sample prompt, a FR/EN JSONL dataset with safety and
  prompt-injection cases, a stdlib eval runner (code graders, `--fake` for keyless CI, call cap, explicit
  timeout and retries), `gate.json`, a CI workflow (prompt lint on every PR; evals only on same-repo PRs, nightly
  and manual runs so forks never see keys; SHA-pinned actions; outputs not uploaded unless asked) and 8 Semgrep
  rules (LLM output into eval/exec/shell/SQL in Python and JS, provider keys in public client env,
  `dangerouslyAllowBrowser`, missing output-token caps, clients without an explicit timeout) with fixtures.
- **`eos scaffold llm-otel`**: GenAI OpenTelemetry helpers for Python (spans for LLM calls, tools and agents,
  token usage metrics, opt-in content capture, cost estimate from a price table you fill in) with a test, and a
  TypeScript equivalent.
- `tests/evals/llm.json` (20 tasks): pack alone 44% coverage, pack + refs 100%. `versions.toml` gained
  openai-python, `@opentelemetry/api` and promptfoo.

### Changed (stage 10)
- `agent-security` pack points to the LLM refs and the new checks (1,192 tokens, under the 1,200 cap);
  `data-ml` and `operations` packs link `llm/rag`, `llm/evals-in-production` and `llm/observability-otel`.
  Always-on context unchanged (session start Cursor 1,884 / Cline 1,860 / Claude Code 1,907 / Codex 1,397).
- Prompt files are no longer classified as trivial Markdown in `eos verify`; standard lanes check changed
  prompts, risky lanes check all prompts and run the gate when results are newer than the change.
- `eos library eval` rejects rubrics whose `any` is not a list of strings.

### Added (stage 9: mobile, 2026-10-10)
- **Mobile area, 12 refs (~24k tokens, none always-on):** choosing an approach (Expo SDK 57 / React Native 0.86
  with SDK 58 in beta, New Architecture only since SDK 55; Flutter 3.47 / Dart 3.13 with Impeller and its OpenGL
  fallback; when Swift/Kotlin or Kotlin Multiplatform is warranted); Expo and React Native (Expo Router,
  `Stack.Protected`, CNG, EAS Build/Update, runtime versions, rollouts, signed updates); Flutter (state options,
  go_router, obfuscation, app size); architecture, state and navigation; offline-first and sync (expo-sqlite,
  op-sqlite, WatermelonDB, Drift, sqflite, Isar status: upstream stalled, community fork; PowerSync; outbox,
  idempotency keys, conflict rules, background limits on Tecno); networking on 2G/3G (timeouts read from
  OkHttp/Dio/URLSession sources, jittered retries for idempotent calls only, request coalescing, gzip, Data Saver
  and Low Data Mode); performance on low-end Android (startup, Baseline Profiles, lists, JS/UI threads, memory,
  size budgets, Android vitals thresholds); security with OWASP MASVS v2.1 / MASTG (storage, pinning trade-offs,
  exported components, deep-link hijacking, secrets never in the bundle, obfuscation, rooted/jailbroken-device
  detection, Play Integrity and App Attest); auth and payments (code + PKCE in the system browser, biometrics bound
  to keys, passkeys, MoMo/Orange Money with server confirmation and USSD fallback, store payment rules); push
  (FCM/APNs delivery limits, TTL, collapse, Android 13 permission); release and CI (Play App Signing, versionCode,
  tracks, 12 testers for 14 days, target API 36, staged and phased rollouts, TestFlight, review guidelines, EAS
  Workflows, fastlane match); crash reporting, analytics with privacy, TalkBack/VoiceOver, font scaling, FR/EN.
  Cameroon market facts from StatCounter (Sept 2026: Android about 83% of mobile; Tecno, Infinix and itel, all
  Transsion brands, about 36% of devices; Android 9 and older about 10%), labelled as indicative.
  `testing/mobile-qa` gained tool versions (Maestro 2.11.0, Detox's tested RN range, Patrol) and low-end device
  testing. 122 unique source links answered 200 on 2026-10-10. Research: `docs/research/v0.7-mobile-sources.md`.
  No third-party text vendored.
- **`eos mobile check`** (in-process): Android manifests, network security config, iOS ATS, Expo app config and
  tracked `.env*` files. MOB001 backup on, MOB002 cleartext, MOB003 debuggable, MOB004 exported component without
  a permission, MOB005 intent-filter without `android:exported`, MOB006 ATS arbitrary loads, MOB007 secret-looking
  names behind `EXPO_PUBLIC_`; warnings MOB008 expo-updates without runtimeVersion, MOB009 unverified deep link,
  MOB000 unparsable file. Exceptions need a written reason in `.eos/config.json` (`mobile.allow`). Part of
  `eos check`.
- **`eos mobile size`**: ratchet on .aab/.apk/.ipa size (default 5% and at least 100 KB) plus optional budgets,
  with a breakdown by ABI, dex and assets; `--update` records the baseline.
- **`eos scaffold mobile`**: 14 MASVS-based Semgrep rules for TS/React Native, Dart, Kotlin and Swift (tokens in
  AsyncStorage/SharedPreferences/UserDefaults, secrets in public env, cleartext URLs, deep link to a sink,
  trust-all TLS, world-readable files, WebView file access and any-origin), with fixtures; Maestro smoke and
  offline-sync flows; an emulator E2E workflow (nightly, manual or `e2e` label) with SHA-pinned
  `actions/setup-java` v6.0.1 and `reactivecircus/android-emulator-runner` v2.38.0 and a checksum-verified Maestro
  download; a low-end performance budget doc.
- `tests/evals/mobile.json` (20 tasks): pack alone 53% coverage, pack + refs 100%.

### Changed (stage 9)
- `eos verify`: standard lanes run the mobile config check only when mobile config files changed; risky,
  one-way-door and `--full` also run the size ratchet when a built package newer than the change exists.
- `src/main/AndroidManifest.xml` and `res/xml/network_security_config.xml` are risky paths (human review).
- Stack ground truth refreshed: Expo SDK 57 / RN 0.86, Flutter 3.47 / Dart 3.13.
- `eos library eval` rejects a task whose `refs` is not a list of existing refs.

### Measured (stage 9)
- Always-on tokens unchanged: session start Cursor 1,884 / Cline 1,860 / Claude Code 1,907 / Codex 1,397; route
  `.py` 2,864 / 2,899 / 2,899; page `.tsx` 2,240 / 2,261 / 2,261. Mobile phase pack 1,005 tokens (rule slice 504).

### Added (design studio, 2026-10-10)
- **Opt-in design studio (`eos studio status|on|off|fetch|find|run|palette`)** for impeccable and
  ui-ux-pro-max (plus Emil Kowalski's review-animations, optional). Knowledge and code are separated:
  four vendored sources (`impeccable-knowledge`, `ui-ux-pro-max-knowledge`, `ui-ux-pro-max-scripts` of kind
  `code`, `emil-review-animations`), all **pending human sign-off**; `eos studio on` refuses until a human
  signs off. impeccable's `SKILL.md` (persona and launcher instructions), its iOS/Android files (third-party
  derived) and ui-ux-pro-max's npm CLI (GitHub downloads, child processes) are not imported.
- **Sandbox for third-party code:** Docker/Podman (`--network none --read-only --cap-drop ALL`, image pinned by
  digest) or bubblewrap (`--unshare-all --clearenv`); project read-only, writes only to `.eos/studio/out/`, no
  secrets in the environment; verb, flag and path allow-lists. No sandbox → knowledge-only mode
  (`eos studio find`). The impeccable engine (v0.1.14) is fetched to a cache and used only if its sha256 matches
  both our pin and the upstream sidecar, re-checked on every run; never committed or put on PATH.
- **One design authority:** precedence (direction.md > tokens > `eos design check` > our refs > studio
  suggestions) in the design-direction pack (now 1,169 tokens) and the studio README; `eos studio palette`
  turns a ui-ux-pro-max palette into a DTCG draft and runs our contrast check and violet/default-font rules.
- **A/B harness `eos design ab init|score|report`:** two identical arms (baseline vs studio), three specs (SME
  cash dashboard, ENEO bill payment by mobile money, njangi landing page), blinded X/Y critique sheets, a
  Playwright screenshot script, `eos design check` per screen, and a written decision rule (keep only if B
  beats A by ≥ 2/24 on average, wins ≥ 2 of 3 screens, adds no gate-row zero and no extra check errors).
  Not run here (no agent on the box); static evaluation in `tests/bench/studio_static_eval.py`.
- `eos vendor add --kind knowledge|code`; CSV/TSV injection scanning; dot-folder renaming on import.
- `MEASURE_STUDIO=1` option for `tests/bench/measure_context.py`.

### Changed (design studio)
- `eos design check` now flags purple/indigo/violet gradients written as raw CSS (literal stops in OKLCH hue
  270–330), not only Tailwind classes.

### Measured (design studio)
- Always-on tokens unchanged with the studio installed: session start Cursor 1,884 / Cline 1,860 / Claude Code
  1,907 / Codex 1,397; route `.py` 2,864 / 2,899 / 2,899; page `.tsx` 2,240 / 2,261 / 2,261.
- Static: 189 of 192 ui-ux-pro-max palettes use a stock Tailwind v3 hex as a key colour, 45 a violet/indigo
  one; all 1,344 declared on-pairs pass 4.5:1; 16 of 74 font pairings use a default family.

### Added (stage 8: design / UX, 2026-10-10)
- **Design area, 12 refs (~22.1k tokens, none always-on):** direction process (attributes, audience, mood,
  references and anti-references, the one bold thing); the generic "AI look" with each tell sourced (Anthropic's
  frontend-design skill, shadcn/Tailwind defaults, Next.js/Geist fonts); typography (scale, pairing, 45–90
  characters, WCAG 1.4.12, variable fonts, French spacing with U+202F, accented capitals, Latin Extended for
  Cameroonian names, next/font); colour (OKLCH ramps, semantic tiers, on-pairs, WCAG table vs advisory APCA, dark
  mode); layout and hierarchy (4 px scale, squint test, size classes, reflow); motion, icons, illustration and
  imagery (purpose, NN/g durations, reduced motion in CSS/Tailwind/Motion/RN, labelled icons, alt text); data
  visualisation (chart by task, palette types, XAF with zero decimals); forms, states and microcopy (GOV.UK error
  rules, waiting thresholds, empty/offline states, bilingual FR/EN tone); IA, navigation and HIG vs Material 3
  (tabs, back, targets, size classes, predictive back); tokens pipeline (Figma variables → DTCG 2025.10 → Style
  Dictionary 5 → CSS/Tailwind/Flutter/RN, Figma MCP, the Variables API seat requirement); critique rubric and
  small-team usability testing (5-user rounds, heuristic review); Cameroon context (DataReportal 2025, World Bank
  literacy 2018, GSMA usage gap, NN/g lower-literacy findings, Grameen mobile-money research). 83 unique source
  links answered 200 on 2026-10-10 (canada.ca timed out from curl on the final pass and was confirmed live by a
  separate fetch). Research and decisions: `docs/research/v0.7-design-sources.md`.
- **Imports (quarantined, pending human sign-off; not self-approved):** `anthropic-frontend-design`
  (anthropics/skills @ `dbd4588f`, Apache-2.0, LICENSE.txt copied, scan clean) and
  `vercel-web-interface-guidelines` (vercel-labs/web-interface-guidelines @ `434b7f91`, MIT, `command.md` only).
  Evaluated and rejected: pbakaus/impeccable (downloads a launcher binary, ~260 scripts), ui-ux-pro-max-skill
  (scripts and data files), taste-skill and huashu-design (too large for the budget; huashu also runs scripts).
  emilkowalski/skills: three skills trip the injection scan; `review-animations` is clean and left for a human to
  choose.
- **New gate `eos design check [--strict] [--json]` (stdlib only):** DTCG 2025.10 validation (names, `$type`
  inheritance, aliases across files with cycles and `$ref` pointers, 14 colour spaces with ranges, hex fallback
  mismatch, units on dimension/duration, fontWeight, cubicBezier, composite border/shadow/transition/typography,
  legacy string forms as warnings); WCAG 2 contrast for token pairs (`X`/`X-foreground`, `on-X`, configured
  pairs) and CSS theme variables per block (`:root`, `.dark`, `@media` dark), floor-truncated so 4.47 never shows
  as 4.5; the generic-look lint (raw colours outside tokens, Tailwind arbitrary colours, purple/indigo gradients,
  unchanged shadcn theme, emoji in UI code, default-only fonts, heavy stock palette, motion without reduced
  motion). `eos design contrast FG BG` for one pair. Lint findings are warnings unless `design.raw_colors` /
  `design.generic` are set to "error"; schema and contrast failures are errors. `eos check` includes it when
  design files exist.
- **Lanes:** trivial and spike unchanged; standard runs the design check in-process only when UI or token files
  changed (lint on the changed files); risky, one-way-door and `verify --full` lint the whole repo.
- **Scaffold `design-tokens`:** DTCG light and dark token sets (75 tokens, every pair ≥ 6.27:1), a self-running
  Style Dictionary build (`design/build-tokens.mjs`: CSS `@theme`, `.dark`, JS, Flutter `AppTokens` with custom
  transforms for durations, cubic-bezier, Dart px and fonts, gaps observed in 5.6.1), and a Playwright critique
  spec (phone 360 and desktop 1280, light and dark, reduced motion). `style-dictionary` pinned in versions.toml.
  `eos new critique "<screen>"` writes a dated 12-row rubric sheet (ship rule: no 0 on colour, states,
  interaction, accessibility; total ≥ 18/24; two rounds; human approval).
- **Library:** 20 eval tasks in `tests/evals/design.json` (context coverage 48% pack only → 100% with refs; a
  proxy, same author); bench key `design_stage8`. Pointers added to design-direction (1,184 tokens), ux-design
  (855), mobile (944) and frontend (1,114). ux-design no longer states an unsourced "about 20% longer" for French.
  Always-on context unchanged (session start, route_py, page_tsx).
- **Tests:** `DesignGateTests` (9), `DesignToolContractTests` (Style Dictionary build, with `EOS_TEST_TOOLS=1`),
  selftest section "design tokens and gates (stage 8)".

### Added (stage 7: frontend & web performance, 2026-10-10)
- **Frontend area, 12 refs (~22.6k tokens, none always-on), checked against Next.js 16.4 docs:** rendering and
  data (Server vs Client Components, Cache Components and `use cache`/`cacheLife`/`cacheTag`, fetch uncached by
  default, streaming commits a 200 so a late `notFound()` only adds noindex, SSG/ISR/PPR/CSR per use case, static
  export limits); Server Actions (public endpoints: auth, authorisation and schema validation inside each),
  Route Handlers, `proxy.ts` (not an authorisation layer; CVE-2025-29927); state and forms (TanStack Query for
  server state, URL state with nuqs, local state, zod 4 `z.flattenError`, React Hook Form, schemas generated from
  OpenAPI for a Pydantic backend); design systems (token tiers, typed variants, headless primitives, styling
  trade-offs); accessibility (WCAG 2.2 AA, APG patterns, focus management, route announcements, axe limits);
  Core Web Vitals and budgets (LCP/INP/CLS thresholds, lab vs field, Russell 2024 byte budgets, Lighthouse CI);
  images, fonts, scripts, bundle analysis and code splitting; i18n and localisation for French/English in
  Cameroon (ICU plurals, French text expansion, `fr-CM`/`en-CM` XAF output with U+202F/U+00A0, Africa/Douala
  time zone, next-intl); frontend security (XSS escape hatches, nonce CSP, token storage, env leaks, third-party
  scripts; cross-links to the security refs); errors and observability (error.tsx vs global-error, digests,
  instrumentation-client, source maps; frontend test map cross-linking testing refs); low-bandwidth and low-end
  devices (Save-Data, offline, PWA with Serwist, iOS install limits); React Native Web and Expo sharing. 122 source
  links, all answering 200 on 2026-10-10 except GitHub blob pages, which return 503 to scripted clients from this
  box (their files were confirmed through the GitHub API). Research and decisions:
  `docs/research/v0.7-frontend-sources.md`.
- **Imports: none.** Vercel's `vercel-labs/agent-skills` (commit `063bee94`) fails the import policy: no LICENSE
  file anywhere in the repo (MIT only declared in README/frontmatter), and `web-design-guidelines` tells the agent
  to fetch unpinned remote instructions. Nothing was quarantined because nothing was vendored; a human decides
  whether to ask upstream for a LICENSE file. OWASP sign-off (stage 2) is still pending.
- **New gates (stdlib only):** `eos i18n check` (next-intl / i18next JSON catalogs, flat or per-namespace; missing
  keys per locale, text-vs-group clashes, empty values, ICU syntax and missing `other` branches, argument
  mismatches against the reference locale, i18next `_one` without `_other`, literal `t("key")` calls whose key is
  in no catalog) and `eos bundle-size [--update]` (deterministic gzip of the build's client JS/CSS in
  `.next/static`, `out/_next/static`, `dist/assets`, Expo or CRA output; ratchet against
  `.eos/bundle-baseline.json`, fails above `max_growth_pct` 5 and `min_growth_kib` 1, optional absolute
  `budget_kib`). Both search every stack folder in a monorepo (first match wins; set `frontend.i18n.dir` to choose).
  `eos check` includes i18n problems when catalogs exist; `lighthouserc.*` counts as gate config.
- **Lanes:** trivial and spike unchanged; standard adds the in-process i18n check only when catalogs exist;
  risky, one-way-door and `verify --full` add the bundle ratchet only when a build output newer than the changed
  web files exists (otherwise a note).
- **Scaffolds:** `lighthouse` (`lighthouserc.json` with median-of-3 assertions LCP 2,500 ms, CLS 0.1, TBT 200 ms,
  365 KiB script and 730 KiB total; workflow running pinned `@lhci/cli` 0.15.1 via npx; reports kept private
  with a SHA-pinned `actions/upload-artifact` v7.0.2); `eslint-next` (core-web-vitals + TypeScript + the full
  jsx-a11y recommended set; image/font/script rules as errors; `react/no-danger` warns; eslint ^9 because
  jsx-a11y does not support 10 yet); `web-security` (nonce CSP builder and `proxy.ts` with a Report-Only switch,
  HSTS/nosniff/Referrer-Policy/Permissions-Policy, Playwright test for headers and zero CSP violations,
  `.semgrep/eos-frontend.yml` with three rules: tokens in web storage, private env in `"use client"` files,
  eval-like sinks); `i18n` (fr/en catalogs with ICU plurals, `lib/format.ts` for XAF and Africa/Douala dates plus
  a strict amount parser, Vitest tests pinning the exact Intl output). The `e2e-node` axe check now includes the
  WCAG 2.1 and 2.2 tags.
- **Validated on a real `create-next-app` 16.4 app:** ESLint, `next build`, Vitest, Playwright with Chrome,
  Lighthouse CI and actionlint. The CSP header test caught two template bugs that are now fixed: under Cache
  Components a prerendered page has no nonce (routes need `export const instant = false`), and `next/image`'s
  inline `style="color:transparent"` needs one allowed hash.
- **Library:** new injection-scan rule `remote-instructions` ("fetch the latest guidelines/rules…"); 20 eval tasks
  in `tests/evals/frontend.json` (context coverage 44% pack only → 100% with refs; a proxy, same author);
  bench key `frontend_stage7`. Pointers added to the frontend, security, performance-scale, testing-qa, mobile
  and design-direction packs, all within the 1,200-token budget. Always-on context unchanged at session start;
  the `page.tsx` path rules went down by 16 tokens.
- **Tests:** `FrontendGateTests` (9), `FrontendToolContractTests` (runs when `EOS_TEST_NEXT_FIXTURE` points at a
  Next app), semgrep fixtures for the frontend rules, and a selftest section "frontend scaffolds and gates".

### Added (stage 6: operations / SRE, 2026-10-10)
- **Ops area, 12 refs (~19k tokens, none always-on):** SLIs, SLOs, error budgets and multiwindow burn-rate
  alerting with an error-budget policy; OpenTelemetry (traces, metrics, logs, semantic conventions, OTLP and the
  Collector, head vs tail sampling, cardinality, W3C trace context, structured JSON logs with trace IDs, PII
  redaction); dashboards (RED, USE, four golden signals) and alerting/on-call for a solo dev or small team (paging
  hygiene, alert fatigue); incident response (SEV levels, roles, comms cadence, UTC timeline, blameless
  postmortems, runbooks; PagerDuty's Apache-2.0 docs credited); deployment strategies (rolling, blue-green,
  canary, progressive delivery, rollback, GitHub environment approvals, DORA metrics, preview environments);
  feature flags (categories, OpenFeature, kill switches, expiry, cleanup); capacity planning and cost/FinOps
  (budget alerts do not cap spend); backups and DR (RPO/RTO, 3-2-1, restore drills, AWS's four DR strategies) and
  chaos engineering (when it pays, game days); runtime config and secrets (twelve-factor, startup validation,
  Kubernetes ConfigMap/Secret facts, rotation); platforms (PaaS vs VMs vs Kubernetes, liveness/readiness/startup
  probes, image hygiene); IaC (OpenTofu/Terraform licence, Pulumi, state, plan review, drift, checkov, the March
  2026 trivy-action compromise); operating in Africa and low-connectivity regions (ITU 2025, the March 2024 West
  Africa cable outage, South African cloud regions, data residency, MTN MoMo single-shot callbacks, M-PESA
  maintenance). 75 external URLs checked on 2026-10-10 (one, Safaricom, answers 403 to scripted clients; its text
  was fetched earlier the same day). Research: `docs/research/v0.7-ops-sources.md` (41 ranked sources). Google
  SRE books are linked only (licence); OpenTelemetry, OpenFeature and FinOps (CC BY 4.0) summarised, not adapted.
- **New gate `eos ops check|alerts|budget|runbook` (stdlib only):** validates `ops/slo.json` (ids, objective,
  window, runbook exists), alert rules under `ops/alerts`, `monitoring/alerts`, `prometheus/rules` (every alert
  needs `labels.severity` and an existing `annotations.runbook_url`; warns when the runbook has no Mitigation
  section) and `ops/flags.json` (type, owner and description, `rollout_percent` 0-100 on boolean flags, release/experiment flags
  need an expiry within `flag_max_days`, default 90; flags read in code but not registered fail, unused ones warn).
  `eos ops alerts` generates Prometheus multiwindow burn-rate rules (14.4x/1h/5m and 6x/6h/30m page, 1x/3d/6h
  ticket) from the SLO file; `--check` fails when the generated file is stale; a missing one is a warning. `eos
  ops budget` prints the error budget in minutes; `eos ops runbook <name>` writes a runbook skeleton. The SLO
  and flags files, `.hadolint.yaml` and `.checkov.yaml` count as gate config for `eos test-integrity`.
- **Lanes:** trivial and spike unchanged; standard adds the in-process ops check only when the project has those
  files (milliseconds); risky, one-way-door and `verify --full` add hadolint on changed Dockerfiles when
  installed; `verify --full` adds checkov on changed IaC folders when installed. Otherwise a note says CI runs it.
- **Scaffolds:** `ops` (SLO file, generated burn-rate rules plus promtool unit tests, SLO runbook, incident
  response guide, postmortem template, `.semgrep/eos-ops.yml` with six rules for secrets, personal data and
  request bodies in Python/JS log calls, and a path-triggered workflow running `eos ops check` and a checksummed
  promtool); `otel-python` (vendor-neutral FastAPI/Flask setup over OTLP, JSON logs with trace IDs and redaction,
  health endpoints excluded from traces; tested with both frameworks); `otel-node` (Next.js `instrumentation.ts`
  with the Node SDK only on the Node runtime, JSON logger with trace IDs); `flags` (OpenFeature provider backed by
  `ops/flags.json` with env overrides, stable percentage rollouts identical in Python and TypeScript, a hook that
  records evaluations on the active span); `iac` (checksummed OpenTofu fmt/validate without backend or
  credentials, pinned checkov via uvx, `.checkov.yaml`, IaC `.gitignore`; never applies). `docker-python` gains
  `test_health.py` (liveness never touches dependencies; readiness fails with 503 on errors and on a 2 s timeout)
  and a non-root user; `docker-lint` adds `.hadolint.yaml` and a container workflow (checksummed hadolint, build
  without push). No new GitHub Actions: tools are checksummed release binaries or pinned packages; versions in
  `versions.toml`.
- **Packs:** pointers to the new refs in operations, infra-devops, release and architecture; budgets 994, 1,054,
  905 and 1,087 of 1,200; rule slices unchanged.
- **Evals:** `tests/evals/ops.json`, 19 tasks; context coverage 51% (pack) → 100% (pack + refs), mean context
  1,002 → 2,782 tokens (availability proxy, not answer quality). Always-on tokens unchanged (session start Cursor
  1,884, Cline 1,860, Claude Code 1,907, Codex 1,397).
- **Tests:** `OpsGateTests`, `OpsToolContractTests` (promtool, rendered Python templates, hadolint; with
  `EOS_TEST_TOOLS=1`), semgrep fixtures for the ops rules, selftest section "operations scaffolds and gates".

### Added (stage 5: testing & QA, 2026-10-10)
- **Testing area, 12 refs (~17.5k tokens, none always-on):** strategy shapes (pyramid, trophy, honeycomb; when
  each fits; what not to test); unit test design (behaviour not implementation, test-double taxonomy, avoiding
  over-mocking); integration tests with real dependencies (Testcontainers, ephemeral databases, contract tests via
  `api/testing`); E2E with Playwright (locators, fixtures, auth state, flakiness, sharding, traces) plus visual
  regression and axe accessibility checks; property-based testing (Hypothesis, fast-check, stateful) and fuzzing
  (Atheris, Go, Jazzer.js, ClusterFuzzLite); mutation testing (mutmut, StrykerJS incremental; where it pays);
  performance/load testing with k6 (test types, open vs closed model, thresholds, realistic data, where to run);
  test data (factories, builders, object mothers, anonymised production data); flaky tests and suite speed
  (detection, quarantine with expiry, retry policy, parallelism, affected tests, sharding, caching); coverage
  (meaning, ratchet, diff coverage) and testing AI-written code against test cheating (ImpossibleBench, METR;
  cross-links to `eos test-integrity` and protected paths); LLM evals; mobile testing (Maestro, Detox, Flutter
  integration_test, device farms; Firebase Test Lab shuts down 30 September 2027) and the QA process for a solo
  dev or small team (exploratory charters, release checklist, bug bash). 80 external URLs checked live on
  2026-10-10 (research: `docs/research/v0.7-testing-sources.md`, 48 ranked sources). Nothing vendored or adapted.
- **New gates in `eos` (stdlib only):** `eos diff-coverage` (changed lines from `git diff -U0` against the
  merge-base, Cobertura XML or LCOV; default 80%, 90% on money/auth/security paths; config `testing.*` in
  `.eos/config.json`; exit 2 when no report); `eos quarantine check|list|add` (`tests/quarantine.json`, owner,
  issue and expiry required, max 14 days; `eos check` fails on expired or incomplete entries; the file counts as
  gate config for `eos test-integrity`); `eos mutation-plan` (changed source on risky paths, all changed source
  with `lane:risky`, all risky files on schedule) and `eos mutation-score` (mutmut cicd stats or Stryker JSON).
- **Lanes:** trivial and spike unchanged; standard adds the in-process quarantine check; risky, one-way-door and
  `verify --full` add changed-line coverage from a coverage report newer than the edits (otherwise a note) and a
  pointer to the CI mutation job. No new subprocesses in any lane.
- **Scaffolds:** `quarantine`, `property-python` (Hypothesis), `property-node` (fast-check + Vitest), `load-k6`
  (smoke and arrival-rate load scripts with tagged thresholds, abortOnFail, SharedArray data; workflow on manual
  dispatch and weekly smoke when `LOAD_BASE_URL` is set, never on PRs), `mutation` (plan → mutmut / Stryker
  incremental → score, `MUTATION_MIN` default 60). tests-python conftest gains a Hypothesis `nightly` profile and
  honours quarantine (`xfail(strict=False)` while active); the e2e-node Playwright config skips quarantined
  titles. Stack CI (Python, TypeScript, Flutter) fetches full history, writes coverage and runs a "Diff coverage"
  step on pull requests. New action `grafana/setup-k6-action` pinned to v1.2.2 by SHA; tool versions in
  `versions.toml` (k6 2.3.0, mutmut 3.8.0, Stryker 10.0.0, Hypothesis 6.168.5, fast-check 4.10.2, diff-cover 10.6.0).
- **Tests and CI:** `TestingGateTests` (diff coverage incl. risky threshold and unmeasured files, quarantine
  expiry rules, mutation plan and score, lane wiring, scaffold rendering); opt-in `TestingToolContractTests`
  (`EOS_TEST_TOOLS=1`: real mutmut, Hypothesis and the conftest quarantine hook); CI job `testing-tools`
  (checksummed k6 download); selftest section for the stage-5 scaffolds and gates.
- **Packs:** testing-qa points to all 12 refs; mobile, release, agent-security and performance-scale point to the
  relevant ones (performance-scale reworded one line to fit, 1,199/1,200). Rule slices unchanged; always-on
  session start and path rules unchanged.
- **Evals:** `tests/evals/testing.json`, 15 tasks; context coverage 44% (pack only) → 100% (pack + refs).

### Added (stage 4: API design, 2026-10-10)
- **API area, 11 refs (~22.9k tokens, none always-on):** resource modelling, naming, methods and status codes;
  errors with RFC 9457 problem details (stable `code`, validation `errors[]` with JSON pointers, framework wiring);
  collections (cursor pagination, filtering, sorting, totals, search/export); reliability (idempotency keys, client
  retry policy, ETag/If-Match with 412/428, long-running operations, bulk and batch); evolution (compatibility
  rules, versioning schemes, RFC 9745 `Deprecation` + RFC 8594 `Sunset`, stability levels, the oasdiff gate);
  contract-first OpenAPI 3.1 (3.2 status, codegen for Next.js with openapi-typescript/openapi-fetch or Hey API and
  for Kotlin/Swift/Dart with OpenAPI Generator, docs and DX); outbound webhooks (Standard Webhooks signing,
  retries, ordering, replay, SSRF-safe sending); rate limits and API-layer authN/Z (the IETF RateLimit header
  fields are an active draft, -11, not an RFC; cross-links to the stage-2 security refs); GraphQL (when it fits,
  trusted documents, depth/cost limits, DataLoader); gRPC/Protobuf/AsyncAPI/CloudEvents contracts (deadlines,
  retries, `buf breaking`); API testing (Schemathesis, when Pact fits, must-have cases). 86 external URLs checked
  live on 2026-10-10 (research: `docs/research/v0.7-api-sources.md`).
- **CC BY 4.0 adaptations with attribution, no vendoring:** Google AIP, Zalando RESTful API Guidelines, Microsoft
  REST API Guidelines and Azure Architecture Center are paraphrased (licence evidence and pinned commits in the
  research doc). New optional ref key `adapted_from`; `eos library lint` requires a matching `## Attribution`
  section with each adapted URL, a licence link and a "Changes:" note (unit-tested). Wording needs human review
  before a public release.
- **`eos scaffold api-contract` upgraded:** `.spectral.yaml` with 13 `eos-*` rules on top of `spectral:oas`
  (problem+json errors, a 4xx per operation, no bare-array bodies, list GETs paginated with a bounded page size,
  offset flagged, kebab-case paths with `:verb` custom methods, no CRUD verbs, POST Idempotency-Key, deprecated
  needs `x-sunset`, security declared, money not `number`, `*_at` as `date-time`); a Spectral lint job (Node 24,
  pinned setup-node); the oasdiff job now sets `deprecation-days-stable: 180` / `deprecation-days-beta: 31`
  explicitly (the action has no defaults; without them a deprecation needs no sunset) and `github-token: ""`;
  new `api-fuzz.yml` runs `uvx schemathesis==4.30.1` against the app started per stack (short on PRs, stateful
  nightly). Versions in `versions.toml` (`spectral-cli`, `schemathesis`). No new third-party actions.
- **Tests and CI:** Spectral fixtures (`tests/spectral/`: failing, passing and edge cases) with
  `tests/spectral_check.py`; oasdiff flag tests with dynamic sunset dates (`tests/oasdiff/`); scaffold render
  test; a static test that every rule has a failing fixture; CI job `api-rules` (Spectral fixtures, checksummed
  oasdiff v1.33.0 binary); selftest renders the scaffold, runs actionlint, and with `--full` the Spectral fixtures.
- **Packs:** api-design points to all 11 refs and the scaffold; backend, testing-qa, mobile and architecture point
  to the relevant ones. All within budget; always-on session start unchanged, `route_py` path rules 8 tokens
  smaller, `page_tsx` unchanged.
- **Evals:** `tests/evals/api.json`, 14 tasks; context coverage 27% (pack only) → 100% (pack + refs).

### Added (stage 3: data, 2026-10-10)
- **Data area, 12 refs (~26k tokens, none always-on):** relational modelling (constraints, normalisation vs
  deliberate denormalisation, enums vs lookup tables, JSONB trade-offs), keys/money/time (identity vs UUIDv7/ULID,
  PostgreSQL 18 `uuidv7()`, integer minor units and zero-decimal currencies such as XAF, double-entry ledger schema,
  `timestamptz`), multi-tenancy (tenant_id + RLS pitfalls, schema/database per tenant), history and retention
  (soft delete, audit tables, temporal data incl. PG 18 `WITHOUT OVERLAPS`, erasure and retention at the schema
  level), PostgreSQL indexing, query patterns and EXPLAIN, concurrency (lock queue, isolation levels and anomalies,
  MVCC, vacuum, bloat, wraparound), operations (PgBouncer, replicas, partitioning, backups/PITR, upgrades,
  extensions), zero-downtime migrations (expand/contract, lock-safe DDL, batched backfills; Alembic, Prisma 7/8,
  Drizzle, Laravel), ORMs vs SQL and test data (SQLAlchemy 2, Prisma, Drizzle; real-Postgres tests, factories),
  search and Redis (Postgres FTS/pg_trgm vs dedicated engines, Redis use and misuse, licences, Valkey), NoSQL and
  analytics (when another store fits, OLAP separation, CDC, materialized views). 144 cited URLs checked live on
  2026-10-10; every number traced to a source (research: `docs/research/v0.7-data-sources.md`). Imports: none.
  Wired to the data-modeling, backend, performance-scale, api-design, testing-qa, operations, infra-devops,
  data-ml and architecture packs, all inside their 1,200-token budgets.
- **`eos scaffold db-safety`** (PostgreSQL): a tuned `.squawk.toml` (`pg_version`, `assume_in_transaction`);
  `scripts/db/alembic_squawk.py`, which lints each changed Alembic revision through its offline SQL
  (`alembic upgrade <down>:<rev> --sql`, bookkeeping stripped, real BEGIN/COMMIT kept, merge revisions skipped);
  `scripts/db/schema_lint.sql`, run on a freshly migrated database, which fails on foreign keys without a supporting
  index and on money-like columns stored as `real`/`double precision`/`money` (warns on `timestamp` without time
  zone; reviewed exceptions go in an allow list); `.semgrep/eos-data.yml` with 6 money-as-float rules (SQLAlchemy /
  Django models, float conversions, `parseFloat`, Drizzle, Prisma, SQL DDL; rate/percent names skipped); and a
  `db-safety` workflow running all three (migrate command auto-detected for Alembic, Prisma, Drizzle, or set
  `MIGRATE`). The core squawk job now also covers `drizzle/**.sql` and reads `.squawk.toml`.
- **Tests:** Semgrep fixtures for the data rules (`semgrep --test`); `tests/semgrep_generic_check.py` checks the
  `*.sql`/`*.prisma` rules, whose annotations `semgrep --test` ignores; unit tests for the scaffold and the Alembic
  linter (fake alembic/squawk); a schema-lint test against real Postgres (new `schema-lint` CI job with a Postgres
  18 service; locally with `EOS_TEST_PG_DSN`). `tests/evals/data.json` (14 tasks): context coverage 35% with the
  pack alone → 100% with pack + refs, at a mean of ~3.9k tokens per task. Always-on context unchanged.

### Fixed (stage 3)
- **Supply chain:** every GitHub Action in eos-generated workflows (core CI, stack CI, all scaffolds) is pinned to a
  full commit SHA with a `# vX.Y.Z` comment, so Renovate (`helpers:pinGitHubActionDigests` in the seeded
  `.github/renovate.json`) updates both. `eos check` errors on unpinned actions in eos-generated workflows and warns
  on your own; a unit test checks every template against `ACTION_PINS` and `versions.toml`.

### Added (stage 2: security, 2026-10-10)
- **Security area, 13 refs (~22k tokens, none always-on):** threat modelling (STRIDE workflow + LINDDUN),
  authentication (NIST SP 800-63B-4 passwords, OWASP hashing parameters, sessions, MFA, passkeys), OAuth/OIDC/JWT
  (RFC 9700, RFC 10017 BFF, RFC 8725), authorization (RBAC/ABAC/ReBAC, BOLA/BOPLA/BFLA, Postgres RLS), input
  handling and injection (SQLi, XSS/strict CSP, SSRF/IMDSv2, uploads, deserialization), web/API/mobile-backend
  hardening, secrets and keys, crypto do's and don'ts, payments (idempotency, ledger, webhook verification, fraud
  signals, PCI SAQ A 2025 change), privacy (LINDDUN, GDPR, Cameroon Law 2024/017 with a not-legal-advice caveat),
  supply chain (SLSA 1.2, SBOM, pinning, release-age delays, slopsquatting), security testing, and LLM/agent
  security (lethal trifecta, Rule of Two, injection-resistant patterns, MCP risks, OWASP LLM and Agentic Top 10).
  117 cited URLs checked live on 2026-10-10. Wired to the security, agent-security, api-design, backend,
  data-modeling, mobile, infra-devops, release and testing-qa packs; the security pack was compressed to stay under
  its 1,200-token budget.
- **Vendored, quarantined:** 16 OWASP Cheat Sheets (CC-BY-SA-4.0, pinned `cb9fe01e`) in `packs/vendor/owasp-cheatsheets`
  and `packs/vendor/owasp-llm-prompt-injection` (held with 19 injection-scan findings, which are quoted attack
  examples). **Pending human sign-off**: not installed into projects and not pointed to until a human runs
  `eos vendor review`.
- **`eos vendor` quarantine:** new `status: pending-human-sign-off` and attribution in `PROVENANCE.json`; `--hold`
  keeps a source with findings quarantined; pending sources are skipped by install and rejected as pack pointers;
  `vendor check` warns while pending and `--strict` fails; review of a source with findings needs
  `--accept-findings`; fetches use a partial clone.
- **Enforcement:** `eos scaffold security` now also writes `.semgrep/eos-security.yml` (12 rules: JWT verification
  disabled / `none`, non-constant-time signature compares, webhook routes without signature checks (Python and
  Node), `Math.random` for secrets, SQL template literals, CORS wildcard/reflection with credentials, TLS
  verification disabled, unsanitized `dangerouslySetInnerHTML`) and a blocking Semgrep CI job. The rules have
  `ruleid:`/`ok:` fixtures (`tests/semgrep/`) run by `semgrep --test` in CI and `selftest --full`. New
  `eos scaffold security-tests` (Python): a webhook verifier (Standard Webhooks + hex HMAC, raw body, constant-time,
  timestamp tolerance, replay guard) with 14 tests including GitHub's published test vector, and an
  authorization-matrix test template (BOLA, cross-tenant, BFLA, mass assignment, route coverage) that skips until
  wired. Threat-model template gains LINDDUN rows and owner/expiry on accepted risks.
- `tests/evals/security.json` (12 tasks): context coverage 28% with the pack alone → 100% with pack + refs, at a
  mean of ~3.3k tokens per task. Always-on context unchanged.

### Added
- **Deep reference library** (`packs/ref/<area>/<topic>.md`): fixed format (decision guide, anti-patterns, checks,
  ≥ 2 verified sources), ≤ 3,000 tokens each, `verified` date and `revisit_days`. Packs point to refs in one
  `## Deep references` section (~5 tokens per pointer), which is kept out of edit-time path rules. `eos init` /
  `eos update` install only the refs that selected packs point to, plus `.eos/packs/ref/INDEX.md`.
- **Architecture area, 11 refs (~20k tokens, none always-on):** quality attributes and trade-offs, modular monolith,
  service communication (sync/async, contracts, outbox, sagas), data consistency, caching, database scaling,
  API performance (N+1, pagination, BFF/GraphQL), event-driven design and queues, resilience, scaling stages (and
  when not to), cost. Wired to the architecture, performance-scale, topology, api-design, data-modeling and backend
  packs. All 84 cited URLs checked live on 2026-10-10.
- **`eos library`** `list | lint | index | eval`: lint checks format, size, sources, dates, staleness (`--strict`),
  pointers and orphans, and scans for prompt injection; eval compares tokens and rubric coverage with and without
  refs (`tests/evals/*.json`) and scores real agent answers with `--responses`.
- **`eos vendor`** `add | update | review | check | list`: third-party text pinned to a full commit SHA, licence on an
  allow-list, injection-scanned, per-file SHA-256 in `packs/vendor/PROVENANCE.json`, named human review; in-place
  edits fail the check; `packs/vendor/` is a risky lane. Nothing is vendored yet (see the sources research).
- **Enforcement:** new `tables` lifecycle criterion; the architect phase now needs filled "Quality attributes" and
  "Failure modes" tables in `docs/architecture/overview.md` (BMAD architecture output also satisfies it).
  Library lint and vendor check run in pre-commit, `tests/selftest.sh` and CI.
- `tests/bench/measure_context.py`: per-tool context measurement that counts every folder each tool scans.

### Changed
- **One copy of each skill per tool.** Cursor reads `.agents/`, `.cursor/`, `.claude/` and `.codex/` skill folders
  without de-duplicating; eos now writes each skill once in a folder every selected tool reads (all tools:
  `.claude/skills`; Codex then uses `.eos/packs/INDEX.md`). Measured: Cursor 2,347 → 1,884, Cline 2,277 → 1,860
  tokens at session start (the v0.6 bench had counted one folder per tool).
- **Guard runs once inside Cursor.** Cursor also runs Claude Code hooks from `.claude/settings.json`; the
  `claude-*` guard modes now step aside when the payload comes from Cursor (`cursor_version`/`workspace_roots`) and
  eos's Cursor hooks are installed. Detection uses the payload, not env vars, so `claude` run in Cursor's terminal
  keeps its guard.
- The code-review pack points to the tools' native reviewers (`/review`, Bugbot, `/security-review`) and acts as
  their rubric instead of duplicating them.
- The topology pack's pointer to `topologies.md` moved into its Deep references line.

## [0.6.0] - 2026-10-10
Velocity audit: the process now fits the risk. A typo no longer pays for what a payment change needs, there are
sanctioned fast paths for spikes and hotfixes, and eos measures its own cost. Safety for money, auth, secrets and
force pushes is unchanged. Full audit with ten workflow walk-throughs: docs/research/v0.6-velocity-audit.md and
docs/BLUEPRINT.md section 29.

| Measured on the same fixture (median of 15; v0.5.0 and v0.6.0 run back to back) | 0.5.0 | 0.6.0 |
|---|---|---|
| Guard hook per agent tool call (read / edit / shell) | 92 / 93 / 99 ms | 44 / 44 / 48 ms |
| Commit: docs typo / .py change | 966 / 979 ms | 394 / 398 ms |
| Stop check (.py change) | 522 ms | 420 ms |
| Session start, default `web-app` (Cursor / Cline / Claude Code / Codex) | 2,039 / 2,015 / 2,062 / 2,015 | 1,884 / 1,860 / 1,907 / 1,860 |
| Cline per request incl. default MCP schemas | ~6,465 (`build`) | ~3,110 (`minimal`) |

(0.5.0 defaulted to teaching on; with teaching on, 0.6.0 is +30. `api` 1,795–1,842; `full` 1,976–2,023. Bench:
tests/bench/bench_hooks.py, results in tests/bench/results-v0.*.json. CI wall time was not measured.)

### Added
- **Risk lanes**: `eos lane` classifies the current change as trivial, standard, risky or one-way-door from paths
  (risk words matched as whole words), migrations/infra/CI/gate configs, diff size and content (dropped columns,
  removed contract lines), plus spike/hotfix branch prefixes. `--ci` writes the lane to the job summary and fails
  spike PRs. Override with a `lane:<name>` PR label or `EOS_LANE` (logged). Tunable under `lanes` in `.eos/config.json`.
- **`eos verify`**: the checks a change needs, sized to its lane: pre-commit on changed files; related tests for
  standard (pytest by module, `vitest related`, `jest --findRelatedTests`); the stack full check and strict
  test-integrity for risky lanes; `--full` forces everything. Runs app dirs in parallel. Core rule 2 now uses it.
- **Escape hatches**: `eos spike <name>` (spike/ branch, no tests or plans, stop check off, guards and gitleaks on,
  CI refuses to merge; `eos spike done` writes a learning note) and `eos hotfix <name>` (branch from fresh
  origin/main with a 15 s fetch timeout or `--no-fetch`; smallest fix plus regression test; `eos hotfix done` writes
  a post-incident note from the git log). Core rule 8.
- **`eos stats`**: a local, git-ignored event log (`.eos/state/events.jsonl`) summarised as approval prompts per 100
  tool calls, guard/stop/hook p50 and p90, verify runs by lane, overrides, skips and lead time, with tuning tips.
- `eos next --skip` / `--unskip`; `eos --help` leads with the five daily commands.
- `.eos/bin/hook.py` launcher (bytecode-cached), `.eos/ruff.toml` so the project's own ruff ignores eos files,
  background `pre-commit install-hooks` at init (on a terminal, unless `EOS_NO_WARM`), CI Lane step.
- Guard: `git clean -fdx` (any flag combination with `f`) now asks; it slipped through in 0.5.0.

### Changed
- Core rules rewritten around lanes (~95 fewer tokens). Plans block only for risky changes that alter money, auth or
  security behaviour, and for one-way doors; "spans several modules" no longer blocks.
- Teaching mode is **off** by default; the default MCP profile is **minimal** for every product profile.
- Memory: only `memory/handoff.md` for unfinished work; git history is the progress log.
- `eos check` runs at commit only when agent-context files change; the commit-msg stage is installed only with
  release-please and uses a local hook (no download). Pre-push type checks and tests run through `eos hook-run`
  (timed; pytest `-x --ff`). The stop check skips gitleaks (it runs at commit) and spike branches.
- The loop guard fingerprints `git status` plus changed-file sizes and times instead of the whole diff.
- `eos test-integrity`: new suppression comments warn in trivial/standard lanes and block in risky lanes or with
  `--strict`. Skips, removed asserts and lowered thresholds still block everywhere.
- `eos next`: `.eos-new` files are a note, not a blocker. WORKFLOW leads with the golden path; the 12-step table is for
  new products only.
- `git-hooks/_dispatch` skips its own gitleaks pass when the repo's pre-commit config already runs gitleaks.

### Removed
- The per-task `eos next --brief` core line and the `navigator` skill pack (25 phase packs).
- Seeded `memory/active-context.md` and `memory/progress.md` and their `eos check` warnings (`eos doctor` still warns on
  older projects). The remote `conventional-pre-commit` hook. The wizard's teaching question.

### Kept on purpose
Branch + PR + CI for every change; gitleaks on every commit; force-push and secret-read denials; test-integrity on
skips, asserts and thresholds; pre-push type checks and tests; the stop check; money/auth plan approval and human
review; one-way-door approval; cross-repo ceremony. Reasons: docs/research/v0.6-velocity-audit.md section 6.

## [0.5.0] - 2026-10-10
Any project state, self-guiding, any repo shape. eos now works on existing and messy repos as well as new ones,
tells you the next step in plain words, and handles modular monoliths, microservices, monorepos and multi-repo
workspaces. Details, sources and deferred items: docs/BLUEPRINT.md section 28, docs/research/v0.5-notes.md.

| Tool | Session start, 0.4.0 → 0.5.0 (default `web-app`; teaching off; `api`; `full`) | Path rules editing a route / a .tsx page |
|---|---|---|
| Cursor | 1,889 → 2,039; 2,009; 1,824 → 1,974; 1,941 → 2,155 | 2,864 / 2,256 (unchanged) |
| Cline | 1,865 → 2,015; 1,985; 1,800 → 1,950; 1,917 → 2,131 | 2,899 / 2,277 (unchanged) |
| Claude Code | 1,912 → 2,062; 2,032; 1,847 → 1,997; 1,964 → 2,178 | 2,899 / 2,277 (unchanged) |
| Codex | 1,865 → 2,015; 1,985; 1,800 → 1,950; 1,917 → 2,131 | none |

(Same FastAPI + Next.js fixture and script as 0.4.0; AGENTS.md alone 1,100 → 1,220. The 0.4.0 `api` figures were
re-measured on this run (1,824 vs 1,834 published). The increase is the one-line next-step rule (~33), the navigator
skill description (~27), the teaching line (~30, off with `eos teach off`) and, on this two-app fixture, the
monorepo topology block (~45). Everything else (3 packs, 2 reference files, concepts, lifecycle, templates) loads on
demand. Core-block budget 888/1,100; skill descriptions 491/500 with every pack selected.)

### Added
- **Lifecycle modes** (greenfield, brownfield, rewrite, maintain), detected from git history, code size and docs,
  shown with the reason: `eos mode`, `eos mode set <mode>`.
- **`eos adopt`** for existing repos, non-destructive by default. It scans languages, frameworks, build/test commands,
  CI, lint configs, existing AGENTS.md / CLAUDE.md / Cursor and Cline rules, folders, coverage signals, dependency
  health and git hot spots. It writes `docs/eos/project-map.md`, `docs/eos/baseline-report.md`,
  `docs/plans/improvement-plan.md` (P0/P1/P2, each with why and how) and `.eos/state/scan.json`. Files you already
  have are never overwritten: eos's version goes to `.eos/suggested/<path>` and your existing CI stays (only
  `eos-core.yml` is added). The manifest records `adopted: true`, so later `eos update` keeps this behaviour.
- **Ratchet gates**: `eos ratchet init|add|check|update` and `eos gates strict|ratchet`. Existing violations are
  recorded in `.eos/baseline/<name>.json` (file + message fingerprints, line numbers ignored); only new ones fail.
  `--tighten` lowers the baseline as debt is paid. Adopted repos get a pre-push `eos-ratchet` hook; strict hooks are
  offered in `.eos/suggested/pre-commit-strict.yaml`. Prior art: ESLint bulk suppressions, PHPStan baseline, Betterer.
- **Rewrite support**: `migration` pack and `ref/migration-playbook.md` (strangler fig, characterization tests,
  parity checks, feature flags and dual-run, expand/contract data migrations, cutover and rollback runbooks);
  `eos new migration "<title>"` creates the plan.
- **Navigator**: a phase state machine (`core/lifecycle.json`, overridable per project in `.eos/lifecycle.json`) with
  entry and exit checks per mode. `eos status` shows where you are; `eos next` gives the one next step, why, and the
  exact command or prompt to give your agent; `eos explain <topic>` explains a principle in plain words
  (`core/concepts.md`, with sources). Blockers (failing gates, `.eos-new` files, an open handoff, uncommitted setup)
  come first. The `navigator` skill and one core rule make agents end a verified task with `eos next --brief`,
  never mid-task, and not repeat an ignored suggestion.
- **Teaching mode** (`eos teach on|off`, on by default for new projects): agents explain each decision in one or two
  plain sentences and define jargon once.
- **`eos start`**: a short wizard for a new or existing folder (detects the state, runs init or adopt, then shows
  `eos next`).
- **Topologies**: detection of single app, monorepo, modular monolith, microservices and multi-repo workspace
  (`eos topology`, `eos topology set`), with a short AGENTS.md block. `topology` pack and `ref/topologies.md`
  (boundaries, contracts, shared-library policy, service template, catalog, compose). `eos new service <name>`
  (README, AGENTS.md, Backstage `catalog-info.yaml`, OpenAPI contract, row in `docs/architecture/services.md`),
  `eos new module <name>`, and `eos scaffold boundaries` (import-linter / dependency-cruiser from detected modules).
- **Monorepos**: every app directory is wired per stack (lists in the manifest, per-directory hooks and CI jobs).
- **Multi-repo workspaces**: `eos workspace init|add|status|sync|change`. Creates `eos-workspace.json`, a workspace
  AGENTS.md (repos, roles, contracts), CLAUDE.md import, a Cursor `.code-workspace` (multi-root), Cline rules that
  point into each repo, `docs/changes/` for cross-repo changes with linked PRs and contract versions, and a
  `workspace` block in each repo's manifest. Credentials in git remote URLs are stripped.
- **Docs**: new `docs/GUIDE.md` (plain-language guide), `docs/research/v0.5-notes.md`; README, WORKFLOW, PROFILES,
  ARCHITECTURE, SOURCES and the BMAD integration (brownfield flow against v6.12.1: `bmad-project-context`,
  `bmad-help`) updated.
- **Tests**: 50 → 67 unit tests, with fixtures for a messy repo (adopt must not clobber), a modular monolith, a
  3-service microservices monorepo, a rewrite project and a 4-repo workspace; selftest covers adopt, navigator and
  workspace and shellchecks the fixture scripts.

### Changed
- Skill descriptions shortened to keep all 19 intent packs under the 500-token cap.
- Dates use the local timezone explicitly.

### Fixed
- Drift no longer reports `.clinerules/*` as missing when `.clinerules` is your own file.
- An empty handoff template no longer counts as an open handoff.

### Deferred
- CODEOWNERS lines per module/service; several OpenAPI specs in the `api-contract` scaffold.
- Contract consumer detection in workspaces is a heuristic; check `eos-workspace.json`.
- Claude Code nested `.claude/rules` across a workspace not verified; `workspace status --prs` not tested without `gh`.
- Coverage is not ratcheted automatically, and `eos ratchet` is not inserted into your existing CI (it is an
  improvement-plan item).

## [0.4.0] - 2026-10-10
Research-driven upgrade: independent, cited research (docs/research/RESEARCH.md) folded into the system so it fits any
project type. Details, deferred items and reasons: docs/BLUEPRINT.md section 27.

| Tool | Session start, 0.3.0 → 0.4.0 (default `web-app` profile; `api` profile; `full`) | Path rules editing a route / a .tsx page | MCP schemas per request |
|---|---|---|---|
| Cursor | 1,740 → 1,889; 1,834; 1,941 | 2,864 (unchanged) / 2,241 → 2,256 | names only (lazy) |
| Cline | 1,716 → 1,865; 1,810; 1,917 | 2,899 (unchanged) / 2,262 → 2,277 | unchanged: ≈4,450 `build`, 1,250 `minimal` |
| Claude Code | 1,763 → 1,912; 1,857; 1,964 | 2,899 (unchanged) / 2,262 → 2,277 | names only (tool search) |
| Codex | 1,716 → 1,865; 1,810; 1,917 | none | deferred (tool search) |

(Same FastAPI + Next.js fixture and script as 0.3.0. The increase is the new Product-profile block (~50–140 tokens,
by answers) plus the decisions and agent-security skill descriptions; profiles keep irrelevant skills out.)

### Added
- **Project profiles + questionnaire**: `eos init` asks project type (web-app, api, mobile, data-ml, internal-tool,
  cli-library, full) and five risk questions (money, personal data, LLM features, scale, low-end devices) on a
  terminal, or takes `--profile`, `--answers k=v,…`, `--yes`, `--interactive`. Saved in the manifest; rendered as a
  short "Product profile" block in AGENTS.md (security target ASVS 5.0 L1/L2, MASVS for mobile, low-end and LLM
  notes). Unknown money/personal-data answers count as yes (fail-safe). Profiles choose the skill packs; files-mode
  packs are always installed. Switching profile prunes unselected generated files (edited ones are kept).
  `core/profiles.json`, docs/PROFILES.md. Suggested scaffolds and MCP profile printed after init.
- **Phase packs**: `decisions` (decision engine: one-way/two-way doors, boring defaults, total cost, build vs buy,
  fitness function, ADR), `design-direction` (direction and tokens before UI code, list of AI-generic defaults to
  reject, WCAG 2.2 floor, screenshot critique loop), `agent-security` (OWASP Agentic Top 10, lethal trifecta, MCP
  tool poisoning/rug pulls, sandboxing, injection evals), `performance-scale` (SLOs and burn-rate alerts, scaling
  ladder, capacity model, load tests, when not to scale), `data-ml` (reproducible runs, data contracts, leakage,
  slice evals, model cards, drift).
- **Reference files** read on demand (`.eos/packs/ref/`): `decision-matrices.md` (questionnaire + matrices for
  stack, database, hosting, auth, monolith vs services, mobile approach, build vs buy, internal tools) and
  `security-baseline.md` (ASVS level choice, security cadence, GDPR / Cameroon Law 2024/017 / PCI DSS notes,
  supply-chain checklist).
- **Stack packs**: `react-native-expo` (Expo SDK 57 / RN 0.86, dev builds, CNG, EAS Build/Update with runtimeVersion,
  secure store, offline, Maestro/Detox) and `flutter` (3.47 / Dart 3.13; analyzer, state ADR, secure storage,
  offline, size, obfuscation) with `ci-flutter.yml` (subosito/flutter-action@v2, pinned Flutter) and pre-commit hooks.
  Expo detection by `app.json`/`app.config.*` containing "expo"; Flutter no longer reported as unsupported.
- `eos new plan "<title>"` (execution plans in docs/plans/active with progress and decision logs) and
  `eos new design` (docs/design/direction.md); `docs/plans/tech-debt.md` seeded by init.
- `eos scaffold reproducible`: `mise.toml` (pins from versions.toml, lockfile on), `.devcontainer/devcontainer.json`
  (official features), docs/dev-environment.md (worktrees per agent, offline tips).
- docs/research/{RESEARCH.md,notes.md}: cited research report and raw notes.

### Changed
- `security` pack: OWASP Top 10:2025 (incl. A10 exceptional conditions), ASVS 5.0 levels tied to the product
  profile, LINDDUN for personal data, SLSA Build L2+ target, slopsquatting check; money/PII lines condensed; links
  to the security baseline.
- `mobile` pack: MASVS levels, deep links, low-end/low-data rules (small downloads, SMS/USSD fallbacks, cheap
  Android test), OTA update rules, Maestro/Detox.
- `architecture` (fitness functions whose errors say how to fix), `code-review` (duplication/drift, cross-model
  review, human approval for money/auth/security), `maintenance` (weekly garbage collection), `frontend` (follow
  the design direction). Shorter skill descriptions for api-design, data-modeling, discovery, maintenance.
- Core rules: one line on execution plans for multi-session work. Core budget 1,000 → 1,100 (product block).
- `eos update` adds new packs only when the project's profile selects them; pre-0.4 projects are treated as `full`.
- versions.toml: flutter 3.47.7, expo 57.0.27, react-native 0.87.1, dart 3.13.5, mise 2026.10.7,
  subosito/flutter-action v2, jdx/mise-action v5. MCP phase mapping for the new packs.
- WORKFLOW: decisions and design-direction steps, plans, weekly garbage collection.

### Tests
- 50 unit tests (was 39): profiles vs packs/CLI, phase selection, skill budget per profile, fail-safe security
  level, questionnaire, Expo/Flutter detection, Flutter CI/pre-commit rendering, profile switch pruning, update
  behaviour for profiled and legacy projects, `new plan|design`, devcontainer JSON validity.
- selftest: Expo and Flutter fixtures (init, check, pre-commit config, actionlint).

## [0.3.0] - 2026-10-09
Senior review: productivity over minimal spend, mechanical handoffs, real CI gates, production scaffolds.
Full findings, what was fixed and what was deferred: docs/BLUEPRINT.md section 26.

| Tool | Session start, 0.2.0 → 0.3.0 | Path rules editing a route | MCP schemas per request |
|---|---|---|---|
| Cursor | 1,715 → 1,740 | 2,864 (unchanged) | names only (lazy) |
| Cline | 1,691 → 1,716 | 2,899 (unchanged) | 1,250 → ≈4,450 in the default `build` profile (GitHub now on); `minimal` = 1,250 |
| Claude Code | 1,738 → 1,763 | 2,899 (unchanged) | names only (tool search) |
| Codex | 1,691 → 1,716 | none | deferred (tool search) |

(0.2.0 re-measured on its tag with the same script; +25 tokens = one escalation line in the core rules.)

### Added
- `eos mcp list|status|use <profile|phase> [--tools …]`: per-task MCP profiles (minimal, build, review, api, design,
  debug-ui, off) in `mcp/servers.json`, chosen per tool and remembered in state.json; phase ids map to profiles.
  Cline gets every server with secrets set, toggled with `disabled`, so you can flip one in its MCP panel.
  Measured per-server token cost shown per profile. Cline CLI settings file supported.
- `eos models [task] [--failures N] [--check] [--usage]` and `personal/models.toml` (+ git-ignored
  `models.user.toml`): premium / strong / cheap tiers, task → tier routing, escalation after N failures, budget caps
  as settings (0 = none); `--check` verifies ids and prices against the live OpenRouter catalogue; `--usage` compares
  your key's spend with the caps (optional `OPENROUTER_API_KEY` in secrets.env).
- `eos new adr|story "<title>"`: numbered files from templates; ADRs get their INDEX line.
- `eos scaffold list|release|security|api-contract|codeowners|compose|docker-python|docker-node|tests-python|e2e-node`:
  opt-in starter files, written once (release-please v5; dependency review v5 + SBOM + CodeQL v4 with a threat-model
  template and dependency policy; oasdiff breaking-change gate with `review: false`; CODEOWNERS; Postgres 18 +
  Redis 8 compose and `.env.example`; uv and Next.js standalone Dockerfiles with health checks; testcontainers
  fixture, factories and test strategy; Playwright smoke + axe).
- `eos uninstall [--force]`: removes generated files you did not edit, strips hook entries and AGENTS.md blocks,
  keeps memory, docs, templates and scaffolds.
- `eos init` seeds a PR template (AC → test map, risk boxes, AI-assistance note) and story/bug issue forms, and runs
  `pre-commit install` when pre-commit is available.
- Guard: `push_policy: "feature-branches"` (default for new projects) allows pushes to non-protected branches and
  still asks for protected branches, tags, deletes, --all/--mirror, force-with-lease and sub-shell pushes.
- CI: coverage gate (`COVERAGE_MIN`, default 80) when pytest-cov is installed; bundle-size step (`size` script);
  Playwright e2e + a11y when a Playwright config exists; squawk on changed SQL migrations in eos-core.
- `docs/WORKFLOW.md`: idea → release table with the check at each handoff; plan vs act, escalation, recovery,
  worktrees and cloud agents, system evals, memory hygiene.
- Memory staleness warnings in `eos check` and `eos doctor` (advisory, never fail the gate).
### Changed
- `eos doctor` is actionable: every problem line ends with its fix command (brew/winget/Linux), checks PATH, WSL
  (`/mnt/c`), bootstrap version, empty secrets for the active profiles and the current project (version behind,
  hooks, `.eos-new` files, AGENTS.md placeholders, stale memory). Exit 1 only when a required tool is missing.
- GitHub MCP is no longer hard-excluded from Cline; `clients` remains as an optional per-server override.
- Claude Code MCP script removes previously managed servers before adding the active profile's.
- BMAD dev persona: name tests after AC ids; PR body follows the PR template.
- Core rules: one line on escalating after two failed attempts at a hard problem.
### Fixed
- Guard: `git -C dir push --force` and `git push origin +branch` were not denied (regex only matched `git push`).
### Upgrade notes
- `eos update` seeds the new PR/issue templates. `.eos/config.json` is seeded once, so add
  `"push_policy": "feature-branches"` by hand to opt an existing project in (it keeps asking otherwise).
- Re-run `eos bootstrap` to render the default `build` MCP profile; `eos mcp use minimal --tools cline` restores
  the 0.2.0 Cline footprint.

## [0.2.0] - 2026-10-09
Context and reasoning audit: less always-on text, no duplicate loading, fewer false prompts, bounded loops.
Measured on a FastAPI + Next.js fixture with all four tools (chars/4; see docs/BLUEPRINT.md section 4.2):

| Tool | Session start, 0.1.0 → 0.2.0 | MCP schemas at start | Path rules editing a FastAPI route, 0.1.0 → 0.2.0 |
|---|---|---|---|
| Cursor | 3,114 → 1,724 | names only (lazy) | 4,346 → 2,864 |
| Cline | 2,743 → 1,700 | 4,450 + Postman + Figma (unmeasured) → 1,250 | 4,331 → 2,899 |
| Claude Code | 2,816 → 1,747 | names only (tool search) | 4,331 → 2,899 |
| Codex | 2,743 → 1,700 | deferred (tool search) | none (reads `.eos/packs/INDEX.md` on demand) |

### Changed
- Core rules rewritten (~720 → ~670 tokens; AGENTS.md ~1,710 → ~980): process scales with risk (plan + approval only
  for schema, public API, money, auth, infra or multi-module work); checks are reported one line each, with output
  only on failure; low-risk gaps get a stated assumption instead of a question; no bold walls; the arbitrary
  "40 tool calls" rule is gone; memory is updated only when there is state worth keeping.
- The per-pack Context map moved out of AGENTS.md into the generated `.eos/packs/INDEX.md`.
- Path rules carry only a phase pack's Standards + Automated checks (plus a pointer); skills keep the whole pack.
- Path rules never carry a `description`: "both" packs were listed twice in Cursor (rule + skill).
- Stack-pack globs are prefixed with the stack's directory, so `api/app/*.py` no longer attaches Next.js rules.
- Skill descriptions shortened (527 → 324 tokens for all 12). Profile trimmed (~390 → ~280) and no longer asks for
  pasted command output (it contradicted "keep it short").
- Bold emphasis removed from packs; the volatile "TypeScript 7 is current" line and duplicate stack DoD sections removed.
- MCP: only GitHub (read-only) and Context7 enabled; Postman and Figma off until a phase needs them. New per-server
  `clients` list keeps GitHub out of Cline, which sends every enabled tool schema on every request.
- BMAD dev/architect overrides no longer inject packs that already attach by path (~4-5k tokens per dev session).
### Fixed
- Guard: read-only commands (`rg`, `grep`, `git status/log/diff/commit`, `cat`…) no longer prompt because they
  mention `psql`, `DELETE FROM`, `kubectl apply`… and no longer count towards the loop guard. Shell interpreters,
  `$(…)`, backticks and `find -exec` still get the full checks.
- Stop hook: checks only files changed in the current agent session; skips gitleaks (still runs at commit);
  output capped at 40 lines / 3,000 characters with the full log in `.eos/state/last-check.log`; a timeout lets
  the agent stop instead of retrying.
### Added
- Budgets enforced by `eos check`/`eos budget`: core blocks ≤1,000, AGENTS.md ≤1,600, profile ≤400, path rule ≤800,
  all skill descriptions ≤500, intent descriptions ≤160 chars; memory caps active-context 40, handoff 30,
  lessons 40, progress 200 lines.
- Tests for the new budgets, rule slicing, scoped globs, guard false positives, stop-output cap, session-scoped stop
  check, memory caps and MCP defaults (29 unit tests).

## [0.1.0] - 2026-10-09
### Added
- Core always-on `AGENTS.md` rules with stop conditions (anti-loop), just-in-time loading rules and memory rules.
- 18 phase packs: ideation, discovery, requirements, ux-design, architecture, data-modeling, api-design, backend,
  frontend, mobile, infra-devops, testing-qa, security, code-review, release, operations, documentation, maintenance.
- Stack packs: python, python-fastapi, python-flask, typescript, nextjs, plus `_template`.
- `eos` CLI: bootstrap, init, update, sync, check, budget, detect, doctor, new-stack, test-integrity, guard.
- Adapters for Cursor (.mdc + skills + hooks), Cline (.clinerules + skills + hooks), Claude Code (rules, skills, settings
  hooks, CLAUDE.md) and Codex (AGENTS.md + .agents/skills + config.toml MCP).
- MCP canonical config rendered per tool with secrets kept outside git; global git-hook dispatcher; BMAD v6.12.1 integration.
- Pre-commit base + stack fragments; CI templates (eos-core, ci-python, ci-node); Renovate seed; unit tests + selftest.
