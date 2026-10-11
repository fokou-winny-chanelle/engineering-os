---
id: security/privacy
title: Data protection and privacy engineering (LINDDUN, GDPR, Cameroon Law 2024/017)
area: security
read_when: adding personal data fields, analytics/tracking, KYC, data exports, retention/deletion, new processors or cross-border transfers, or a DPIA
verified: 2026-10-10
revisit_days: 180
sources: ["https://linddun.org/linddun-go-categories/", "https://eur-lex.europa.eu/eli/reg/2016/679/oj", "https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web", "https://www.africanlawbusiness.com/expert-views/key-features-of-cameroons-new-data-protection-law/", "https://research.lawlab.africa/cameroon/", "https://cheatsheetseries.owasp.org/cheatsheets/User_Privacy_Protection_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html"]
---
# Data protection and privacy engineering

**Not legal advice.** This ref turns common legal duties into engineering tasks. Laws differ by country and change; confirm obligations with counsel or the data protection authority, especially for Cameroon, where the implementing texts and authority were still being set up at the time of writing.

## Decision guide

**Privacy threat modelling with LINDDUN** (add rows to the feature's threat model, `security/threat-modeling`):

| Category | Ask | Typical control |
|---|---|---|
| Linking | Can records be combined to build a profile? | separate identifiers per context, aggregate, avoid joining datasets without need |
| Identifying | Can a person be re-identified from "anonymous" data? | minimise quasi-identifiers (birth date, location), k-anonymity/aggregation, no raw exports |
| Non-repudiation | Can a person be unable to deny something they want to (e.g. a whistleblower)? | plausible deniability where needed |
| Detecting | Can someone infer a person is involved just from observable behaviour? | uniform responses, no existence oracles |
| Disclosure of information | Can personal data leak to people who should not see it? | authz, encryption, redaction in logs/analytics/LLM prompts |
| Unawareness | Do users know and control what happens to their data? | clear notices, consent where required, self-service export/delete |
| Non-compliance | Do we break law, policy or our own notice? | records of processing, DPIA, retention enforcement, processor contracts |

**Engineering duties that map to most laws (GDPR articles shown):**
- **Data inventory / records of processing** (GDPR Art. 30): table of fields, purpose, lawful basis, retention, location, processors. Keep it in the repo (`docs/security/data-inventory.md`) and update it in the PR that adds a field.
- **Minimisation and purpose limitation** (Art. 5): collect only what the feature needs; no "just in case" columns.
- **Privacy by design and default** (Art. 25): least-visible defaults, pseudonymous ids in analytics, PII-free logs (OWASP Logging: exclude secrets and sensitive personal data).
- **Security of processing** (Art. 32): encryption in transit and at rest, access control, tested backups and restores.
- **Breach notification** (Art. 33): to the supervisory authority within **72 hours** of becoming aware, where required; you need an incident runbook and logs good enough to scope a breach.
- **DPIA** (Art. 35) for high-risk processing (large-scale sensitive data, systematic monitoring, profiling with significant effects).
- **Data subject rights**: access/export (Art. 15, 20 portability), rectification, erasure (Art. 17) implemented as jobs that also cover backups policy, search indexes, caches, analytics and processors.
- **Processors** (Art. 28): contract and inventory for every vendor that touches personal data (cloud, email, SMS, analytics, LLM APIs).
- **International transfers** (Chapter V): know where each processor stores data.

**Cameroon — Law No. 2024/017 of 23 December 2024 on personal data protection** (official text: prc.cm; summary from legal commentary, verify before relying on it):
- Prior authorisation/registration with the data protection authority, records of processing, DPIA for high-risk processing, and a DPO in the cases the law prescribes.
- Data subject rights including portability.
- Breach notification to the authority and affected people "immediately"/without delay per commentary; no hour limit is stated in the commentary we reviewed. Processors also have notification duties.
- Cross-border transfers need prior authorisation from the authority per commentary.
- The 18-month compliance grace period ended on **23 June 2026**; commentary (Law Lab Africa) noted the authority's composition was still awaited, so practical procedures may lag.
Engineering consequence for Cameroonian products: keep the data inventory and processor locations current (transfers to foreign cloud/LLM providers are cross-border), log enough to notify fast, and record the authorisation status per processing activity.

**LLM features:** prompts, embeddings and logs sent to model providers are processing by a processor and often a cross-border transfer; redact or pseudonymise before sending; check provider retention and training settings (`security/llm-agent-security`).

## Anti-patterns
- "We anonymised it" by dropping the name but keeping phone, birth date and location.
- Personal data in logs, error trackers, analytics events, URLs and LLM prompts by default.
- Soft-delete forever as "deletion"; no retention jobs; backups kept indefinitely without a policy.
- Adding a processor (SMS gateway, analytics SDK, AI API) without updating the inventory or checking transfer rules.
- Copying production data into dev/test or into AI tools.

## Checks
- [ ] `docs/security/data-inventory.md` lists every personal-data field with purpose, basis, retention, location and processors; PRs that add PII fields update it.
- [ ] Threat model has LINDDUN rows for features processing personal data; DPIA filed when high-risk.
- [ ] Log/analytics redaction test (email, phone, national id, card data never appear).
- [ ] Retention and erasure jobs exist with tests; export endpoint returns a user's data in a machine-readable format.
- [ ] Incident runbook names who notifies the authority and users, and how fast (72 h GDPR; "immediately" under Cameroon law per commentary).
- [ ] Cross-border transfer and authorisation status recorded per processor (Cameroon).

## Sources
- https://linddun.org/linddun-go-categories/
- https://eur-lex.europa.eu/eli/reg/2016/679/oj (GDPR)
- https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web (official text, Cameroon)
- https://www.africanlawbusiness.com/expert-views/key-features-of-cameroons-new-data-protection-law/ (commentary)
- https://research.lawlab.africa/cameroon/ (commentary; grace period, authority status)
- https://cheatsheetseries.owasp.org/cheatsheets/User_Privacy_Protection_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
