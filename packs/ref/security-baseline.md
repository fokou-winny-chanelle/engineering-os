# Security baseline: levels, cadence, compliance (read on demand by the security pack)

## Pick a level (OWASP ASVS 5.0)

| Product | ASVS | Mobile | Extra |
|---|---|---|---|
| No accounts, no personal data | L1 | MASVS L1 | Secrets scan, dependency audit, headers |
| Accounts or personal data, or money | **L2** (eos default when unknown) | MASVS L2 | Threat model per feature, LINDDUN for personal data, pentest before launch |
| Banking, health, identity, critical infrastructure | L3 (decide with a human) | MASVS L2 + RESILIENCE | External audit, formal risk acceptance |

Standards: OWASP Top 10:2025 (web), API Security Top 10, Top 10 for LLM Applications and for Agentic Applications (agent-security pack), ASVS 5.0, MASVS v2 / MASTG.

## Cadence

| When | What |
|---|---|
| Every commit/PR | Secrets scan (gitleaks), lint + SAST (Semgrep/CodeQL), dependency audit, `eos test-integrity`, review security-relevant diffs by a human |
| Weekly | Renovate dependency PRs (cooldown, no auto-merge for majors); triage new advisories |
| Monthly | Review access (people, tokens, deploy keys, MCP servers and their tool descriptions); rotate what's due; check backups restore |
| Every release | SBOM + provenance (SLSA Build L2+), migration safety, DAST/ZAP baseline on major releases |
| Quarterly | Refresh threat models, run an incident drill, review logging and alerts, prune unused dependencies and permissions |
| Yearly / before big launches | External pentest for apps with money or personal data; review data-protection compliance |
| On incident or leak | Revoke first, then investigate, then clean history; write a postmortem and turn the lesson into a check |

## Compliance notes (not legal advice; confirm with counsel)

- **GDPR** (EU users or EU-based processing): lawful basis, data minimisation, data subject rights, DPIA for high risk, processor agreements, breach notice within 72 hours to the authority.
- **Cameroon, Law No. 2024/017 of 23 December 2024** on personal data protection. Commentators summarise its obligations as:
  - lawful basis and consent;
  - records of processing;
  - security measures;
  - impact assessments for high-risk processing;
  - breach notification;
  - authorisation regimes for some processing and cross-border transfers.

  It gave an 18-month compliance window. Commentators reported the supervisory authority was still being set up. Official text: https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
- **PCI DSS** (cards): keep card data off your servers with the provider's hosted fields or redirects. That shrinks your scope to the simplest questionnaire your acquirer allows. Never log card data.
- **Mobile stores**: privacy labels / data safety forms must match what the app really collects.

## Supply chain checklist

- Lockfiles committed. Installs in CI are frozen. Actions are pinned (SHA, or a version kept up to date by Renovate).
- New dependency: does it exist (AI hallucinates names)? Real downloads and history? Maintainers active? Licence OK? Is it needed at all?
- Release: build in CI only, attach an SBOM, and sign or attest provenance (Sigstore/GitHub attestations).
- Containers: minimal base image, non-root, scanned, pinned by digest for production.
