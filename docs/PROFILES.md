# Project profiles, modes and topologies (v0.5)

Different products need different guidance. A CLI library doesn't need a design-direction skill; a mobile wallet needs MASVS and a low-bandwidth reminder in every session. Profiles pick what gets installed, and the questionnaire records the few facts that change how the agent should behave.

## How it works

1. **`eos init` guesses a profile** from the detected stacks: Expo/Flutter → `mobile`, Next.js → `web-app`, FastAPI/Flask → `api`, nothing recognised → `full`.
2. **On a terminal it asks** for the project type plus five questions (Enter keeps the default):

   | Key | Question | Values |
   |---|---|---|
   | `money` | Does the product move money? | yes / no / unknown |
   | `personal_data` | Personal or sensitive data? | yes / no / unknown |
   | `llm` | Does the product itself call LLMs or run agents? | yes / no / unknown |
   | `scale` | Users in 12 months | small (<10k) / medium / large (>1M) / unknown |
   | `low_bandwidth` | Many users on low-end phones or slow/expensive networks? | yes / no / unknown |

3. **No terminal (CI, agents) or `--yes`:** flags, then saved answers, then guesses. Unanswered stays `unknown`. Unknown money or personal data counts as "yes" (fail-safe default → ASVS L2).
4. **The result is saved** in `.eos/manifest.json` (`profile`, `answers`). It is rendered as a short *Product profile* block in `AGENTS.md` (about 50–140 tokens, depending on answers).

```sh
eos init --profile mobile --answers money=yes,personal_data=yes,low_bandwidth=yes
eos init --profile api --yes                 # non-interactive
eos init --interactive                       # force the questions (e.g. inside a script with stdin)
eos init --profile cli-library               # re-run any time to switch; saved answers are kept
```

## What a profile selects

- **Files-mode packs are always installed:** backend, frontend, mobile, data-ml, testing-qa, infra-devops, documentation. They cost nothing until a matching file is edited.
- **Skill packs** (intent/both) are listed by description in every request, so the profile picks them:

| Profile | Skill packs (on top of the base set) | Suggested MCP profile | Suggested scaffolds |
|---|---|---|---|
| base (all profiles) | requirements, architecture, decisions, code-review, security, agent-security, release, maintenance | | |
| `web-app` | discovery, ux-design, design-direction, api-design, data-modeling, operations | minimal | security, release, e2e-node, compose, reproducible |
| `api` | api-design, data-modeling, operations, performance-scale | api | security, release, api-contract, compose, reproducible |
| `mobile` | discovery, ux-design, design-direction, api-design, operations | minimal | security, release, reproducible |
| `data-ml` | discovery, data-modeling, operations | minimal | security, reproducible |
| `internal-tool` | ux-design, data-modeling, operations | minimal | security, compose, reproducible |
| `cli-library` | api-design | minimal | security, release, reproducible |
| `full` | everything (v0.3 behaviour; projects initialised before v0.4 keep this) | minimal | security, release, reproducible |

`scale=medium|large` adds `performance-scale` to any profile.

## Lifecycle mode and topology add packs too (v0.5)
`eos init` / `eos adopt` also detect the **lifecycle mode** and the **repo shape** (topology), print the evidence ("why"), and save both in the manifest. Confirm or change them with `eos mode set <mode>` and `eos topology set <shape>`.

| Detected | Rule (first match wins) | Adds skill packs |
|---|---|---|
| mode `rewrite` | a migration plan exists in `docs/migration/` | migration, maintenance |
| mode `greenfield` | fewer than 5 source files | (none) |
| mode `maintain` | history ≥ 365 days with ≥ 3 tags, or ≥ 1000 commits | maintenance, performance-scale, operations |
| mode `brownfield` | anything else with code | migration, maintenance |
| topology `microservices` | ≥ 2 deployable units under `services/` (or `svc/`, `microservices/`), or a compose file with ≥ 3 built services | topology, api-design |
| topology `modular-monolith` | a module root (`modules/`, `domains/`, `contexts/`, `bounded_contexts/`) with ≥ 2 code folders, or a boundary config (`.importlinter`, `.dependency-cruiser.*`, Packwerk, Tach) | topology |
| topology `monorepo` | workspace tooling (pnpm, Turborepo, Nx, Lerna, Rush, go.work, npm/uv/Cargo workspaces) or several app dirs | (none: a short AGENTS.md block is enough) |
| multi-repo workspace | the folder is not a git repo and holds ≥ 2 git repos | `eos init` refuses and points to `eos workspace init` |

Aliases: `refonte`, `replatform`, `migration` → rewrite; `adopt`, `legacy`, `existing` → brownfield; `maintenance`, `scale-up`, `mature` → maintain.

Other per-project settings, all in `.eos/manifest.json`:
- `teaching`: `off` by default since v0.6 (terse answers); `on` adds one always-on line (~30 tokens) asking agents to explain each decision in plain words. `eos teach on|off`.
- `lanes` (in `.eos/config.json`, optional): extra `risky` / `trivial` globs, `risk_words` and `large` thresholds for `eos lane` (docs/WORKFLOW.md).
- `gates`: `strict` (default) or `ratchet` (default after `eos adopt`). Ratchet keeps stack formatters out of pre-commit (they would rewrite legacy code; the strict version waits in `.eos/suggested/pre-commit-strict.yaml`) and adds a pre-push `eos ratchet check`. `eos gates strict|ratchet`.

Switching profile removes the generated files of packs that are no longer selected. Files you edited are kept and reported. `eos update` never removes packs; it adds new packs only if the profile wants them.

Edit `core/profiles.json` in your engineering-os checkout to change the mapping. The unit tests check it against the packs and the CLI.
