# Knowledge library: status at v0.7.0 (11 October 2026)

This is the summary of the deep knowledge library after its eleven stages. It covers what exists, how big it is, what each area enforces, and, in section 4, **one consolidated checklist of everything a human still has to review**, in priority order. Design of the library: `docs/LIBRARY.md`. Per-area sources and decisions: `docs/research/v0.7-*-sources.md`.

## 1. Cost to agents: unchanged

The library is read on demand. Always-on context is the same as before stage 1 (measured with `tests/bench/measure_context.py`, default `web-app` profile, 11 October 2026):

| Context | Cursor | Cline | Claude Code | Codex |
|---|---|---|---|---|
| session start | 1,884 | 1,860 | 1,907 | 1,397 |
| path rule, `app/api/route.py` | 2,864 | 2,899 | 2,899 | n/a |
| path rule, `app/page.tsx` | 2,240 | 2,261 | 2,261 | n/a |

The route rule is 8 tokens larger than before stage 1 (the words "deep references" in the pointer line, stage 1). Packs stay ≤ 1,200 tokens. Refs aim for ≤ 2,500 and `eos library lint` fails above 3,000.

## 2. Areas

134 ref files, ~246,600 tokens in total (`eos library lint --strict`: OK, 0 warnings). Token counts use eos's own estimator (`eos budget`).

| Area | Stage | Refs | Tokens | Largest | Pointed to from (packs) | Eval tasks | Coverage pack → pack+refs |
|---|---|---|---|---|---|---|---|
| architecture (+ 4 top-level refs) | 1 | 11 + 4 | 19,916 + 6,795 | 2,415 | architecture, topology, backend, api-design, data-modeling, performance-scale | 8 | 15% → 100% |
| security | 2 | 13 | 22,133 | 2,113 | security, agent-security, backend, api-design, discovery, data-modeling, infra-devops, testing-qa, mobile, release | 12 | 26% → 100% |
| data | 3 | 12 | 26,094 | 2,494 | data-modeling, data-ml, backend, architecture, performance-scale, operations, infra-devops, testing-qa | 14 | 33% → 100% |
| api | 4 | 11 | 22,896 | 2,478 | api-design, backend, architecture, testing-qa, mobile | 14 | 27% → 100% |
| testing | 5 | 12 | 17,784 | 1,930 | testing-qa, release, performance-scale, mobile, agent-security | 15 | 43% → 100% |
| ops | 6 | 12 | 19,258 | 1,915 | operations, infra-devops, release, architecture, performance-scale | 19 | 51% → 100% |
| frontend | 7 | 12 | 22,701 | 2,165 | frontend, ux-design, design-direction, security, performance-scale, testing-qa, mobile | 20 | 44% → 100% |
| design | 8 | 12 | 22,106 | 2,034 | design-direction, ux-design, frontend, mobile | 20 | 46% → 100% |
| mobile | 9 | 12 | 24,016 | 2,521 | mobile | 20 | 53% → 100% |
| llm | 10 | 11 | 20,087 | 2,013 | agent-security, data-ml, operations | 20 | 41% → 100% |
| analytics | 11 | 7 | 13,088 | 2,082 | data-ml | 14 | 33% → 100% |
| ml | 11 | 5 | 9,749 | 2,477 | data-ml | 13 | 58% → 100% |
| **all** | | **134** | **~246,600** | | | **189** | **41% → 100%** |

Notes:
- Coverage is a proxy: the share of rubric points present in the context an agent would have. The rubric and the refs share an author, so 100% shows availability, not better answers. No agent was run live on the build box. `eos library eval tests/evals --responses DIR` scores real answers.
- `mobile/security-masvs` is 2,521 tokens, slightly over the 2,500 target but well under the 3,000 limit.

Vendored third-party material (quarantined, never installed until a human signs off): 8 sources (`eos vendor list`): owasp-cheatsheets (16 files, ~74k tokens), owasp-llm-prompt-injection (2 files, ~12k, held), anthropic-frontend-design (~2.3k), vercel-web-interface-guidelines (~2k), impeccable-knowledge (47 files, ~108k, 1 held finding), ui-ux-pro-max-knowledge (43 files, ~12.8k), ui-ux-pro-max-scripts (code, sandbox only), emil-review-animations (~4.5k). The design studio that uses some of them is opt-in (`eos studio`) and outside every lane.

## 3. Checks per area

All `eos` gates run in-process (no network, milliseconds) unless marked CI. Lanes: trivial and spike lanes run none of them. Standard runs them on changed files. Risky, one-way-door and `--full` run them on everything.

| Area | eos gates (rule ids) | Scaffolds (`eos scaffold …`) | Semgrep rules | CI-only tools |
|---|---|---|---|---|
| architecture | `eos check` (packs, budgets, drift), `eos topology`, lane classification | boundaries (import-linter), codeowners | – | – |
| security | `eos guard` agent hooks, `eos vendor check` (pins, hashes, licences, injection scan), test-integrity | security, security-tests (webhook HMAC, authz matrix), web-security (CSP, headers) | eos-security, eos-frontend | Semgrep, dependency review, CodeQL, SBOM (gitleaks runs in pre-commit) |
| data | migrations and destructive SQL are one-way-door in `eos lane` | db-safety (Squawk, schema lint) | eos-data (Python + generic SQL/Prisma) | Squawk |
| api | public contract changes (OpenAPI, proto, GraphQL, ODCS) are one-way-door | api-contract (Spectral, oasdiff, Schemathesis) | – | Spectral, oasdiff, Schemathesis |
| testing | `eos diff-coverage`, `eos quarantine`, `eos test-integrity`, `eos mutation-plan/score` | tests-python, property-python/node, mutation, load-k6, e2e-node, quarantine | – | mutmut/Stryker, k6, Playwright |
| ops | `eos ops check` (SLOs, alerts→runbooks, flags expiry, generated burn-rate rules) | ops, otel-python/node, flags, docker-lint, docker-python/node, compose, iac, release, reproducible | eos-ops (secrets/PII in logs) | promtool, hadolint, checkov, OpenTofu plan |
| frontend | `eos i18n check`, `eos bundle-size` ratchet | eslint-next, lighthouse, i18n, web-security, e2e-node | eos-frontend | Lighthouse CI, Playwright |
| design | `eos design check` (DTCG schema, WCAG contrast, generic-look lint), `eos design ab` | design-tokens | – | – |
| mobile | `eos mobile check` (MOB rules: backup, cleartext, debuggable, exported, ATS, public env), `eos mobile size` ratchet | mobile (Maestro flows, emulator workflow, budget) | eos-mobile | Maestro on emulator |
| llm | `eos llm check` (LLM001–LLM011), `eos llm gate` (eval regressions) | llm-evals, llm-otel | eos-llm | real-model evals (same-repo PRs, nightly) |
| analytics | `eos data check` (DAT001–DAT008 ODCS contracts incl. breaking changes vs base) | analytics (dbt + DuckDB, contract, CI) | eos-analytics (PII in events) | dbt build |
| ml | `eos data check` (NB000–NB004 notebooks), `eos data split` (SPL001–SPL005) | ml (split checklist, model card, datasheet) | – | – |

## 4. Consolidated human review checklist (priority order)

Nothing below was self-approved. Each item names who should act and the exact command or file.

### P1. Security and money code to read line by line before a team relies on it
These are templates and rules that protect money and data. A security reviewer, and someone who owns payments, should read them:
1. **Webhook signature verification and authz tests**: `core/scaffold/security-tests/webhook_verify.py`, `test_webhook_verify.py.tmpl`, `test_authz_matrix.py`.
2. **Web hardening**: `core/scaffold/web-security/csp.ts`, `proxy.ts`, `security-headers.spec.ts`. Start the CSP as `Content-Security-Policy-Report-Only`.
3. **Semgrep rule sets** (pattern-based; they miss renamed variables and custom wrappers): `core/scaffold/security/semgrep.yml`, `web-security/semgrep-frontend.yml`, `db-safety/semgrep-data.yml`, `ops/semgrep-ops.yml`, `mobile/semgrep-mobile.yml`, `llm/semgrep-llm.yml` (the taint rule lists the sources it knows), `analytics/semgrep-analytics.yml`.
4. **eos's own guards**: `bin/eos.py` agent hooks (`eos guard`), the vendor injection scan, the studio sandbox, and the secret patterns (`LLM_SECRET_RX`, `DATA_SECRET_RX`), plus LLM007/LLM008 and NB003.
5. **Money refs and code**: `packs/ref/security/payments.md`, `packs/ref/mobile/auth-payments.md`, `packs/ref/data/keys-money-time.md`, `packs/ref/ml/fintech-risk.md`. Also the analytics scaffold's money definitions and reconciliation test (`core/scaffold/analytics/models/marts/fct_daily_payments.sql`, `tests/assert_daily_totals_reconcile.sql`: are refunds dated on the original attempt? do failed attempts count?), and `core/scaffold/llm-otel/genai_otel.py` cost estimation (empty price table; a human fills in prices and spend limits).
6. **Production changes stay human**: the IaC workflow never applies. Apply, DNS, restores and failovers need a named approver (GitHub environment with required reviewers).

### P2. Legal items (a lawyer or the owner decides)
1. **Licence (resolved in v0.7.1):** MIT for the repository; vendored sources and the CC BY 4.0-adapted API refs keep their own licences ([THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)).
2. **Cameroon Law No. 2024/017**: every quote comes from OCR of the official PDF (sections 5, 9, 44, plus cross-border and breach sections). Check them against the original in `security/privacy`, `llm/privacy-residency`, `analytics/product-events`, `analytics/privacy-anonymisation` and `ml/fintech-risk`.
3. **Credit scoring and automated decisions** (`ml/fintech-risk`): EU AI Act Annex III 5(b) and the Digital Omnibus dates (Regulation (EU) 2026/1744: Annex III obligations from 2 December 2027), CJEU C-634/21 SCHUFA, US Regulation B §1002.9, and CFPB Circular 2022-03 (withdrawn 12 May 2025).
4. **Consent for analytics** (`analytics/product-events`): the CNIL sheet 16 exemption conditions and Cameroon s.9 consent. Decide the consent banner and opt-out behaviour per market.
5. **Licences of tools named in refs**: k6 (AGPL-3.0, CLI in CI), Soda Core (Elastic License 2.0), the lakeFS server (Business Source License 1.1), Meta MMS (non-commercial), and the fraud handbook (CC BY-SA prose, GPL code; linked only).
6. **Attribution wording** in the adapted API refs (`packs/ref/api/*`, `## Attribution` sections) before a public release.
7. **Data residency and breach notification** (GDPR 72 h; Cameroon law) are legal calls; the ops and LLM refs give facts only.

### P3. Vendor sign-offs (8 sources, all pending)
Read the files under `packs/vendor/<id>/` (and `PROVENANCE.json`), then record the review yourself. `eos vendor check --strict` fails until every source is signed off or removed, so it is not yet a release gate.

```sh
python3 bin/eos.py vendor list
python3 bin/eos.py vendor review owasp-cheatsheets --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor review owasp-llm-prompt-injection --by "<your name>" --note "<what you checked>" \
    --accept-findings "<why the 19 quoted attack examples are safe to keep>"
python3 bin/eos.py vendor review anthropic-frontend-design --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor review vercel-web-interface-guidelines --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor review impeccable-knowledge --by "<your name>" --note "<what you checked>" \
    --accept-findings "<why the HTML comment template in skill/reference/document.md is harmless>"
python3 bin/eos.py vendor review ui-ux-pro-max-knowledge --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor review ui-ux-pro-max-scripts --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor review emil-review-animations --by "<your name>" --note "<what you checked>"
python3 bin/eos.py vendor check --strict
```

Notes: OWASP material is CC BY-SA 4.0 and stays separate and unmodified. Pointers to add after sign-off are listed in `docs/research/v0.7-security-sources.md`. `ui-ux-pro-max-knowledge` embeds Google Fonts metadata and Phosphor icon names. `emil-review-animations` is optional; drop it with `git rm -r packs/vendor/emil-review-animations` and remove it from `core/studio/studio.json`. Not signing off is a valid outcome: delete the source instead.

### P4. Thresholds to confirm (defaults from cited sources, not measured on your projects)
| Where | Default | Owner |
|---|---|---|
| `.eos/config.json` → `testing` | diff coverage 80% (90% on money/auth paths), quarantine ≤ 14 days, mutation score ≥ 60% | tech lead |
| `ops/slo.json`, `ops` config | example SLOs 99.5% / 99.0%, flags expire after 90 days, page vs ticket split, incident response times | whoever carries the pager |
| `lighthouserc.json` | 365 KiB script and 730 KiB total per route, LCP 2.5 s (lab), TBT 200 ms, CLS 0.1 | frontend lead (tune with field data) |
| `mobile` config | app-size ratchet +5% and +100 KB; no absolute budget by default | mobile lead |
| `evals/llm/gate.json` | placeholder pass rates; the 4-case dataset is a sample. Someone owns the first baseline (`eos llm gate --update`) | product owner of the LLM feature |
| `data` config, `eos data split` | NB004 500 KB; DAT005 personal-data name list; SPL004 99% purity on ≥ 50 rows | data lead |
| `design` config | contrast 4.5:1 (WCAG AA body text); generic-look lint as warnings | design lead |
| drift and fairness (refs only) | none set on purpose: choose from your own history and policy | data lead + compliance |

### P5. The design A/B test (decides whether the opt-in design studio stays)
No agent or model runs on the build box, so this one is for the maintainer to run:
```sh
python3 bin/eos.py design ab init /tmp/ab --allow-pending   # arm-a: our packs; arm-b: + studio (stamped PENDING-SIGN-OFF)
# one fresh agent session per arm, same PROMPT.md, the three specs in core/templates/design/ab/
python3 bin/eos.py design ab score /tmp/ab --shoot           # eos design check per screen, blinded X/Y copies, critique sheets
# a person scores the 12-row critique sheets blind
python3 bin/eos.py design ab report /tmp/ab                  # unblinds and applies the rule
```
Keep the studio only if all four hold: B's mean critique total ≥ A's + 2 (of 24); B wins at least 2 of 3 screens; no new 0 on gate rows 5, 7, 9, 10; B's `eos design check` errors ≤ A's. Otherwise drop it (the default). Details: `docs/research/v0.7-design-studio.md` §6.

### P6. Housekeeping
- Re-verify refs when `eos library lint` warns that one is past its `revisit_days`. LLM refs use 60–90 days; the rest use 180–365. Check dbt versions and EU AI Act dates sooner if the news moves.
- `versions.toml` pins were checked on 10–11 October 2026. Renovate or a manual bump keeps them fresh. dbt's v2 engine should be re-checked for Postgres support before moving the analytics scaffold off dbt-core v1.
