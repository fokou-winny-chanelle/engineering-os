---
id: security/security-testing
title: Security testing (SAST, DAST, API fuzzing, fuzzing, secret scanning, security unit tests)
area: security
read_when: setting up security scans in CI, writing security test cases, triaging scanner findings, or preparing a release/pentest
verified: 2026-10-10
revisit_days: 365
sources: ["https://docs.semgrep.dev/", "https://docs.semgrep.dev/writing-rules/testing-rules", "https://codeql.github.com/docs/", "https://docs.astral.sh/ruff/rules/#flake8-bandit-s", "https://bandit.readthedocs.io/en/latest/", "https://www.zaproxy.org/docs/docker/baseline-scan/", "https://schemathesis.readthedocs.io/en/stable/", "https://github.com/google/atheris", "https://github.com/CodeIntelligenceTesting/jazzer.js", "https://google.github.io/oss-fuzz/", "https://github.com/gitleaks/gitleaks", "https://owasp.org/projects/web-security-testing-guide", "https://github.com/OWASP/ASVS"]
---
# Security testing

Scanners find known-bad patterns and dependency CVEs; they rarely find broken authorization or business-logic flaws. A good setup combines **cheap automated layers on every PR** with **targeted security unit tests written from the threat model**, plus deeper scans before releases.

## Decision guide

**Layers and when they run:**

| Layer | Finds | Tool options | When | Blocking? |
|---|---|---|---|---|
| Secret scanning | committed credentials | gitleaks (pre-commit + CI), GitHub push protection, TruffleHog (verifies liveness) | every commit/push | yes |
| Lint-level SAST | dangerous calls (shell=True, pickle, weak hash, SQL strings, no timeout) | ruff `S` (bandit rules re-implemented; bandit itself if not using ruff), eslint security plugins | pre-commit + CI | yes |
| Pattern SAST with project rules | your own banned patterns (JWT verify off, unsigned webhooks, CORS `*`+credentials) | Semgrep with `.semgrep/eos-security.yml` (`eos scaffold security`) | CI on PR | yes for ERROR rules |
| Dataflow SAST | taint from request to sink across functions | CodeQL (GitHub code scanning), Semgrep Pro | CI on PR + scheduled | triage queue |
| Dependency / SBOM scan | known-vulnerable packages | dependency-review action, OSV-Scanner, `npm audit`, `pip-audit` | CI on PR + daily | block on high with fix available |
| Security unit/integration tests | authz (IDOR/BOLA/BFLA), auth flows, webhook signature/replay, rate limits, input bounds | pytest/vitest/JUnit + `eos scaffold security-tests` templates | every PR | yes |
| API fuzzing / property tests | crashes, 500s, schema violations from generated inputs | Schemathesis (from OpenAPI), Hypothesis/fast-check | CI nightly or on API changes | 500s block |
| Coverage-guided fuzzing | memory/parsing bugs in parsers, decoders, file handlers | Atheris (Python), Jazzer.js (Node), OSS-Fuzz for OSS | nightly / long-running | crashes triaged |
| DAST baseline | missing headers, cookie flags, info leaks on a running app | ZAP baseline scan (spider + **passive** scan, no attacks, a few minutes) | CI against staging/preview | warn → fail on agreed rules |
| DAST full / pentest | exploitable flaws in a deployed system | ZAP full scan (active attacks; test env only), manual testing guided by OWASP WSTG and ASVS | before major releases, yearly, after big auth/payment changes | findings tracked |

**Writing security tests from the threat model:** every STRIDE row's mitigation names a test (`security/threat-modeling`). The minimum set for an API: authorization matrix (every route × role incl. cross-tenant), authentication edge cases (expired/wrong-audience tokens, session rotation), mass-assignment attempt, injection payloads at each input type, SSRF to metadata/localhost, oversize/wrong-type uploads, webhook bad signature/stale/replay, rate-limit 429s, error responses without stack traces.

**Semgrep rules you own:** keep them in `.semgrep/`, each with a test file containing `# ruleid:` and `# ok:` annotations, run `semgrep --test .semgrep/` in CI so rules do not silently rot (Semgrep "testing rules" docs).

**Triage discipline:** every suppression (`# nosemgrep: rule-id`, `# noqa: S608`) carries a reason; exceptions to dependency findings have an expiry date; false-positive-heavy rules are fixed or removed, not ignored en masse.

## Anti-patterns
- Running ZAP full/active scans against production.
- "Scanner is green" as the security sign-off; no authorization tests at all.
- Turning off a scanner because of noise instead of tuning rules.
- Suppressing findings file-wide or with no reason; scanner output nobody reads (non-blocking forever).
- Security tests that only cover the happy path ("admin can do X") and never the denial ("customer cannot").

## Checks
- [ ] CI has: gitleaks, ruff `S` (or bandit), Semgrep with project rules + `semgrep --test`, dependency review/OSV, CodeQL (where available).
- [ ] `tests/security/` contains authorization-matrix and webhook tests (or equivalents) and they run in CI.
- [ ] Schemathesis (or equivalent) runs against the OpenAPI spec on API changes; no 500s.
- [ ] ZAP baseline runs against a preview/staging deployment before release; findings triaged.
- [ ] Every suppression has a reason; dependency exceptions have expiry dates.

## Sources
- https://docs.semgrep.dev/ and https://docs.semgrep.dev/writing-rules/testing-rules (`ruleid:`/`ok:` annotations, `--test`)
- https://codeql.github.com/docs/
- https://docs.astral.sh/ruff/rules/#flake8-bandit-s and https://bandit.readthedocs.io/en/latest/
- https://www.zaproxy.org/docs/docker/baseline-scan/ (spider + passive scan, no attacks)
- https://schemathesis.readthedocs.io/en/stable/
- https://github.com/google/atheris
- https://github.com/CodeIntelligenceTesting/jazzer.js
- https://google.github.io/oss-fuzz/
- https://github.com/gitleaks/gitleaks
- https://owasp.org/projects/web-security-testing-guide
- https://github.com/OWASP/ASVS
