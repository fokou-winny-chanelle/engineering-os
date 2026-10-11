# Postmortem: <title> (INC-YYYYMMDD-name)

Status: draft | reviewed · Severity: SEV-? · Date: YYYY-MM-DD · Authors: <names>
Blameless: describe what the system and the process allowed, not who to blame. People acted reasonably
with what they knew at the time; if they did not, ask why the system let that happen.

## Summary
Two or three sentences a customer could read.

## Impact
Users affected, duration (start to end, UTC), failed requests or payments, money involved, SLO budget
burned (`eos ops budget`), support tickets, data affected.

## Timeline (UTC)
| Time | Event |
|---|---|
| | First bad signal (metric, user report) |
| | Detected (alert / human) |
| | Declared, severity |
| | Mitigated |
| | Resolved |

## Root causes and triggers
What made this possible (latent causes) and what set it off (trigger). Several causes are normal.

## What went well / what went badly / where we got lucky

## Action items
| Action | Type (prevent / detect / mitigate / process) | Owner | Issue | Due |
|---|---|---|---|---|
Prefer actions that a machine enforces (a test, a check, an alert with a runbook, a limit) over
"be more careful".

## Supporting material
Dashboards, traces (by trace_id), logs, PRs. No secrets or personal data in this document.
