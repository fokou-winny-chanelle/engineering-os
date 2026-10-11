---
id: analytics/privacy-anonymisation
title: Privacy for analytics and ML data (pseudonymisation vs anonymisation, k-anonymity and its limits, aggregation thresholds, differential privacy basics, re-identification evidence, minimisation in the warehouse, Cameroon and GDPR definitions)
area: analytics
read_when: copying production data into a warehouse, notebook or training set, sharing data with a partner or researcher, publishing statistics, claiming data is "anonymous", or choosing masking, hashing, aggregation or differential privacy
verified: 2026-10-11
revisit_days: 365
sources: ["https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf", "https://gdpr-info.eu/recitals/no-26/", "https://www.nature.com/articles/s41467-019-10933-3", "https://arxiv.org/abs/cs/0610105", "https://csrc.nist.gov/pubs/sp/800/226/final", "https://docs.opendp.org/en/stable/", "https://www.census.gov/programs-surveys/decennial-census/decade/2020/planning-management/process/disclosure-avoidance/differential-privacy.html", "https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/", "https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web"]
---
# Privacy for analytics and ML data

"We removed the names" is not anonymisation. Most analytics and training data is **pseudonymised personal data** and must be protected, minimised, retained and erased like any personal data. The one idea: minimise first, pseudonymise by default, call something anonymous only after testing it against singling out, linkability and inference, and use aggregation or differential privacy when you publish. Legal bases, rights and inventory: `security/privacy`; event-level rules: `analytics/product-events`.

## Decision guide

**1. Vocabulary that has legal consequences.**
- **Pseudonymisation** replaces identifiers with artificial ones (Cameroon Law 2024/017, Section 5). GDPR Recital 26: pseudonymised data that could be attributed to a person with additional information **is still personal data**. WP29 Opinion 05/2014: pseudonymisation "is not a method of anonymisation"; it only reduces linkability.
- **Anonymisation** makes data unattributable to specific individuals (Cameroon Section 5). WP29 tests an anonymisation against three risks: **singling out** (isolating a person's records), **linkability** (linking records about the same person across datasets) and **inference** (deducing an attribute).
- Truly anonymous data falls outside data-protection law (Recital 26); that is a high bar, so most teams should not rely on it.

**2. Re-identification is easier than intuition says.**
- Rocher et al. (Nature Communications, 2019) estimated that **99.98% of Americans would be correctly re-identified in any dataset using 15 demographic attributes**.
- Narayanan and Shmatikov (2008) re-identified Netflix Prize subscribers, whose ratings were published "anonymously", using little background knowledge and public IMDb data.
- For a mobile-money product, a phone-number hash, a home cell tower and a few transaction timestamps are enough to re-identify most people.

**3. Technique choice.**
| Goal | Technique | Limits |
|---|---|---|
| Internal analytics and ML | drop direct identifiers; keyed hash (HMAC with a secret in the KMS, not plain SHA-256 of a phone number, which is brute-forceable); coarsen (age bands, region, week) | still personal data; access control, retention, erasure apply |
| Joins across systems without sharing identifiers | keyed hash per purpose; rotate keys per project | key holders can re-link |
| Sharing record-level data externally | generalisation + suppression to **k-anonymity**, plus l-diversity for sensitive attributes | WP29: k-anonymity does not prevent inference (a group of k people who all share the sensitive value), and l-diversity/t-closeness do not improve linkability. Treat as risk reduction, not anonymity |
| Publishing aggregates (dashboards for partners, reports) | minimum cell size (suppress small counts), rounding, no overlapping cuts that allow differencing | differencing attacks across many queries |
| Publishing many statistics or training on sensitive data with guarantees | **differential privacy** (noise calibrated to a privacy-loss budget ε) | utility cost; the budget must be accounted across all releases |

**4. Differential privacy basics.** DP is a mathematical framework that quantifies privacy loss when a person's data is in a dataset (NIST SP 800-226, March 2025, which lists common "privacy hazards" in real implementations). Use a vetted library (OpenDP, MIT licence, v0.16) instead of adding noise by hand; decide the unit of privacy (person, not transaction), the total ε budget and who approves spending it. Real-world caution: the US Census Bureau applied DP to 2020 Census data, and its page now says that information is "no longer current" while it evaluates alternatives after an administrative order prohibiting noise infusion. Technical guarantees still need institutional backing.

**5. Minimise on the way into the warehouse.** Do not copy columns you have no question for. Replace MSISDN, email and national ID with keyed hashes in staging; keep the mapping table in the production boundary only. Free text (support notes, transfer memos) is the riskiest column: exclude it or run PII detection before loading. Put the warehouse, notebooks, exports and training sets in the data inventory with retention and erasure (`data/history-retention`).

**6. Notebooks and laptops.** No production personal data on laptops; analysts query a governed environment (warehouse, hosted notebooks) with masked views. Sample datasets for development are synthetic or properly anonymised and reviewed (`testing/test-data`).

## Examples
- Fraud model training set: user id → `HMAC(key_fraud_2026, user_id)`, MSISDN dropped, birth date → age band, GPS → region, memo text dropped. Still personal data: access limited to the fraud team, retention 24 months, erasure job removes rows for deleted users.
- Partner report "transfers by region": counts below 10 suppressed, totals rounded to the nearest 1,000 XAF, no week × region × channel cut for small regions.

## Anti-patterns
- Calling hashed phone numbers "anonymous"; unsalted hashes of low-entropy identifiers.
- Production dumps in notebooks on personal laptops; CSV exports emailed to partners.
- Publishing many overlapping small-cell tables.
- Hand-rolled noise with no budget accounting, labelled "differential privacy".
- **When NOT to bother with DP:** internal analytics by authorised staff; access control, minimisation and pseudonymisation are the right tools there.

## Checks
- [ ] Each analytics/ML dataset lists identifiers removed, pseudonymisation method (keyed, key location) and why remaining fields are needed.
- [ ] Anonymity claims documented against singling out, linkability and inference, reviewed by the privacy owner.
- [ ] Published aggregates apply a minimum cell size; DP releases record ε and the library version.
- [ ] Contracts classify personal-data properties (`eos data check`, DAT005); events carry no PII (Semgrep `eos-analytics-pii-*`).

## Sources
- Article 29 Working Party, Opinion 05/2014 on anonymisation techniques (WP216): https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf
- GDPR Recital 26: https://gdpr-info.eu/recitals/no-26/
- Rocher, Hendrickx, de Montjoye, Nature Communications (2019): https://www.nature.com/articles/s41467-019-10933-3
- Narayanan and Shmatikov, How To Break Anonymity of the Netflix Prize Dataset: https://arxiv.org/abs/cs/0610105
- NIST SP 800-226, Guidelines for Evaluating Differential Privacy Guarantees (March 2025): https://csrc.nist.gov/pubs/sp/800/226/final
- OpenDP: https://docs.opendp.org/en/stable/
- US Census Bureau, Understanding Differential Privacy (status note): https://www.census.gov/programs-surveys/decennial-census/decade/2020/planning-management/process/disclosure-avoidance/differential-privacy.html
- ICO, Anonymisation guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/
- Cameroon Law No. 2024/017 (Section 5 definitions): https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
