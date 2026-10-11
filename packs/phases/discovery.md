---
id: discovery
title: Product discovery
kind: phase
mode: intent
when: validating a problem, users, market or feasibility before writing requirements
description: Use to validate that a problem is worth solving (users, competitors, spikes, metrics) before a PRD.
globs: ["docs/discovery/**", "docs/research/**"]
next: [requirements]
---
# Product discovery

## Entry
An idea doc with a chosen direction and a riskiest assumption (from ideation), or a stakeholder request.

## Standards
1. Evidence over opinion. Every finding cites a source: an interview note, analytics query, support ticket, doc URL or spike result. Unknowns stay "unknown".
2. Users & jobs. Name 1–3 primary personas and their job-to-be-done ("When …, I want to …, so I can …"). Note context constraints such as low bandwidth, mobile-first use, local payment methods, language (FR/EN), and regulation.
3. Competitive and alternative scan. Cover what users do today and why it fails them. Mark findings from web research with a date and link.
4. Feasibility spikes are time-boxed (≤1 day each). Their code is thrown away and lives in `spikes/` or a branch, never on main. Record the result, not the code.
5. Success metrics. Pick one North Star metric plus 2–3 guardrail metrics (e.g. error rate, cost per transaction, fraud rate). Each needs a target and a measurement method.
6. Non-goals are explicit. They are the cheapest scope control you have.
7. Risk register: product, technical, security/privacy, compliance and operational risks, each with an owner and a mitigation.
8. Use BMAD Analyst (Mary): `bmad-product-brief`, `bmad-prfaq` (working-backwards press release) and `bmad-deep-recon` for research.

## Deliverables
- `docs/discovery/brief.md` (or BMAD product brief): problem, personas, JTBD, alternatives, metrics, non-goals, risks, open questions.
- Spike reports in `docs/discovery/spikes/<n>-<slug>.md` (question → method → result → decision).

## Automated checks
- Markdown lint. Optional: a link checker on docs.

## Exit checklist (Definition of Done)
- [ ] The riskiest assumption has been tested and the result recorded.
- [ ] Personas and JTBD are written; metrics have targets and a measurement method.
- [ ] Non-goals are listed. Risks have owners.
- [ ] Open questions are listed with who answers each one.
- [ ] Human sign-off: proceed to requirements (choose BMAD track: Quick Flow / BMad Method / Enterprise).

## Handoff → requirements
Pass the brief plus spike reports. Requirements must trace back to the personas and metrics.

## Stop & escalate
Stop when the evidence contradicts the idea (report it, don't spin it), or when the work needs real user data or PII.
