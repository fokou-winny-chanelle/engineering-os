# Third-party notices

engineering-os is licensed under the MIT licence ([LICENSE](LICENSE)). It also contains third-party material that is **not** covered by that licence. Each item below keeps its own licence. The licence text sits next to the material and must travel with it if you copy it.

## Vendored sources (`packs/vendor/`)

Each source is copied byte for byte at a pinned commit. Every file is hashed in [`packs/vendor/PROVENANCE.json`](packs/vendor/PROVENANCE.json), and `eos vendor check` verifies the hashes. **All eight are quarantined pending human review:** eos does not load them into any agent context until a maintainer runs `eos vendor review <id>`.

| Directory | Upstream (pinned commit) | Licence | Licence / notice file |
|---|---|---|---|
| `packs/vendor/owasp-cheatsheets/` | [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) @ `cb9fe01` | CC BY-SA 4.0 | `LICENSE.md` in the directory |
| `packs/vendor/owasp-llm-prompt-injection/` | [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) @ `cb9fe01` | CC BY-SA 4.0 | `LICENSE.md` in the directory |
| `packs/vendor/impeccable-knowledge/` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) @ `d631a88` | Apache-2.0 | `LICENSE`, `NOTICE.md` (includes MIT-licensed material from ehmo/platform-design-skills) |
| `packs/vendor/anthropic-frontend-design/` | [anthropics/skills](https://github.com/anthropics/skills) @ `dbd4588` | Apache-2.0 | `skills/frontend-design/LICENSE.txt` |
| `packs/vendor/emil-review-animations/` | [emilkowalski/skills](https://github.com/emilkowalski/skills) @ `e8a175d` | MIT | `LICENSE` |
| `packs/vendor/ui-ux-pro-max-knowledge/` | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) @ `50d8a7d` | MIT | `LICENSE` |
| `packs/vendor/ui-ux-pro-max-scripts/` | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) @ `50d8a7d` | MIT | `LICENSE` |
| `packs/vendor/vercel-web-interface-guidelines/` | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) @ `434b7f9` | MIT | `LICENSE` |

The CC BY-SA 4.0 OWASP material stays in its own directories and is not mixed into MIT-licensed files. The vendored files have not been modified. The pre-commit fixers exclude `packs/vendor/`, so the hashes stay valid.

## Adapted text under CC BY 4.0 (`packs/ref/api/`)

These references condense guidance from the Zalando RESTful API Guidelines, Google AIPs, the Microsoft Azure REST API Guidelines and the Azure Architecture Center, all CC BY 4.0. Each file ends with an `## Attribution` section naming the sources, the licence and the changes made:

`packs/ref/api/collections.md`, `packs/ref/api/errors-problem-details.md`, `packs/ref/api/evolution.md`, `packs/ref/api/rate-limits-auth.md`, `packs/ref/api/reliability.md`, `packs/ref/api/resource-design.md`.

If you redistribute these files, keep the Attribution sections.

## Other references

The remaining files under `packs/ref/` are original text that cites its sources (each lists them under `## Sources`). They are covered by the MIT licence of this repository. Quoted facts remain the work of their authors.

## Tools that eos installs or runs

eos does not bundle third-party binaries. Tools such as gitleaks, ruff, pre-commit, Semgrep, Playwright MCP and postgres-mcp are downloaded by the user's package managers at the versions pinned in `versions.toml` and `mcp/`. Each is used under its own licence.
