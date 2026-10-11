# The knowledge library (v0.7)

eos gives agents short rules all the time and deep knowledge only when they are doing that work. This file explains how that library is organised, loaded, kept current, checked and grown. Research behind it: `docs/research/v0.7-native-capabilities.md` (what the tools already do) and `docs/research/v0.7-external-sources.md` (what is worth importing).

## Four layers

| Layer | What | Where | When it is in context |
|---|---|---|---|
| 1. Rules | short, imperative standards | `packs/phases/*.md`, `packs/stacks/*/STACK.md` (≤ 1,200 tokens each) | phase packs as skills/intent rules when relevant; a path-rule slice (≤ 800) while editing matching files |
| 2. Deep references | decision guides, examples, anti-patterns, checks, sources | `packs/ref/<area>/<topic>.md` (≤ 3,000 tokens, target 2,500) | only when a pack points to one and the agent is doing that work |
| 3. Vendored material | the best external text, pinned and reviewed | `packs/vendor/<source>/` + `packs/vendor/PROVENANCE.json` | same as layer 2 (`vendor:<source>/<path>` pointers) |
| 4. Enforcement | the practices as automated checks | stack-pack linters, `eos` gates, lifecycle exit criteria | on every commit / CI run, zero tokens |

Always-on cost of layers 2 and 3 is zero: nothing about them appears in AGENTS.md, skill descriptions or path-rule slices. Measured in `tests/bench/results-v0.7.0-dev.json`: session-start context is unchanged (Cursor 1,884, Cline 1,860, Claude Code 1,907, Codex 1,397 tokens); a Python path rule grew by 8 tokens (the word "deep references" in the pointer line).

## Loading

1. A pack lists its refs in one section, `## Deep references`, as backticked ids: `` `architecture/caching` ``. That section is the only source of truth (`eos.deep_refs_of`), so a pointer costs about 5 tokens and cannot drift from a second copy.
2. The section sits after "Automated checks", so it is **not** in the edit-time path-rule slice; the slice's last line says the full pack has deep references.
3. `eos init` / `eos update` install a ref into `.eos/packs/ref/<area>/<topic>.md` only if a selected pack points to it, plus `.eos/packs/ref/INDEX.md` (one line per installed ref with its `read_when`). Vendored files travel with their licence file. Pre-v0.7 top-level refs (`topologies.md`, …) are always installed.
4. The agent reads the pack (as a skill or rule), sees the pointer, and reads only the ref it needs. Progressive disclosure, no tool-specific mechanism.

**Why not each tool's skill `references/` folder?** Cursor, Cline, Claude Code and Codex each read skills from different folders, and Cursor reads several of them without de-duplicating (see the native-capabilities research). eos writes one skill copy per project; a project-relative `.eos/packs/ref/` path works in every tool, including plain AGENTS.md readers, and keeps one copy of each ref.

## Ref format

```markdown
---
id: architecture/caching            # = path under packs/ref/, without .md
title: Caching layers
area: architecture                  # = folder
read_when: adding or debugging a cache …   # shown in INDEX.md; write the trigger, not the topic
verified: 2026-10-10                # the day every claim and link was checked
revisit_days: 365                   # 180 for fast-moving topics (prices, tool versions)
sources: ["https://…", "https://…"] # ≥ 2 https sources, each also listed under ## Sources
adapted_from: ["https://…"]        # optional: sources whose text was adapted (e.g. CC BY 4.0); needs ## Attribution
---
# Title
One paragraph: what this is for and the one idea to remember.
## Decision guide        (required: criteria, tables, numbers with their source)
## Examples              (concrete, small, realistic)
## Anti-patterns         (required: including "when NOT to")
## Checks                (required: how to verify or enforce it)
## Sources               (required)
## Attribution           (required with adapted_from: title, author, each adapted URL, licence link, "Changes: …")
```

Writing rules: plain English; decision criteria over descriptions; numbers only with a cited source (else describe the method to get your own number); no prices (cite the pricing page or say "unknown"); don't repeat the pack (the ref deepens it); write for an agent that already knows the textbook basics, so spend tokens on criteria, traps and examples.

## Currency

- `verified` + `revisit_days` per ref. `eos library lint` warns when a ref is overdue and fails on future dates; `--strict` makes overdue an error (use before a release).
- Re-verifying means re-opening every source, checking the facts quoted, and bumping `verified`. Broken links: `rg -o "https://[^ )\"'>\]]+" packs/ref | sort -u` and check each with curl (done for v0.7: all 200).
- Vendored files: `eos vendor check` warns when a source was fetched more than 365 days ago (`--max-age-days`).

## Checks (`eos library lint`, in pre-commit, selftest and CI)

- Ref files: required keys, id/area match the path, required sections, ≥ 2 https sources all listed under `## Sources`, size ≤ 3,000 tokens, valid and non-future `verified`, staleness, injection scan.
- Adapted text: when `adapted_from` is set, each URL must also be in `sources` and be credited under `## Attribution`, which must link the licence and say what changed (CC BY 4.0 requires attribution, a licence link and an indication of changes). Adapting is paraphrasing in our own words, not copying; copying whole files goes through `eos vendor` below. Allowed for adaptation: the vendoring allow-list minus share-alike (CC-BY-SA would make the ref share-alike too).
- Pointers: every id in a pack's `## Deep references` resolves to a ref file (or a vendored file of a vendored source); every area ref is pointed to by at least one pack (no orphans).
- Injection scan (`eos.scan_injection`, also used by `eos vendor`): instruction overrides, persona switches, `curl | sh`, exfiltration phrasing, hidden Unicode, instructions in HTML comments, long base64 blobs, links to remote scripts.

## Vendoring external material (`eos vendor`)

Import policy (details in the external-sources research):
1. Licence on the allow-list: MIT, Apache-2.0, BSD-2/3-Clause, ISC, CC0-1.0, CC-BY-4.0, CC-BY-SA-4.0. NC/ND, "all rights reserved" and no-licence sources are linked from refs, never copied.
2. Pinned to a full commit SHA; the licence file is copied too.
3. Injection scan must be clean, or a human records why each finding is benign (`--accept-findings`).
4. Per-file SHA-256 in `PROVENANCE.json`; vendored files are never edited in place (`vendor check` fails on any change or extra file).
5. **Quarantine until a named human signs off.** `vendor add` records `status: pending-human-sign-off` and an attribution line. While pending, a source is never installed into projects, `eos library lint` rejects pack pointers to it, and `eos vendor check` warns (`--strict` turns the warning into an error, for releases). Sign-off is `eos vendor review <id> --by <name> --note …`, run by a human, never by an agent. A source with injection-scan findings is refused unless it is added with `--hold` (kept quarantined with the findings recorded) or a human passes `--accept-findings '<why>'`; review of such a source also needs `--accept-findings`.
6. `packs/vendor/` is a risky lane: every change gets human review.
7. Token cost counted per file; prefer the smallest file that carries the value, and point to it like any ref (`` `vendor:<id>/<path>` ``).

```bash
eos vendor add anthropic-frontend-design --repo https://github.com/anthropics/skills \
  --ref <commit-sha> --path skills/frontend-design/SKILL.md --license Apache-2.0 --license-file skills/frontend-design/LICENSE.txt
eos vendor review anthropic-frontend-design --by fey --note "read in full; no instructions beyond design guidance"
eos vendor check            # CI: pinned, licensed, unchanged; warns while pending sign-off
eos vendor check --strict   # release: pending sign-off is an error
eos vendor update <id> --ref <new-sha>   # re-fetch, re-scan; review again
eos vendor list
```

Architecture (stage 1) vendors nothing: the best material is link-only (NC/ND or all rights reserved) or textbook knowledge models already have, so the refs are original text that cites it.

Security (stage 2) vendors 16 OWASP Cheat Sheets (CC-BY-SA-4.0, pinned `cb9fe01e`) as two sources, `owasp-cheatsheets` and `owasp-llm-prompt-injection` (held: its 19 scan findings are quoted attack examples a human must judge). Share-alike text stays unmodified in its own folder with its licence; eos refs cite it but never copy it. Both are **pending human sign-off**; the pointers to add after sign-off are listed in `docs/research/v0.7-security-sources.md`.

Data (stage 3) vendors nothing: the PostgreSQL manual is under the PostgreSQL Licence but is long and already well known to models, and the best practitioner material (squawk docs, vendor engineering blogs) is better cited than copied. The 12 `data/*` refs are original text that cites them (`docs/research/v0.7-data-sources.md`).

Testing (stage 5) vendors and adapts nothing: tool docs are cited, *Software Engineering at Google* is CC BY-NC-ND (link only), and the 12 `testing/*` refs are original text (`docs/research/v0.7-testing-sources.md`).

Operations (stage 6) vendors and adapts nothing: the Google SRE books are linked only (licence), OpenTelemetry, OpenFeature and FinOps Foundation docs (CC BY 4.0) are summarised and cited, PagerDuty's incident-response docs (Apache-2.0) are credited where their severity and role model is used, and the 12 `ops/*` refs are original text (`docs/research/v0.7-ops-sources.md`).

Frontend (stage 7) vendors and adapts nothing: Vercel's `agent-skills` was evaluated and fails the import policy (no LICENSE file in the repository; one skill loads unpinned remote instructions, a pattern the injection scan now flags as `remote-instructions`). react.dev and web.dev (CC BY 4.0) are cited, W3C and MDN pages are linked only, and the 12 `frontend/*` refs are original text (`docs/research/v0.7-frontend-sources.md`).

Design (stage 8) vendors two sources, both quarantined and **pending human sign-off**: Anthropic's `frontend-design` skill (Apache-2.0, LICENSE.txt copied, pinned `dbd4588f`) and Vercel's Web Interface Guidelines `command.md` (MIT, pinned `434b7f91`). No pack points to them until a human runs `eos vendor review`. Five other popular design-skill repos were checked and not imported (binary downloads, scripts, size, or injection-scan hits); see `docs/research/v0.7-design-sources.md`. The 12 `design/*` refs are original text that cites their sources.

Design studio (after stage 8) vendors four more sources, all quarantined and **pending human sign-off**: `impeccable-knowledge` (pbakaus/impeccable, Apache-2.0 + NOTICE, pinned `d631a882`; held: 1 scan finding), `ui-ux-pro-max-knowledge` and `ui-ux-pro-max-scripts` (nextlevelbuilder/ui-ux-pro-max-skill, MIT, pinned `50d8a7de`) and `emil-review-animations` (MIT, pinned `e8a175de`; optional). Vendor sources now have a **kind**: `knowledge` (text and data an agent may read) or `code` (never pointed to by packs, never installed as context, runs only in the studio sandbox). CSV/TSV files are injection-scanned, and dot-folders are renamed on import (`.claude` → `dot-claude`) so no agent harness can discover a quarantined skill. No pack points to these sources; they reach a project only through the opt-in `eos studio on` (refused while pending) or an A/B workspace made with `eos design ab init --allow-pending`. Review, sandbox design, token measurements and the A/B plan: `docs/research/v0.7-design-studio.md`.

Mobile (stage 9) vendors nothing: the 12 `mobile/*` refs are original text citing Expo, React Native, Flutter, Android, Apple, Firebase, OWASP MASVS/MASTG (linked, CC BY-SA), IETF and StatCounter pages. Expo and Maestro docs carry instructions aimed at AI agents, which is one more reason not to copy them. Enforcement is in-process (`eos mobile check`, `eos mobile size`) plus `eos scaffold mobile` (Semgrep rules with fixtures, Maestro flows, emulator workflow). Survey and decisions: `docs/research/v0.7-mobile-sources.md`.

LLM applications (stage 10) vendor nothing: the 11 `llm/*` refs are original text citing OpenAI, Anthropic, Google, Mistral, the MCP specification, OpenTelemetry GenAI conventions (Development status), pgvector, Elastic, Ragas, OWASP (linked), Cameroon Law 2024/017, Glottolog, IrokoBench, Meta (MMS, WhatsApp) and the framework docs. Mastra and Pydantic AI docs also carry text aimed at AI agents; it was ignored. No prices are recorded anywhere. Enforcement is in-process (`eos llm check` for versioned prompt files, `eos llm gate` for eval regressions) plus `eos scaffold llm-evals` (dataset, runner, gate, CI job, Semgrep rules) and `eos scaffold llm-otel`. Survey and decisions: `docs/research/v0.7-llm-sources.md`.

Data engineering and ML (stage 11, the last library stage) vendor nothing either. The 7 `analytics/*` refs cover architecture (OLTP vs OLAP, batch ELT vs CDC, DuckDB/Postgres-first, lakehouse, cost), dbt, pipelines and backfills, quality and data contracts (ODCS), product events and consent, metrics and dashboards, and privacy/anonymisation. The 5 `ml/*` refs cover framing, splits and leakage; experiments and reproducibility; serving and monitoring; fintech risk (fraud, credit fairness and explanations, with dated regulatory cautions); and notebooks to production. All are our own text citing dbt, DuckDB, Airflow, Dagster, Prefect, Bitol ODCS, Segment, PostHog, Plausible, CNIL, Cameroon Law 2024/017, WP29, NIST, Google's Rules of ML, scikit-learn, MLflow, DVC, lakeFS (BSL 1.1), Evidently, the fraud handbook (linked only), Fairlearn, the EU AI Act and Digital Omnibus, CJEU SCHUFA and Regulation B. PostHog, Prefect, dbt and Dagster pages carry text aimed at AI agents; it was ignored. No new pack: the refs hang off `data-ml`, so always-on context is unchanged. Enforcement is in-process (`eos data check` for ODCS contracts and notebooks, `eos data split` for split leakage) plus `eos scaffold analytics` (dbt + DuckDB project with tests, contract and CI; PII-in-events Semgrep rules) and `eos scaffold ml` (split checklist, model card, datasheet). Survey and decisions: `docs/research/v0.7-data-ml-sources.md`. Status of the whole library and the consolidated human review checklist: `docs/LIBRARY-STATUS.md`.

## Evaluation (`eos library eval`)

`tests/evals/<area>.json` holds small tasks: a prompt, the pack an agent would load, the refs it should read, and a rubric of expert points, each with regex evidence. `eos library eval tests/evals` reports, per task, the tokens of pack alone vs pack + refs, and the share of rubric points present in that context. With `--responses DIR` (files `<task>.base.md` and `<task>.lib.md` from real agent runs without and with the refs) it scores the answers with the same rubric. Context coverage is a proxy for "the guidance is available"; the same author wrote rubric and refs, so treat it as a regression check, and use real runs for quality claims.

## Adding an area (checklist)

1. Survey sources (quality, maintenance, licence, injection risk, tokens); record them in the research doc.
2. Write 5–12 refs under `packs/ref/<area>/`, each ≤ 2,500 tokens, with sources verified live.
3. Point to them from the packs that do that work (`## Deep references`), staying inside pack budgets.
4. Turn what you can into checks (linters in stack packs, `eos` gates, lifecycle exit criteria such as `tables`, Semgrep rules with `ruleid:`/`ok:` fixtures in `tests/semgrep/`, scaffolded test templates). Security example: `core/scaffold/security/semgrep.yml` (12 rules, tested by `semgrep --test` in CI) and `eos scaffold security-tests`. Data example: `eos scaffold db-safety` (tuned `.squawk.toml`, Alembic revisions linted through their offline SQL, `schema_lint.sql` run on a migrated database for unindexed foreign keys and money as float, and money-as-float Semgrep rules). `semgrep --test` ignores annotations in files it treats as generic text (`*.sql`, `*.prisma`), so those fixtures live in `tests/semgrep-generic/` and `tests/semgrep_generic_check.py` checks them. Testing example: native `eos` gates (`diff-coverage`, `quarantine`, `mutation-plan`/`mutation-score`) wired into the lanes so heavier checks run only where they pay, plus scaffolds (`property-python`, `property-node`, `load-k6`, `mutation`, `quarantine`) checked against the real tools in the opt-in `EOS_TEST_TOOLS=1` tests.
5. Add `tests/evals/<area>.json`; run `eos library eval` and `eos library lint --strict`.
6. Re-measure always-on context (`tests/bench/measure_context.py`); it must not grow.
