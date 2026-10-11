---
id: ops/incident-runbooks
title: Incident response (severity, roles, communication, timeline), blameless postmortems and runbooks
area: ops
read_when: something is broken in production, declaring or running an incident, writing a status update, writing a postmortem or a runbook, reviewing on-call documentation
verified: 2026-10-10
revisit_days: 180
sources: ["https://response.pagerduty.com/before/severity_levels/", "https://response.pagerduty.com/before/different_roles/", "https://response.pagerduty.com/during/external_communication_guidelines/", "https://postmortems.pagerduty.com/", "https://sre.google/sre-book/managing-incidents/", "https://sre.google/sre-book/postmortem-culture/", "https://sre.google/workbook/incident-response/"]
---
# Incident response, postmortems and runbooks

An incident is unplanned user harm (or a credible risk of it) that needs a coordinated response. The goal during an incident is to stop the harm; finding the root cause comes after.

## Decision guide

**1. Declare early.** The SRE book: it is better to declare early and close a false alarm than to start coordinating hours in. Write the conditions down (`docs/ops/incident-response.md` from `eos scaffold ops`): users cannot pay or sign in, data may be lost or exposed, money totals disagree, a fast-burn SLO page is not mitigated within 15 minutes. When unsure, declare.

**2. Severity, simply.** PagerDuty's levels (SEV-1 critical … SEV-5 cosmetic) are a good base; a small team needs three:
| Sev | Meaning | Response |
|---|---|---|
| SEV-1 | most users affected, money or data at risk, security breach | page now, status page, all hands |
| SEV-2 | many users or a key journey degraded | page now, status page if users notice |
| SEV-3 | few users, workaround exists | ticket, working hours |
PagerDuty treats anything above SEV-3 as a major incident and says to pick the higher level when unsure; argue about severity in the postmortem, not during the incident.

**3. Roles, even when you are alone.** From the Incident Command System (used by Google and PagerDuty): Incident Commander (decides, delegates, does not debug), Subject Matter Expert (fixes), Scribe (timeline), Communications/Liaison (status page, support, stakeholders). One person may hold several roles in a small team, but the commander should hand off hands-on debugging as soon as a second person joins. Solo: still write the timeline and still post updates; tell your backup person you are on it.

**4. First 15 minutes.**
1. Declare: channel or issue `INC-YYYYMMDD-name`, severity, commander.
2. Mitigate first: roll back the last deploy, turn off the last flag, fail over, shed load (`ops/deploy-strategies`, `ops/feature-flags`). Follow the alert's runbook.
3. Preserve evidence: keep logs and traces; do not copy production personal data to laptops or chat.
4. Communicate (below), then on a fixed rhythm.

**5. Communication.** First external message fast (PagerDuty aims for 5 minutes after the incident call starts) and boring: what users see, since when (UTC), who is affected, next update time. Then updates on schedule even with no news (PagerDuty: at least every 20 minutes for the first two hours), and whenever impact changes. No blame, no guesses about cause, no names. Internal stakeholders get the same facts plus the mitigation plan.

**6. Timeline.** Append-only, UTC, one line per observation or action, written as it happens (time, who, what). It drives the postmortem and stops people repeating failed fixes.

**7. Resolve, then learn.** Resolved = users no longer affected and metrics confirm it. Then a blameless postmortem for SEV-1/SEV-2, any data or money impact, or when one incident burned more than 20% of the four-week error budget (Workbook example policy):
- Blameless means naming contributing causes in systems and processes without indicting people (SRE book). People acted on what they knew; ask why the system allowed the mistake.
- Sections: summary, impact (users, duration, money, budget burned), timeline, causes and triggers, what went well and badly, action items with owner and due date. Template: `docs/postmortems/_template.md`.
- Prefer action items a machine enforces (a test, a check, an alert with a runbook, a limit, a flag) over "be more careful". Track them like any other work and review completion.

**8. Runbooks: one per alert, written for 3 a.m.** `eos ops runbook <name>` writes the template: Symptoms, Impact, Diagnose, Mitigation, Escalate, Afterwards.
- Mitigation comes before deep diagnosis and contains copy-pasteable commands for your platform (rollback, flag off, scale, fail over), never secrets (say where they live).
- Link dashboards and the exact queries; name the owner and the date last reviewed.
- Update the runbook in every postmortem where it was missing or wrong. Practise the risky steps (restore, failover) before you need them (`ops/dr-chaos`).
- `eos ops check` fails when an alert has no `runbook_url` or the linked file is missing.

**9. Security and personal-data incidents** follow the same structure plus legal duties: notification deadlines (72 hours under GDPR; see `security/privacy` for Cameroon Law 2024/017) are decided with a human who knows the law.

## Anti-patterns
- Debugging for an hour before declaring; the commander also typing the fix.
- Silence on the status page while engineers work; "we are investigating" with no next-update time.
- Root cause = "human error"; postmortems that end with "be more careful" or never get read.
- Action items without owners or dates; runbooks that say "check the logs".
- Postmortems that paste customer data, tokens or full logs.

## Checks
- `eos scaffold ops`: `docs/ops/incident-response.md`, `docs/postmortems/_template.md`, example runbook `docs/runbooks/api-slo.md`.
- `eos ops check` / `eos check`: runbook required per alert and must exist.
- Review: postmortem action items link to issues; runbooks reviewed in the last six months.

## Sources
- PagerDuty Incident Response, Severity levels: https://response.pagerduty.com/before/severity_levels/ · Roles: https://response.pagerduty.com/before/different_roles/ · External communication: https://response.pagerduty.com/during/external_communication_guidelines/ (Apache-2.0)
- PagerDuty Postmortems: https://postmortems.pagerduty.com/
- Google SRE book, Managing Incidents: https://sre.google/sre-book/managing-incidents/ · Postmortem Culture: https://sre.google/sre-book/postmortem-culture/
- Google SRE Workbook, Incident Response: https://sre.google/workbook/incident-response/
