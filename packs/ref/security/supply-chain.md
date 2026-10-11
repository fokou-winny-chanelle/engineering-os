---
id: security/supply-chain
title: Software supply chain (dependencies, CI, SBOM, SLSA, slopsquatting)
area: security
read_when: adding or updating a dependency, editing CI workflows or GitHub Actions, publishing packages/images, or setting up SBOM/provenance
verified: 2026-10-10
revisit_days: 180
sources: ["https://slsa.dev/spec/v1.2/", "https://slsa.dev/spec/v1.2/build-track-basics", "https://arxiv.org/abs/2406.10279", "https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction", "https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem", "https://docs.npmjs.com/cli/v11/using-npm/config/", "https://pnpm.io/settings", "https://docs.astral.sh/uv/reference/settings/#exclude-newer", "https://docs.renovatebot.com/configuration-options/#minimumreleaseage", "https://github.com/zizmorcore/zizmor", "https://google.github.io/osv-scanner/", "https://github.com/ossf/scorecard", "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations", "https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html"]
---
# Software supply chain

Software Supply Chain Failures is A03 in the OWASP Top 10:2025. Recent incidents show the main attack paths: a compromised GitHub Action leaking CI secrets such as PATs, npm tokens and keys (tj-actions/changed-files, CVE-2025-30066, March 2025), and a self-replicating npm worm ("Shai-Hulud", over 500 packages, September 2025) that scanned environments for credentials and targeted GitHub tokens and API keys (both CISA alerts). AI assistants add a new one: **slopsquatting**, attackers registering package names that models hallucinate.

## Decision guide

**Before adding a dependency (human or AI suggested):**
1. Does it exist under exactly that name in the official registry, and is it the package you think (repo link, publisher, download history, age)? In a study of 576,000 generated code samples across 16 models, hallucinated packages averaged at least 5.2% for commercial models and 21.7% for open-source models, with 205,474 unique made-up names (Spracklen et al., USENIX Security 2025).
2. Is it maintained (recent releases, issues answered, OpenSSF Scorecard), and is the licence allowed?
3. Is it worth it? A few lines of code beat a tiny transitive dependency tree.
4. Add it through the lockfile; review the lockfile diff for unexpected new transitive packages.

**Pin and delay:**

| Ecosystem | Lock | Install in CI | Release-age delay | Install scripts |
|---|---|---|---|---|
| npm (v11 docs) | `package-lock.json` | `npm ci` | `min-release-age` (days) or `before` (date) | `ignore-scripts`; project `allowScripts` policy; never `dangerously-allow-all-scripts` |
| pnpm | `pnpm-lock.yaml` | `pnpm install --frozen-lockfile` | `minimumReleaseAge` (+ `trustPolicy`) | dependency build scripts need explicit `allowBuilds`; `strictDepBuilds` |
| uv / Python | `uv.lock` | `uv sync --locked` | `exclude-newer` | prefer wheels; review sdists with build steps |
| Renovate (any) | — | — | `minimumReleaseAge` on update PRs | — |
| GitHub Actions | pin **full commit SHA** (comment the version) | — | Renovate/Dependabot update SHAs | `permissions:` least privilege per job |

A release-age delay (days, set by the team) gives the community time to catch a compromised release before you install it; security fixes can be exempted case by case.

**CI/CD hardening:**
- `permissions: contents: read` by default; grant `id-token: write`, `packages: write` etc. only to the job that needs it.
- No `pull_request_target` or `workflow_run` that checks out untrusted PR code with secrets; no untrusted `${{ github.event.* }}` interpolated into `run:` (script injection). Lint workflows with **zizmor** (and actionlint).
- Deploy with OIDC short-lived credentials, not stored cloud keys (`security/secrets-keys`); protect release environments with required reviewers.
- Treat CI runners as exposed: no long-lived publish tokens; use trusted publishing / provenance where the registry supports it.

**Know what you ship (SBOM + provenance):**
- Generate an SBOM (CycloneDX or SPDX) per release artifact; scan it and the lockfiles with OSV-Scanner or the stack's audit tool; `actions/dependency-review-action` on PRs.
- **SLSA v1.2** (current; v1.1 retired) has a Build track — L1 provenance exists, L2 hosted build platform (signed provenance), L3 hardened builds — and a new Source track. Aim for Build L2 via GitHub artifact attestations (`actions/attest-build-provenance`) or your platform's equivalent; verify provenance before deploying.
- Sign container images (Sigstore cosign) and verify signatures at deploy.

## Anti-patterns
- `npm install`/`pip install` of a name an AI suggested without checking it exists and is the real project.
- `uses: some/action@v3` or `@main` (tags are mutable; CISA told users to audit every version of tj-actions/changed-files run during the compromise window).
- Piping a downloaded install script straight into a shell in CI or Dockerfiles without checksum verification.
- Auto-merging all dependency updates instantly, including majors.
- Long-lived `NPM_TOKEN`/PATs with write scope stored as CI secrets used by every workflow.
- Lockfiles git-ignored, or CI running `npm install` (which can rewrite the lockfile) instead of `npm ci`.

## Checks
- [ ] Lockfile committed; CI installs with the frozen/locked command.
- [ ] All `uses:` pinned to 40-char SHAs with a `# vX.Y.Z` comment (`eos check`: error in eos-generated workflows, warning in yours; zizmor `unpinned-uses`); Renovate `helpers:pinGitHubActionDigests` keeps them fresh; workflow `permissions:` set.
- [ ] Release-age delay configured in the package manager or Renovate; install-script policy set (npm `allowScripts`/pnpm `allowBuilds`).
- [ ] Dependency review + OSV/audit in CI; SBOM generated on release (`eos scaffold security` workflow).
- [ ] Release artifacts have provenance attestations, verified before deploy.
- [ ] New-dependency PR template asks: exists, maintained, licence, why needed.

## Sources
- https://slsa.dev/spec/v1.2/ and https://slsa.dev/spec/v1.2/build-track-basics (Build L0–L3, Source track)
- https://arxiv.org/abs/2406.10279 (package hallucination study)
- https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction
- https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
- https://docs.npmjs.com/cli/v11/using-npm/config/ (`min-release-age`, `before`, `allowScripts`, `ignore-scripts`)
- https://pnpm.io/settings (`minimumReleaseAge`, `trustPolicy`, `allowBuilds`, `strictDepBuilds`)
- https://docs.astral.sh/uv/reference/settings/#exclude-newer
- https://docs.renovatebot.com/configuration-options/#minimumreleaseage
- https://github.com/zizmorcore/zizmor
- https://google.github.io/osv-scanner/
- https://github.com/ossf/scorecard
- https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html
