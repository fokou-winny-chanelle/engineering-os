---
id: security/payments
title: Payments and fintech security (idempotency, ledger, webhooks, fraud, PCI scope)
area: security
read_when: moving money, integrating a payment provider or mobile-money API, handling payment webhooks/callbacks, building balances/wallets/ledgers, or deciding PCI scope
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.stripe.com/api/idempotent_requests", "https://docs.stripe.com/webhooks", "https://www.standardwebhooks.com/", "https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries", "https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Payment_Gateway_Integration_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html", "https://blog.pcisecuritystandards.org/important-updates-announced-for-merchants-validating-to-self-assessment-questionnaire-a", "https://blog.pcisecuritystandards.org/faq-clarifies-new-saq-a-eligibility-criteria-for-e-commerce-merchants", "https://docs.stripe.com/radar", "https://owasp.org/projects/automated-threats-to-web-applications", "https://www.six-group.com/en/products-services/financial-information/data-standards.html"]
---
# Payments and fintech security

Money bugs are security bugs: a race condition that credits twice is theft. Four properties matter: **every money operation is idempotent, every balance is derived from an append-only ledger, every inbound payment signal is authenticated and re-verified, and every flow has abuse limits.** Human review is mandatory for money code (security pack).

## Decision guide

**Idempotency (outbound and inbound):**
- Clients send an `Idempotency-Key` (random, e.g. UUIDv4; no personal data) on every create/charge/transfer request; the server stores key → (request fingerprint, status, response) and returns the saved response on retry. Stripe's API v1 behaves this way: it saves the status and body of the first request for a key (including 500s), keys are up to 255 characters, may be pruned after at least 24 hours, and a reuse with different parameters is rejected.
- Enforce it in the database: `UNIQUE (merchant_id, idempotency_key)`, insert the key **in the same transaction** as the money movement; concurrent duplicates hit the constraint, not your `if` check.
- Pass your own idempotency key to providers on every outbound call so your retries cannot double-charge.

**Ledger integrity:**
- Amounts as integers in minor units (or exact decimals) plus ISO 4217 currency; never floats. Take the minor-unit exponent per currency from the ISO 4217 list (XAF and XOF have 0 decimals).
- Double-entry, append-only `ledger_entries` (account, amount, direction, transaction id); each transaction's entries sum to zero per currency; corrections are new reversing entries, never UPDATE/DELETE.
- Balances are derived (or cached with a check) from entries; enforce non-negative balances with row locks (`SELECT … FOR UPDATE`) or serializable transactions, not read-then-write in app code.
- Daily reconciliation against provider settlement reports; mismatches page a human. See `architecture/data-consistency` for isolation levels and outbox.

**Webhooks and callbacks (inbound payment signals):**
1. Verify the signature over the **raw request body** (before JSON parsing) with HMAC-SHA-256 and a **constant-time compare** (GitHub: "never use a plain == operator"; Stripe: do not manipulate the raw body).
2. Reject stale timestamps (Stripe's libraries default to a 5-minute tolerance; Standard Webhooks signs `msg_id.timestamp.payload` and sends headers `webhook-id`, `webhook-timestamp`, `webhook-signature`).
3. Deduplicate by event id in a persistent table (providers retry and may deliver duplicates; Stripe says track event ids, do not rely on `created`).
4. Do not assume order (Stripe does not guarantee event order); fetch the current object state from the provider API when it matters.
5. Return 2xx quickly and process asynchronously (Stripe: return before complex logic).
6. **Before fulfilling, verify payment status server-side with the provider API and match amount, currency and order id** (OWASP Third-Party Payment Gateway sheet); trust only server-to-server notifications, never the browser return URL. If a provider's callbacks are unsigned, the status-API check is the only trustworthy signal.
Reference implementation and tests: `eos scaffold security-tests` (`webhook_verify.py`).

**Transaction authorization (OWASP sheet):** for high-value or new-payee transfers, require step-up authentication bound to the transaction details ("what you see is what you sign": amount, payee shown in the confirmation), server-side enforcement of the step-up, and protection against changing transaction data between authorization and execution.

**Fraud and abuse signals:** velocity per account/card/device/IP; new device + new payee + high amount; mismatched country of card, IP and phone; many failed attempts (card testing / OWASP OAT-010 Card Cracking, OAT-001 Carding); rapid account creation; SIM-swap or phone-number change before a withdrawal; refunds to a different instrument. Use the provider's risk tooling (e.g. Stripe Radar) where available and keep your own rules for wallet/mobile-money flows; send risky cases to manual review rather than silently allowing.

**PCI DSS scope reduction:**
- Best: never touch card data. Use the provider's hosted payment page (full redirect) or hosted fields/iframes; card data never reaches your servers or logs.
- SAQ A (PCI SSC, effective 31 March 2025): requirements 6.4.3 and 11.6.1 were removed from SAQ A and replaced by an eligibility criterion that the merchant confirms its site is not susceptible to attacks from scripts that could affect the e-commerce system. The FAQ clarifies this applies to pages that embed the payment iframe, not to full redirects; it can be met with 6.4.3/11.6.1-style script controls or a confirmation from the payment provider.
- Your acquirer decides which SAQ applies; confirm with them. Keep script inventories and CSP on payment pages regardless.

## Anti-patterns
- Updating `balance = balance + x` from a webhook without dedupe or ledger entry.
- Trusting the client for amount, currency, price or discount; trusting the redirect/return URL as proof of payment.
- Parsing JSON then re-serializing to verify a signature; `==` comparison of signatures; no timestamp check.
- Catching the provider timeout and retrying without the same idempotency key.
- Floats for money; rounding in several places; currency implied rather than stored.
- Logging full card numbers, CVV, mobile-money PINs or OTPs.

## Checks
- [ ] Tests (from `eos scaffold security-tests`): bad signature → 400/401; old timestamp → rejected; replayed event id → processed once; body modified after signing → rejected.
- [ ] semgrep `eos-webhook-without-signature-check` and `eos-non-constant-time-compare` pass.
- [ ] Concurrency test: two simultaneous identical requests with one idempotency key → one ledger transaction.
- [ ] Ledger invariant test: entries per transaction sum to zero; no UPDATE/DELETE on ledger tables (DB permission or trigger).
- [ ] Fulfilment code calls the provider status API and compares amount/currency/order id (test with a mismatched amount).
- [ ] Reconciliation job exists with alerting; PCI SAQ choice and eligibility evidence recorded in `docs/security/`.

## Sources
- https://docs.stripe.com/api/idempotent_requests (saved responses, 255 chars, ≥ 24 h pruning, parameter comparison)
- https://docs.stripe.com/webhooks (raw body, 2xx before complex logic, duplicates, no ordering guarantee)
- https://www.standardwebhooks.com/
- https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries (`X-Hub-Signature-256`, constant-time compare)
- https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Payment_Gateway_Integration_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html
- https://blog.pcisecuritystandards.org/important-updates-announced-for-merchants-validating-to-self-assessment-questionnaire-a
- https://blog.pcisecuritystandards.org/faq-clarifies-new-saq-a-eligibility-criteria-for-e-commerce-merchants
- https://docs.stripe.com/radar
- https://owasp.org/projects/automated-threats-to-web-applications
- https://www.six-group.com/en/products-services/financial-information/data-standards.html (ISO 4217 currency list and minor units)
