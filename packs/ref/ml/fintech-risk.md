---
id: ml/fintech-risk
title: Fraud and credit-risk models in fintech (imbalance, delayed labels, time-based validation, rules plus models, review capacity; credit scoring fairness metrics and trade-offs, proxies, explanations and adverse-action reasons; regulatory cautions for Cameroon, the EU and the US)
area: ml
read_when: building or changing a fraud score, transaction monitoring model, credit score, loan limit or pricing model, choosing fairness metrics, producing reasons for declines, or assessing legal exposure of automated decisions
verified: 2026-10-11
revisit_days: 180
sources: ["https://fraud-detection-handbook.github.io/fraud-detection-handbook/Foreword.html", "https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_5_ModelValidationAndSelection/ValidationStrategies.html", "https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html", "https://arxiv.org/abs/1609.05807", "https://arxiv.org/abs/1703.00056", "https://shap.readthedocs.io/en/latest/example_notebooks/overviews/Be%20careful%20when%20interpreting%20predictive%20models%20in%20search%20of%20causal%20insights.html", "https://artificialintelligenceact.eu/annex/3/", "https://eur-lex.europa.eu/eli/reg/2026/1744/oj", "https://oeil.europarl.europa.eu/oeil/en/procedure-file/pdf?reference=2025%2F0359%28COD%29", "https://curia.europa.eu/juris/liste.jsf?num=C-634/21", "https://www.consumerfinance.gov/rules-policy/regulations/1002/9/", "https://www.consumerfinance.gov/compliance/guidance/withdrawn-guidance/", "https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web"]
---
# Fraud and credit-risk models

Fraud and credit models move money and decide who gets served. They need the general practice (`ml/framing-splits-leakage`, `ml/serving-monitoring`) plus domain traps and legal duties. The one idea: **validate on time with label delay, measure at the operating point reviewers and the business can afford, test fairness by slice before launch, give every decline a specific, true reason, and let a human review contested decisions.** This ref is engineering guidance, not legal advice; the regulatory points below need confirmation by counsel for your market.

## Decision guide

**1. Fraud models: the domain traps** (the open *Reproducible Machine Learning for Credit Card Fraud Detection* handbook covers them in depth; prose CC BY-SA, so we link rather than copy):
- **Imbalance:** positives are rare; use precision/recall and precision@k at the alert volume reviewers can handle, and cost-weighted metrics (fraud loss avoided minus friction cost of false alerts).
- **Delayed labels:** confirmed fraud (chargebacks, investigations) arrives late, so the most recent transactions cannot be used for training: the handbook's validation strategy drops a **delay period** between training and test blocks.
- **Adversaries adapt:** retrain on a schedule; keep rules for fast response.
- **Rules plus model:** hard rules for known patterns and regulatory blocks (sanctions, limits), the model to rank the rest, analysts' feedback as labels. The model never silently overrides a compliance rule.
- **Feedback loops:** blocked transactions never get a fraud label; keep a small, approved random sample of lower-risk alerts reviewed to estimate what you miss.
- **Mobile money specifics:** SIM swap recency, new device, agent cash-out patterns, many small transfers to new recipients (mule accounts); features computed as of the transaction instant.

**2. Credit scoring: fairness is a choice among incompatible goals.**
- Fairlearn's common metrics: **demographic parity** (similar approval rates across groups) and **equalized odds** (similar true- and false-positive rates). Fairlearn notes equalized odds assumes the target is a good measurement of what you model, which may not hold (construct validity: past repayment reflects past access to credit).
- **They cannot all hold at once**: Kleinberg, Mullainathan and Raghavan show that, except in highly constrained cases, no method satisfies calibration within groups and balance for both classes simultaneously; Chouldechova shows the criteria cannot all be met when base rates differ between groups. Pick the criterion that matches the harm, document why, and report the others.
- **Proxies:** removing protected attributes does not remove bias. Location, phone model, language, top-up patterns and social graph features can stand in for ethnicity, gender, age or income. Test outcomes by group where lawful (or with proxy-based estimates under a privacy review) and remove or constrain features that drive disparities without predictive justification.
- Thin-file applicants (no bureau history) are common in Cameroon: alternative data (mobile money, airtime) needs explicit consent and a clear purpose (`analytics/privacy-anonymisation`, `security/privacy`).

**3. Explanations and reasons.** Prefer inherently interpretable models (scorecards, monotonic gradient boosting) for credit decisions. SHAP values explain the model, not the world; SHAP's own docs warn: "making correlations transparent does not make them causal". Reason codes must be **specific and true** for the individual (top factors that lowered the score, mapped to plain language a person can act on), stable across small input changes, and tested.

**4. Regulatory cautions (checked 2026-10-11).**
| Jurisdiction | What applies | Engineering consequence |
|---|---|---|
| Cameroon, Law No. 2024/017 (from an OCR of the official text) | Section 44: right to object to a decision based solely on automated processing, including profiling, unless the person was informed and gave prior explicit consent, or a law permits it with safeguards; the person may obtain human intervention, express their view and challenge the decision | human review path for automated declines; consent records; explainable reasons. Banking and microfinance rules (COBAC/BEAC) may add requirements: ask counsel |
| EU, AI Act Annex III point 5(b) | AI systems used to evaluate creditworthiness or establish credit scores of natural persons are high-risk, **except systems used to detect financial fraud** | the Digital Omnibus (Regulation (EU) 2026/1744, in force 27 July 2026) sets 2 December 2027 for Annex III high-risk obligations: risk management, data governance, logging, human oversight, documentation |
| EU, GDPR Art. 22 (CJEU C-634/21 *SCHUFA*, 7 Dec 2023) | an automatically established credit score is itself an automated decision when a lender "draws strongly" on it | scoring vendors and lenders both need an Art. 22 basis and safeguards |
| US, ECOA / Regulation B §1002.9 | adverse-action notices must state specific reasons (or the right to them) | reason codes from the model. CFPB Circular 2022-03 (complex algorithms are no excuse) was **withdrawn on 12 May 2025**; the regulation itself still applies |

## Examples
Micro-loan limit model for a wallet: monotonic gradient boosting; split by application month with a 90-day gap; default and approval rates at the threshold, calibration by decile; fairness report by region, gender (where collected with consent) and language with the chosen criterion justified; declines show the top three reasons ("account active for less than 3 months", …) and a "request human review" button.

## Anti-patterns
- Accuracy or AUC as the launch metric for fraud; no alert-volume constraint.
- Random splits on transactions; training on the most recent, still-unlabelled weeks.
- "We don't use gender, so the model is fair."
- Generic decline messages, or SHAP-derived reasons that change when an irrelevant input changes.
- Fully automated declines with no way to object or reach a human.
- **When NOT to use ML for credit:** too few repaid/defaulted loans to learn from; start with a transparent scorecard or policy rules and collect outcomes.

## Checks
- [ ] Time-based validation with a label-delay gap; metrics at the operating threshold and alert capacity.
- [ ] Fairness report by slice with the chosen criterion documented and signed off by risk/compliance.
- [ ] Reason codes generated, specific, tested for stability; human review path live.
- [ ] Legal review per market recorded (Cameroon Section 44; EU AI Act status; GDPR Art. 22; Reg B if lending in the US).

## Sources
- Le Borgne et al., Reproducible ML for Credit Card Fraud Detection (foreword, licence): https://fraud-detection-handbook.github.io/fraud-detection-handbook/Foreword.html · validation strategies (delay period): https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_5_ModelValidationAndSelection/ValidationStrategies.html
- Fairlearn, common fairness metrics: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
- Kleinberg, Mullainathan, Raghavan, Inherent Trade-Offs in the Fair Determination of Risk Scores: https://arxiv.org/abs/1609.05807
- Chouldechova, Fair prediction with disparate impact: https://arxiv.org/abs/1703.00056
- SHAP, Be careful when interpreting predictive models in search of causal insights: https://shap.readthedocs.io/en/latest/example_notebooks/overviews/Be%20careful%20when%20interpreting%20predictive%20models%20in%20search%20of%20causal%20insights.html
- EU AI Act Annex III (reader-friendly text): https://artificialintelligenceact.eu/annex/3/
- Regulation (EU) 2026/1744 (Digital Omnibus on AI): https://eur-lex.europa.eu/eli/reg/2026/1744/oj · procedure file: https://oeil.europarl.europa.eu/oeil/en/procedure-file/pdf?reference=2025%2F0359%28COD%29
- CJEU C-634/21 SCHUFA: https://curia.europa.eu/juris/liste.jsf?num=C-634/21
- Regulation B §1002.9: https://www.consumerfinance.gov/rules-policy/regulations/1002/9/ · CFPB withdrawn guidance: https://www.consumerfinance.gov/compliance/guidance/withdrawn-guidance/
- Cameroon Law No. 2024/017 (Section 44): https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
