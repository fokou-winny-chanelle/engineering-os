# Service: {{NAME}}

- **Purpose:** <one sentence: the business capability this service owns>
- **Owner:** {{OWNER}}  ·  **On-call / escalation:** <rota or channel>
- **Contract:** `{{CONTRACT}}` (the only way other services talk to this one; change it additively)
- **Data:** owns <store>; no other service reads it directly
- **Depends on:** <services/contracts it consumes, with timeouts and fallbacks>
- **SLO:** <e.g. 99.9% of requests < 300 ms over 30 days>
- **Run locally:** `docker compose up {{NAME}} --wait` (root compose.yaml)
- **Runbook:** <link>

Code skeleton: copy the best existing service or use the framework's generator; then fill this file.
