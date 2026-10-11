# AGENTS.md: service {{NAME}}

- Owner: {{OWNER}}. Contract: `openapi.yaml` (additive changes only; breaking = new version + ADR).
- This service owns its data. Never read another service's database; call its contract with a timeout and a fallback.
- Checks: run the commands for this directory from the root AGENTS.md table.
