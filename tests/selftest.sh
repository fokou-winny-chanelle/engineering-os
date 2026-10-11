#!/usr/bin/env sh
# End-to-end self-test for engineering-os. Usage: tests/selftest.sh [--full]
#   default : unit tests, ruff, shellcheck, budgets, init into fixtures, actionlint, pre-commit config validation,
#             global git-hook dispatcher (secret blocked, bad commit message blocked)
#   --full  : also runs the generated pre-commit hooks end-to-end on a fixture (downloads hook environments)
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
eos="python3 $here/bin/eos.py"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
ok() { printf '  ok  %s\n' "$1"; }
has() { command -v "$1" >/dev/null 2>&1; }

echo "== unit tests"
if python3 -m unittest discover -s "$here/tests" >/dev/null 2>&1; then ok "unittest"; else python3 -m unittest discover -s "$here/tests"; exit 1; fi
echo "== static checks"
if has ruff; then ruff check "$here/bin/eos.py" -q && ok "ruff"; elif has uvx; then uvx -q ruff@0.16.10 check "$here/bin/eos.py" -q && ok "ruff"; fi
if has shellcheck; then shellcheck "$here"/bootstrap.sh "$here"/tests/selftest.sh "$here"/tests/fixtures/*.sh "$here"/git-hooks/* && ok "shellcheck"; else echo "  skip shellcheck (not installed)"; fi
$eos budget >/dev/null && ok "pack budgets"
$eos library lint >/dev/null && ok "library lint (deep refs: format, size, sources, dates, injection)"
$eos vendor check >/dev/null && ok "vendor check (pinned, licensed, unchanged, reviewed)"
$eos mcp list | grep -q "^  debug " && ok "mcp profiles (debug profile present)"
if POSTGRES_MCP_URL="postgresql://ro@prod.example.com/app" HOME="$tmp" $eos mcp run postgres </dev/null >/dev/null 2>&1; then
  echo "postgres MCP guard did not refuse a production host"; exit 1
else ok "postgres MCP guard refuses a non-dev host"; fi

echo "== init into fixtures"
mk() { mkdir -p "$tmp/$1" && git -C "$tmp/$1" init -q -b main && git -C "$tmp/$1" config user.email t@example.com && git -C "$tmp/$1" config user.name t; }
mk mono; mkdir -p "$tmp/mono/apps/api" "$tmp/mono/apps/web"
printf '[project]\nname="api"\nversion="0.1.0"\ndependencies=["fastapi"]\n' > "$tmp/mono/apps/api/pyproject.toml"
printf '{"name":"web","private":true,"scripts":{"lint":"echo lint","typecheck":"echo tc","test":"echo test"},"dependencies":{"next":"16.4.0"}}\n' > "$tmp/mono/apps/web/package.json"
: > "$tmp/mono/apps/web/next.config.ts"; : > "$tmp/mono/apps/web/pnpm-lock.yaml"
mk flask; printf '[project]\nname="svc"\nversion="0.1.0"\ndependencies=["flask"]\n' > "$tmp/flask/pyproject.toml"
mk go; printf 'module example.com/x\n' > "$tmp/go/go.mod"
mk expo; printf '{"expo":{"name":"app"}}\n' > "$tmp/expo/app.json"; : > "$tmp/expo/pnpm-lock.yaml"
printf '{"name":"app","private":true,"scripts":{"lint":"echo lint","typecheck":"echo tc","test":"echo test"}}\n' > "$tmp/expo/package.json"
mk flutter; printf 'name: app\ndependencies:\n  flutter:\n    sdk: flutter\n' > "$tmp/flutter/pubspec.yaml"
for p in mono flask go expo flutter; do
  $eos init "$tmp/$p" --tools all --yes >/dev/null
  (cd "$tmp/$p" && python3 .eos/bin/eos.py check >/dev/null) && ok "init + check: $p"
  if has pre-commit; then pre-commit validate-config "$tmp/$p/.pre-commit-config.yaml" >/dev/null && ok "pre-commit config valid: $p"; fi
  if has actionlint; then actionlint "$tmp/$p"/.github/workflows/*.yml && ok "actionlint: $p"; fi
done
grep -q '"nextjs": "apps/web"' "$tmp/mono/.eos/manifest.json" && ok "monorepo detection"
grep -q '"profile": "mobile"' "$tmp/expo/.eos/manifest.json" && grep -q '"react-native-expo"' "$tmp/expo/.eos/manifest.json" && ok "expo -> mobile profile"
[ -f "$tmp/flutter/.github/workflows/ci-flutter.yml" ] && ok "flutter stack + CI"

echo "== v0.5: adopt, navigator, workspace"
sh "$here/tests/fixtures/make_messy.sh" "$tmp/messy" >/dev/null
$eos adopt "$tmp/messy" --yes --tools all --no-baseline >/dev/null && (cd "$tmp/messy" && python3 .eos/bin/eos.py check >/dev/null) && ok "adopt messy repo + check"
grep -q "Never touch app/billing/legacy.py" "$tmp/messy/AGENTS.md" && [ -f "$tmp/messy/.eos/suggested/.pre-commit-config.yaml" ] && ok "adopt kept the user's rules and configs"
(cd "$tmp/messy" && python3 .eos/bin/eos.py next --brief | grep -q "^Next: ") && ok "eos next (project copy, no EOS_HOME needed)"
sh "$here/tests/fixtures/make_workspace.sh" "$tmp/ws" >/dev/null
$eos init "$tmp/ws/api" --yes --tools cursor,cline >/dev/null && $eos workspace init --dir "$tmp/ws" --name shop >/dev/null
[ -f "$tmp/ws/shop.code-workspace" ] && grep -q "this repo = \`api\`" "$tmp/ws/api/AGENTS.md" && ok "workspace init (4 repos)"
$eos workspace status --dir "$tmp/ws" | grep -q "infra" && ok "workspace status"

echo "== v0.6: lanes, verify, escape hatches, stats"
f="$tmp/flask"
(cd "$f" && git add -A && git commit -qm "chore: eos" --no-verify && git switch -qc feat/x)
printf '# Docs\n' > "$f/README.md"
(cd "$f" && python3 .eos/bin/eos.py lane | grep -q "^Lane: trivial") && ok "lane: docs-only change is trivial"
mkdir -p "$f/app/auth" && printf 'def login():\n    return 1\n' > "$f/app/auth/login.py"
(cd "$f" && python3 .eos/bin/eos.py lane | grep -q "^Lane: risky") && ok "lane: auth change is risky"
(cd "$f" && python3 .eos/bin/eos.py verify --dry-run | grep -q "full check") && ok "verify: risky lane runs the full check"
(cd "$f" && git stash -qu && python3 .eos/bin/eos.py spike try >/dev/null && python3 .eos/bin/eos.py lane | grep -q "^Lane: spike") && ok "spike branch"
(cd "$f" && python3 .eos/bin/eos.py stats | grep -q "1 spikes") && ok "stats counts escapes"
rc=0; printf '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | (cd "$f" && python3 .eos/bin/hook.py claude-tool 2>/dev/null) || rc=$?
[ "$rc" -eq 2 ] && ok "hook launcher denies secret reads"

echo "== global git-hook dispatcher"
if has pre-commit && has gitleaks; then
  gcfg="$tmp/gitconfig"; printf '[core]\n\thooksPath = %s\n[user]\n\temail = t@example.com\n\tname = t\n' "$here/git-hooks" > "$gcfg"
  mk hooks; cd "$tmp/hooks"
  cat > msgcheck.py <<'PY'
import re, sys
msg = open(sys.argv[1], encoding="utf-8").read()
sys.exit(0 if re.match(r"^(feat|fix|chore|docs|test|refactor)(\([\w-]+\))?!?: ", msg) else 1)
PY
  cat > .pre-commit-config.yaml <<'YAML'
repos:
  - repo: local
    hooks:
      - id: msg
        name: conventional commit message
        entry: python3 msgcheck.py
        language: system
        stages: [commit-msg]
YAML
  pre-commit validate-config .pre-commit-config.yaml
  git add msgcheck.py
  git add .pre-commit-config.yaml
  if GIT_CONFIG_GLOBAL="$gcfg" git commit -qm "chore: config"; then ok "good commit passes"; else echo "  FAIL good commit rejected"; exit 1; fi
  # A random, fake GitHub-style token generated at runtime, so no secret-looking string is stored in this repo.
  fake="ghp_$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36)))')"
  printf 'GITHUB_TOKEN=%s\n' "$fake" > leak.txt
  git add leak.txt
  if GIT_CONFIG_GLOBAL="$gcfg" git commit -qm "chore: leak" >/dev/null 2>&1; then echo "  FAIL secret was committed"; exit 1; else ok "secret blocked by global gitleaks"; fi
  git rm -q --cached leak.txt; rm leak.txt; echo x > a.txt; git add a.txt
  if GIT_CONFIG_GLOBAL="$gcfg" git commit -qm "bad message" >/dev/null 2>&1; then echo "  FAIL bad message accepted"; exit 1; else ok "commit-msg delegated to repo pre-commit"; fi
  cd "$here"
else
  echo "  skip (needs pre-commit and gitleaks)"
fi

echo "== security scaffolds"
fail() { echo "  FAIL $1"; exit 1; }
mk sec; printf '[project]\nname="svc"\nversion="0.1.0"\ndependencies=["flask"]\n' > "$tmp/sec/pyproject.toml"
$eos init "$tmp/sec" --tools cursor --yes >/dev/null
if $eos scaffold security "$tmp/sec" >/dev/null && $eos scaffold security-tests "$tmp/sec" >/dev/null; then ok "security + security-tests scaffolds render"; else fail "security scaffolds"; fi
if has actionlint; then actionlint "$tmp/sec/.github/workflows/security.yml" && ok "actionlint: security.yml (semgrep job)"; fi
if [ "${1:-}" = "--full" ]; then
  sg=""; if has semgrep; then sg="semgrep"; elif has uvx; then sg="uvx -q semgrep"; fi
  if [ -n "$sg" ]; then
    mkdir -p "$tmp/sg" && cp "$here/core/scaffold/security/semgrep.yml" "$tmp/sg/eos-security.yml" && cp "$here"/tests/semgrep/* "$tmp/sg/"
    cp "$here/core/scaffold/db-safety/semgrep-data.yml" "$tmp/sg/eos-data.yml"
    cp "$here/core/scaffold/ops/semgrep-ops.yml" "$tmp/sg/eos-ops.yml"
    cp "$here/core/scaffold/web-security/semgrep-frontend.yml" "$tmp/sg/eos-frontend.yml"
    cp "$here/core/scaffold/mobile/semgrep-mobile.yml" "$tmp/sg/eos-mobile.yml"
    cp "$here/core/scaffold/llm/semgrep-llm.yml" "$tmp/sg/eos-llm.yml"
    cp "$here/core/scaffold/analytics/semgrep-analytics.yml" "$tmp/sg/eos-analytics.yml"
    if $sg --test --metrics=off "$tmp/sg" >/dev/null 2>&1; then ok "semgrep rules pass their ruleid/ok fixtures (security + data + ops + frontend + mobile + llm + analytics)"; else fail "semgrep --test"; fi
    if SEMGREP="$sg" python3 "$here/tests/semgrep_generic_check.py" "$here/core/scaffold/db-safety/semgrep-data.yml" "$here/tests/semgrep-generic" >/dev/null; then ok "generic semgrep rules (*.sql, *.prisma) pass their fixtures"; else fail "generic semgrep fixtures"; fi
    if $sg scan --config "$tmp/sec/.semgrep/" --error --metrics=off --quiet "$tmp/sec" >/dev/null 2>&1; then ok "semgrep: generated security templates are clean"; else fail "semgrep scan of templates"; fi
  else echo "  skip semgrep rule tests (needs semgrep or uvx)"; fi
  if has uvx; then
    if (cd "$tmp/sec" && uvx -q --with pytest python -m pytest -q -p no:cacheprovider tests/security >/dev/null); then ok "security-tests templates pass (authz matrix skips until wired)"; else fail "security-tests templates"; fi
  fi
fi

echo "== api-contract scaffold"
if $eos scaffold api-contract "$tmp/sec" >/dev/null && [ -f "$tmp/sec/.spectral.yaml" ]; then ok "api-contract scaffold renders (Spectral, oasdiff, Schemathesis)"; else fail "api-contract scaffold"; fi
if has actionlint; then actionlint "$tmp/sec/.github/workflows/api-contract.yml" "$tmp/sec/.github/workflows/api-fuzz.yml" && ok "actionlint: api-contract.yml, api-fuzz.yml"; fi
if [ "${1:-}" = "--full" ] && has npx; then
  sv=$(sed -n 's/^"spectral-cli" = "\([^"]*\)".*/\1/p' "$here/versions.toml")
  if SPECTRAL="npx --yes @stoplight/spectral-cli@$sv" python3 "$here/tests/spectral_check.py" "$tmp/sec/.spectral.yaml" "$here/tests/spectral" >/dev/null 2>&1; then ok "Spectral eos rules pass their fixtures (rendered ruleset)"; else fail "spectral fixtures"; fi
fi

echo "== testing scaffolds and gates (stage 5)"
for k in quarantine load-k6 mutation property-python; do $eos scaffold "$k" "$tmp/sec" >/dev/null || fail "scaffold $k"; done
[ -f "$tmp/sec/tests/quarantine.json" ] && [ -f "$tmp/sec/load/load.js" ] && ok "testing scaffolds render (quarantine, k6, mutation, Hypothesis)"
if has actionlint; then actionlint "$tmp/sec/.github/workflows/load.yml" "$tmp/sec/.github/workflows/mutation.yml" && ok "actionlint: load.yml, mutation.yml"; fi
if has k6; then (cd "$tmp/sec" && k6 inspect load/smoke.js >/dev/null && k6 inspect load/load.js >/dev/null) && ok "k6 inspect: smoke.js, load.js"; fi
$eos quarantine add "tests/test_x.py::test_y" --dir "$tmp/sec" --reason flaky --owner @me --issue "#1" >/dev/null && $eos quarantine check --dir "$tmp/sec" >/dev/null && ok "quarantine add + check"
(cd "$tmp/sec" && python3 .eos/bin/eos.py mutation-plan >/dev/null) && ok "mutation-plan (project copy)"

echo "== db-safety scaffold"
if $eos scaffold db-safety "$tmp/sec" >/dev/null && [ -f "$tmp/sec/scripts/db/schema_lint.sql" ]; then ok "db-safety scaffold renders"; else fail "db-safety scaffold"; fi
if has actionlint; then actionlint "$tmp/sec/.github/workflows/db-safety.yml" && ok "actionlint: db-safety.yml"; fi
if [ -n "${EOS_TEST_PG_DSN:-}" ] && has psql; then
  psql "$EOS_TEST_PG_DSN" -q -c "DROP SCHEMA IF EXISTS eos_st CASCADE; CREATE SCHEMA eos_st; CREATE TABLE eos_st.p (id bigint PRIMARY KEY); CREATE TABLE eos_st.c (id bigint PRIMARY KEY, p_id bigint REFERENCES eos_st.p);" >/dev/null 2>&1
  if psql "$EOS_TEST_PG_DSN" -v ON_ERROR_STOP=1 -f "$tmp/sec/scripts/db/schema_lint.sql" >/dev/null 2>&1; then rc=0; else rc=$?; fi
  psql "$EOS_TEST_PG_DSN" -q -c "DROP SCHEMA eos_st CASCADE" >/dev/null 2>&1
  if [ "$rc" = 3 ]; then ok "schema_lint.sql fails on an unindexed foreign key"; else fail "schema_lint.sql (rc=$rc)"; fi
else echo "  skip schema_lint.sql run (set EOS_TEST_PG_DSN and install psql)"; fi

echo "== operations scaffolds and gates (stage 6)"
for k in ops flags otel-python docker-python iac; do $eos scaffold "$k" "$tmp/sec" >/dev/null || fail "scaffold $k"; done
[ -f "$tmp/sec/ops/alerts/slo-burn-rate.rules.yml" ] && [ -f "$tmp/sec/app/telemetry.py" ] && ok "ops scaffolds render (SLOs + generated alerts, flags, OpenTelemetry, health tests, IaC)"
if has actionlint; then actionlint "$tmp/sec/.github/workflows/ops.yml" "$tmp/sec/.github/workflows/container.yml" "$tmp/sec/.github/workflows/iac.yml" && ok "actionlint: ops.yml, container.yml, iac.yml"; fi
$eos ops check --dir "$tmp/sec" >/dev/null && $eos ops alerts --check --dir "$tmp/sec" >/dev/null && ok "eos ops check + alerts --check on fresh scaffolds"
(cd "$tmp/sec" && python3 .eos/bin/eos.py ops budget >/dev/null) && ok "eos ops budget (project copy)"
if has promtool; then (cd "$tmp/sec" && promtool check rules ops/alerts/slo-burn-rate.rules.yml >/dev/null && promtool test rules ops/alerts/tests/*.yml >/dev/null) && ok "promtool: generated burn-rate rules parse and their unit tests pass"; else echo "  skip promtool (not installed; the ops workflow runs it)"; fi
if has hadolint; then (cd "$tmp/sec" && hadolint Dockerfile) && ok "hadolint: rendered Dockerfile is clean"; fi
if [ "${1:-}" = "--full" ] && [ -n "${sg:-}" ]; then
  if $sg scan --config "$tmp/sec/.semgrep/" --error --metrics=off --quiet "$tmp/sec/app" >/dev/null 2>&1; then ok "semgrep (security + ops rules): generated app templates log no secrets"; else fail "semgrep scan of ops templates"; fi
fi

echo "== frontend scaffolds and gates (stage 7)"
mk web; printf '{"name":"web","scripts":{"build":"next build","start":"next start"},"dependencies":{"next":"16.4.0","react":"19.2.0"}}\n' > "$tmp/web/package.json"
mkdir -p "$tmp/web/src/app" && printf 'export default function Page() {\n  return <h1>Hi</h1>;\n}\n' > "$tmp/web/src/app/page.tsx" && echo '{}' > "$tmp/web/package-lock.json"
$eos init "$tmp/web" --tools cursor --yes --no-precommit >/dev/null
for k in lighthouse eslint-next web-security i18n e2e-node; do $eos scaffold "$k" "$tmp/web" >/dev/null || fail "scaffold $k"; done
[ -f "$tmp/web/src/proxy.ts" ] && [ -f "$tmp/web/src/lib/csp.ts" ] && [ -f "$tmp/web/lighthouserc.json" ] && ok "frontend scaffolds render (Lighthouse CI, eslint-next, CSP proxy + header test, fr/en i18n)"
if has actionlint; then actionlint "$tmp/web/.github/workflows/lighthouse.yml" && ok "actionlint: lighthouse.yml"; fi
$eos i18n check --dir "$tmp/web" >/dev/null && ok "eos i18n check: shipped fr/en catalogs are complete"
python3 - "$tmp/web/messages/en.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["orders"]["extra"] = "Extra"; json.dump(d, open(p, "w"))
PY
if $eos i18n check --dir "$tmp/web" >/dev/null; then fail "i18n check missed a key"; else ok "eos i18n check fails on a key missing in fr"; fi
mkdir -p "$tmp/web/.next/static/chunks" && printf 'console.log(1)\n' > "$tmp/web/.next/static/chunks/a.js"
$eos bundle-size --dir "$tmp/web" --update >/dev/null && $eos bundle-size --dir "$tmp/web" >/dev/null && ok "eos bundle-size: baseline + ratchet"
if [ "${1:-}" = "--full" ] && [ -n "${sg:-}" ]; then
  if $sg scan --config "$tmp/web/.semgrep/" --error --metrics=off --quiet "$tmp/web/src" "$tmp/web/e2e" >/dev/null 2>&1; then ok "semgrep (frontend rules): generated web templates are clean"; else fail "semgrep scan of web templates"; fi
fi

echo "== design tokens and gates (stage 8)"
$eos scaffold design-tokens "$tmp/web" >/dev/null || fail "scaffold design-tokens"
[ -f "$tmp/web/design/tokens/base.tokens.json" ] && [ -f "$tmp/web/e2e/design-critique.spec.ts" ] && ok "design-tokens scaffold renders (DTCG light + dark, Style Dictionary build, critique screenshots)"
$eos design check --dir "$tmp/web" >/dev/null && ok "eos design check: scaffold tokens are valid DTCG and every pair passes 4.5:1"
python3 - "$tmp/web/design/tokens/dark.tokens.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["color"]["on-bg"] = {"$value": "{color.bg}"}; json.dump(d, open(p, "w"))
PY
if $eos design check --dir "$tmp/web" >/dev/null; then fail "design check missed a 1:1 contrast pair"; else ok "eos design check fails when dark text matches its background"; fi
$eos design contrast "#767676" "#ffffff" >/dev/null && ok "eos design contrast: #767676 on white passes 4.5:1"
$eos new critique "Home" --dir "$tmp/web" >/dev/null && ls "$tmp/web"/docs/design/critiques/*-home.md >/dev/null && ok "eos new critique writes a rubric sheet"

echo "== design studio (opt-in; quarantined sources)"
if $eos studio on --dir "$tmp/web" >/dev/null 2>&1; then fail "studio turned on with unsigned sources"; else ok "eos studio on refuses sources pending human sign-off"; fi
[ ! -d "$tmp/web/.eos/studio" ] && ok "no studio files without sign-off (zero always-on cost)"
$eos design ab init "$tmp/ab" --allow-pending >/dev/null && [ -f "$tmp/ab/arm-b/.eos/studio/README.md" ] && [ ! -d "$tmp/ab/arm-a/.eos/studio" ] && ok "eos design ab init: two identical arms, studio only in arm B"
EOS_STUDIO_SANDBOX=none $eos design ab score "$tmp/ab" --seed s >/dev/null && [ -f "$tmp/ab/.ab-key.json" ] && [ -f "$tmp/ab/scoring/shoot.sh" ] && ok "eos design ab score: blinded copies, critique sheets, screenshot script"
if $eos design ab report "$tmp/ab" >/dev/null 2>&1; then fail "ab report decided without scores"; else ok "eos design ab report refuses unscored sheets"; fi

echo "== mobile gates (stage 9)"
mkdir -p "$tmp/mob" && cd "$tmp/mob" && git init -q -b main && cd "$here"
printf '{"expo":{"name":"f","android":{"package":"cm.example.f","allowBackup":false},"runtimeVersion":{"policy":"appVersion"}}}\n' >"$tmp/mob/app.json"
printf '{"name":"f","dependencies":{"expo":"~57.0.0"}}\n' >"$tmp/mob/package.json"
$eos mobile check --dir "$tmp/mob" >/dev/null && ok "eos mobile check passes a safe Expo config"
$eos init "$tmp/mob" --yes --tools cursor --no-precommit >/dev/null 2>&1 || fail "init mobile fixture"
if $eos scaffold mobile "$tmp/mob" >/dev/null 2>&1 && grep -q "appId: cm.example.f" "$tmp/mob/.maestro/smoke.yaml"; then ok "mobile scaffold renders (MASVS Semgrep rules, Maestro flows, budget doc)"; else fail "scaffold mobile"; fi
if has actionlint; then actionlint "$tmp/mob/.github/workflows/mobile-e2e.yml" && ok "actionlint accepts the mobile E2E workflow"; fi
mkdir -p "$tmp/mob/android/app/src/main"
printf '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:allowBackup="false" android:debuggable="true"/></manifest>\n' >"$tmp/mob/android/app/src/main/AndroidManifest.xml"
if $eos mobile check --dir "$tmp/mob" >/dev/null 2>&1; then fail "mobile check missed debuggable"; else ok "eos mobile check fails a debuggable release manifest (MOB003)"; fi

echo "== LLM app gates (stage 10)"
mkdir -p "$tmp/llm" && cd "$tmp/llm" && git init -q -b main && cd "$here"
printf '[project]\nname = "x"\nversion = "0.1.0"\ndependencies = ["flask"]\n' >"$tmp/llm/pyproject.toml"
mkdir -p "$tmp/llm/app" && : >"$tmp/llm/app/__init__.py"
$eos init "$tmp/llm" --yes --tools cursor --no-precommit >/dev/null 2>&1 || fail "init llm fixture"
if $eos scaffold llm-evals "$tmp/llm" >/dev/null 2>&1 && [ -f "$tmp/llm/evals/llm/gate.json" ]; then ok "llm-evals scaffold renders (prompt file, cases, runner, gate, workflow, Semgrep rules)"; else fail "scaffold llm-evals"; fi
$eos llm check --dir "$tmp/llm" >/dev/null && ok "eos llm check passes the generated prompt file"
if (cd "$tmp/llm" && python3 evals/llm/run_evals.py --fake >/dev/null) && $eos llm gate --dir "$tmp/llm" >/dev/null; then ok "eval runner (--fake) + eos llm gate pass end to end"; else fail "llm eval pipeline"; fi
if has actionlint; then actionlint "$tmp/llm/.github/workflows/llm-evals.yml" && ok "actionlint accepts the llm-evals workflow"; fi
$eos scaffold llm-otel "$tmp/llm" >/dev/null 2>&1 && python3 -m py_compile "$tmp/llm/app/genai_otel.py" && ok "llm-otel scaffold renders a compilable GenAI tracing helper"
sed 's/^owner: support .*$//' "$tmp/llm/prompts/support-answer.prompt.md" >"$tmp/llm/prompts/broken.prompt.md"
if $eos llm check --dir "$tmp/llm" >/dev/null 2>&1; then fail "llm check missed a missing owner"; else ok "eos llm check fails a prompt without an owner (LLM002) and a duplicate id (LLM009)"; fi

echo "== data and ML gates (stage 11)"
mkdir -p "$tmp/data" && cd "$tmp/data" && git init -q -b main && cd "$here"
printf '[project]\nname = "x"\nversion = "0.1.0"\ndependencies = ["flask"]\n' >"$tmp/data/pyproject.toml"
$eos init "$tmp/data" --yes --tools cursor --no-precommit >/dev/null 2>&1 || fail "init data fixture"
if $eos scaffold analytics "$tmp/data" >/dev/null 2>&1 && $eos scaffold ml "$tmp/data" >/dev/null 2>&1 && [ -f "$tmp/data/contracts/payments-daily.odcs.yaml" ]; then ok "analytics + ml scaffolds render (dbt project, ODCS contract, workflow, Semgrep rules, checklists)"; else fail "scaffold analytics/ml"; fi
$eos data check --dir "$tmp/data" >/dev/null && ok "eos data check passes the generated contract"
if has actionlint; then actionlint "$tmp/data/.github/workflows/analytics.yml" && ok "actionlint accepts the analytics workflow"; fi
printf '{"cells":[{"cell_type":"code","execution_count":1,"metadata":{},"outputs":[{"output_type":"stream","name":"stdout","text":["1"]}],"source":["print(1)"]}],"metadata":{},"nbformat":4,"nbformat_minor":5}\n' >"$tmp/data/scratch.ipynb"
(cd "$tmp/data" && git add scratch.ipynb)
if $eos data check --dir "$tmp/data" >/dev/null 2>&1; then fail "data check missed notebook outputs"; else ok "eos data check fails a committed notebook with outputs (NB001/NB002)"; fi
printf 'customer_id,event_at,is_fraud\nc1,2026-01-01T00:00:00Z,0\nc2,2026-01-02T00:00:00Z,1\n' >"$tmp/data/train.csv"
printf 'customer_id,event_at,is_fraud\nc2,2026-01-01T12:00:00Z,1\n' >"$tmp/data/test.csv"
if $eos data split --train "$tmp/data/train.csv" --test "$tmp/data/test.csv" --id customer_id --time event_at >/dev/null 2>&1; then fail "data split missed leakage"; else ok "eos data split fails a shared customer and overlapping time (SPL001/SPL003)"; fi
if [ "${1:-}" = "--full" ] && has uv; then
  if (cd "$tmp/data/analytics" && uv run -q --no-project --with "dbt-core==$(sed -n 's/^"dbt-core" = "\([^"]*\)".*/\1/p' "$here/versions.toml")" --with "dbt-duckdb==$(sed -n 's/^"dbt-duckdb" = "\([^"]*\)".*/\1/p' "$here/versions.toml")" dbt build --profiles-dir . --target ci >/dev/null 2>&1); then ok "dbt build passes on the generated project (tests, unit test, contract, reconciliation)"; else fail "dbt build of analytics scaffold"; fi
fi

if [ "${1:-}" = "--full" ] && has pre-commit; then
  echo "== full pre-commit run on fixture (slow)"
  cd "$tmp/flask" && git checkout -q -b feat/selftest && git add -A && SKIP=py-typecheck,py-tests pre-commit run --all-files >/dev/null && ok "pre-commit all hooks pass on fresh init"
  cd "$here"
fi
echo "selftest: all good"
