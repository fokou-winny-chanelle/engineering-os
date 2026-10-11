---
id: llm/privacy-residency
title: Privacy and data residency when sending data to AI providers (provider retention and training terms, zero data retention, regions, free tiers, Cameroon Law 2024/017 transfers and automated decisions, PII minimisation and redaction)
area: llm
read_when: choosing an AI provider or plan, sending personal or customer data to a model API, storing prompts or outputs, using a free tier, serving Cameroonian or EU users, or making automated decisions about people
verified: 2026-10-10
revisit_days: 90
sources: ["https://developers.openai.com/api/docs/guides/your-data", "https://privacy.claude.com/en/articles/7996866", "https://platform.claude.com/docs/en/manage-claude/api-and-data-retention", "https://ai.google.dev/gemini-api/terms", "https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web", "https://microsoft.github.io/presidio/"]
---
# Privacy and residency for AI providers

**Not legal advice.** A model API is a data processor that may store what you send, in another country. Engineering duties for personal data in general: `security/privacy`; attacks that leak data through the model: `security/llm-agent-security`.

## Decision guide

**1. Know what each provider keeps (re-check terms before launch; they change).**
| Provider (API, paid) | Training on your data | Default retention | Options |
|---|---|---|---|
| OpenAI | not used to train by default since 1 March 2023 | abuse-monitoring logs up to 30 days (longer if law requires or to prevent harm); stored objects (files, stored responses, prompt-cache state) per feature | Zero Data Retention / Modified Abuse Monitoring by approval; data residency regions |
| Anthropic | not used for training without express permission | inputs/outputs deleted on the backend within 30 days, with exceptions (e.g. Files API, policy enforcement) | ZDR by agreement; Covered Models (Fable 5.x, Mythos 5.x) require 30-day retention, so no ZDR for them |
| Google Gemini API, **paid** | prompts and responses not used to improve products | logged for a limited period (abuse detection) | Vertex AI for enterprise controls |
| Google Gemini API, **unpaid** (free quota, AI Studio) | used to improve products; **human reviewers may read** input and output | — | not for personal or confidential data; Google's terms allow only Paid Services when serving users in the EEA, Switzerland or the UK |

**2. Residency.** OpenAI offers regional endpoints for approved customers (United States, Europe (EEA + Switzerland), UK, Canada, Australia, Japan, India, Singapore, South Korea, UAE; none in Africa at the time of writing; not every endpoint or model in every region); non-US regions require abuse-monitoring controls and a Modified Retention amendment, and data-residency endpoints carry a 10% uplift for eligible models released on or after 5 March 2026. Hyperscaler-hosted models (Azure, Bedrock, Vertex) let you pick a cloud region; read which features stay in-region. For Cameroonian users, every one of these is a transfer abroad.

**3. Cameroon Law No. 2024/017 (23 Dec 2024), from the official text** (prc.cm, OCR of the certified copy):
- **Section 32**: transfers of personal data to a foreign country require the **prior authorization** of the Personal Data Protection Authority; conditions include an instrument with the destination country, binding security rules at the importer and the Authority's standard contractual clauses; details "laid down by regulation".
- **Section 33**: high-risk processing needs a prior impact assessment.
- **Section 44**: a right to object to decisions based solely on automated processing, including profiling (exceptions include informed explicit consent or a law with safeguards).
- **Section 22**: inform the Authority and the data subject **immediately** of a breach.
- **Section 73**: 18 months from enactment to comply.
Check whether the Authority and implementing regulations are operating before you rely on any procedure, record the authorization status per provider, and take local legal advice. EU users: GDPR transfer rules apply in parallel.

**4. Minimise before you send.**
- Send only fields the task needs; replace identifiers with placeholders (`<CUSTOMER_1>`, `<PHONE_1>`) and re-insert in your code after the call.
- Detect and redact PII in free text (phone numbers, NIU/ID numbers, emails, names) with tested rules or a library such as Microsoft Presidio; measure its recall on your data in French and English, since redaction is never perfect.
- Keep secrets, credentials and payment card data out of prompts entirely; special-category data (health, biometrics) only with a legal basis and a provider plan that supports it.

**5. Your own storage counts too.** Prompts, outputs, traces, eval datasets, vector indexes and long-term memory all hold personal data: give each a retention period, tenant scoping, access control and deletion on request (delete embeddings and chunks too). Keep content capture in tracing off by default (`llm/observability-otel`).

**6. Automated decisions and transparency.** Tell users when they are talking to an AI and what data it uses; for credit, hiring, fraud blocks or account closure, offer human review and an explanation, and log the inputs and model version behind each decision (Section 44 above; GDPR Article 22 for EU users). Minors (the law protects under-18s): stricter defaults.

**7. Configuration as code.** Record provider, plan, region, retention setting (e.g. `store: false`, ZDR status) and the legal basis in `docs/` or `.eos/config.json` next to the model id, and review it in every provider or model change.

## Examples
```python
text, mapping = redact(user_message, kinds=["PHONE", "EMAIL", "NIU", "PERSON"])  # "<PHONE_1>" ...
reply = llm.call(prompt.render(message=text), store=False)  # no stored response
return restore(reply, mapping)  # names back in our code
```

## Anti-patterns
- Building on a free tier with real customer data; assuming "API data isn't used for training" means "nothing is stored".
- Sending whole customer records when the task needs two fields; prompts logged forever in the app log.
- Choosing a provider region for latency without recording that it is a cross-border transfer.
- Fully automated adverse decisions about people with no human review path.

## Checks
- [ ] Provider, plan, region, retention and training terms recorded per model and re-checked on change.
- [ ] Transfer authorization status (Cameroon) / transfer mechanism (EU) recorded per provider.
- [ ] Inputs minimised and PII redacted; redaction recall measured in FR and EN.
- [ ] Retention and deletion cover prompts, traces, vectors, memory and eval data.

## Sources
- OpenAI, Data controls in the OpenAI platform (training, retention, ZDR, residency): https://developers.openai.com/api/docs/guides/your-data
- Anthropic privacy center, API data retention: https://privacy.claude.com/en/articles/7996866
- Anthropic, API and data retention (ZDR, Covered Models): https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
- Gemini API Additional Terms (paid vs unpaid services): https://ai.google.dev/gemini-api/terms
- Cameroon Law No. 2024/017 of 23 December 2024 (official text): https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
- Microsoft Presidio (PII detection and anonymization): https://microsoft.github.io/presidio/
