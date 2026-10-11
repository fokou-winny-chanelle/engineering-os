---
id: security/threat-modeling
title: Threat modelling workflow (STRIDE + LINDDUN)
area: security
read_when: writing or updating a threat model for a feature that crosses a trust boundary (auth, money, PII, uploads, webhooks, agents)
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.threatmodelingmanifesto.org/", "https://shostack.org/resources/threat-modeling", "https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats", "https://linddun.org/linddun-go-categories/", "https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html", "https://top10.owasp.org/2025/"]
---
# Threat modelling workflow (STRIDE + LINDDUN)

A threat model is a short document that answers the four questions from the Threat Modeling Manifesto: **What are we working on? What can go wrong? What are we going to do about it? Did we do a good enough job?** It is done per feature, at design time, and updated when the design changes. One page that is current beats twenty pages that are not.

## Decision guide

**When to write or update one:** new or changed trust boundary (login, roles, tenant model), money movement, new personal-data field or processor, file upload, inbound webhook, outbound fetch of user-supplied URLs, new third-party integration, LLM feature or agent tool. Skip for pure UI changes behind existing checks.

**The 60-minute workflow** (file: `docs/security/threat-model-<feature>.md`; template: `eos scaffold security`):

1. **Model the system (question 1).** Draw a data-flow diagram in text or Mermaid: external entities (user, partner, payment provider), processes (API, worker), data stores (DB, bucket, queue) and data flows. Mark every **trust boundary** (internet → API, API → DB, your system → third party, user content → LLM). List **assets** (money, credentials, PII, admin rights, availability).
2. **Find threats (question 2)** by walking each element and each flow that crosses a boundary through STRIDE:

| STRIDE | Property broken | Ask | Typical mitigation |
|---|---|---|---|
| Spoofing | authentication | Can someone pretend to be a user, a service or a webhook sender? | MFA/passkeys, mTLS, signed webhooks |
| Tampering | integrity | Can data be changed in transit, at rest or in the request (price, user id, role)? | TLS, server-side values, signatures, DB constraints |
| Repudiation | non-repudiation | Can someone deny an action and we cannot prove it? | append-only audit log with actor, time, ids |
| Information disclosure | confidentiality | Can data leak through APIs, logs, errors, caches, URLs, prompts? | authz on every object, field filtering, redaction |
| Denial of service | availability | Can one client exhaust CPU, memory, money or quota? | rate limits, timeouts, size limits, budgets |
| Elevation of privilege | authorization | Can a user reach admin functions or another tenant's data? | deny by default, server-side checks, least privilege |

3. **Add privacy threats when personal data flows** with LINDDUN: Linking, Identifying, Non-repudiation (bad for the data subject here), Detecting, Disclosure of information, Unawareness, Non-compliance. Details: `security/privacy`.
4. **Decide (question 3).** For each threat choose: mitigate (name the control and the test that proves it), eliminate (remove the feature or data), transfer (provider, insurance; note what remains yours) or accept (owner + expiry date). Rank by impact × likelihood in words (high/medium/low); do not invent numeric scores.
5. **Validate (question 4).** Each mitigation has a test or check id (e.g. `test_cross_tenant_read_denied`, semgrep rule, config assertion). Re-read the diagram against the final code before release.

**Useful threat libraries per area:** OWASP Top 10:2025 (web), OWASP API Security Top 10 2023 (APIs: BOLA, BOPLA, BFLA, SSRF), OWASP Top 10 for LLM and Agentic applications (`security/llm-agent-security`), PCI scope (`security/payments`), supply chain (`security/supply-chain`).

## Examples

Minimal threat table row set for "merchant receives payment webhooks":

| # | Element / flow | STRIDE | Threat | Mitigation (test) | Residual / owner |
|---|---|---|---|---|---|
| T1 | provider → `/webhooks/pay` | S | forged "payment succeeded" event | HMAC over raw body, constant-time compare (`test_bad_signature_rejected`) | key leak → rotation runbook / backend lead |
| T2 | same | T/R | replay of an old valid event | timestamp tolerance + event-id dedupe table (`test_replay_rejected`) | low |
| T3 | handler → ledger | T | double credit on retries | idempotent apply keyed by provider event id (`test_duplicate_event_single_entry`) | low |
| T4 | handler | D | slow processing causes provider retries storm | ack fast, queue work (`test_handler_returns_2xx_before_processing`) | medium / on-call |

## Anti-patterns
- A threat model written after the code, to satisfy a checklist, that nobody re-reads.
- Listing threats with no decision, or "accepted" with no owner and no expiry.
- Modelling only the happy path: forgot retries, admin tools, support back-office, batch jobs, backups and the CI pipeline (all are entry points).
- Treating the internal network, the mobile app or the LLM as a trust boundary you are inside of. The client and the model are always untrusted.
- Numeric risk scores with false precision; stick to ordered words unless your organisation has a calibrated method.

## Checks
- [ ] `docs/security/threat-model-<feature>.md` exists for every feature that crosses a trust boundary, and the PR links it.
- [ ] Every trust-boundary flow has been walked through all six STRIDE letters (a "none" answer is fine but explicit).
- [ ] Personal data in scope → LINDDUN row(s) present.
- [ ] Each threat has a decision; each mitigation names a test or automated check; each accepted risk has an owner and an expiry.
- [ ] The model was updated in the same PR as a design change to the boundary.

## Sources
- https://www.threatmodelingmanifesto.org/ (four questions, values and anti-patterns)
- https://shostack.org/resources/threat-modeling (four-question framework, STRIDE)
- https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats (STRIDE categories and properties)
- https://linddun.org/linddun-go-categories/ (privacy threat categories)
- https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html
- https://top10.owasp.org/2025/
