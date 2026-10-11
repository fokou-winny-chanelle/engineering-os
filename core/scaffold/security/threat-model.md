# Threat model: <system or feature>
<!-- Keep it to one page. Redo it when a trust boundary, data class or money flow changes. Workflow: .eos/packs/ref/security/threat-modeling.md -->
- **Date:** YYYY-MM-DD · **Owner:** <name> · **Reviewed by:** <a second human>

## What we are protecting
| Asset | Class (public / internal / PII / money / secret) | Where it lives |
|---|---|---|

## Trust boundaries and entry points
<!-- Diagram link or a list: browser -> API, API -> DB, API -> payment provider, webhooks in, admin UI, CI/CD. -->

## Threats (STRIDE per entry point)
| Entry point | Threat (S/T/R/I/D/E) | Example | Mitigation | Test / check that proves it | Status |
|---|---|---|---|---|---|
| POST /payments | Tampering | amount changed client-side | server recomputes amount from order | tests/test_payments.py::test_amount_from_server | done |

## Privacy threats (LINDDUN; only when personal data flows)
| Data flow | Category (Linking / Identifying / Non-repudiation / Detecting / Disclosure / Unawareness / Non-compliance) | Example | Mitigation | Status |
|---|---|---|---|---|

## Money and state rules (human-confirmed)
<!-- Idempotency keys, double-spend, rounding (integer minor units), reconciliation, refunds. -->

## Abuse cases
<!-- Rate limits, enumeration, account takeover, webhook replay, SSRF via URLs users give us. -->

## Residual risks accepted
| Risk | Why accepted | Owner | Expires / revisit when |
|---|---|---|---|
