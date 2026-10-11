---
id: analytics/product-events
title: Product analytics and event tracking (tracking plan, object-action naming, required properties, identity, server vs client events, privacy-respecting analytics, consent in Cameroon and the EU)
area: analytics
read_when: adding or renaming analytics events, choosing an analytics tool (PostHog, Plausible, GA, Segment), designing a tracking plan, deciding what user data events may carry, or adding a consent banner or opt-out
verified: 2026-10-11
revisit_days: 180
sources: ["https://www.twilio.com/docs/segment/protocols/tracking-plan/best-practices.md", "https://posthog.com/docs/product-analytics/privacy", "https://plausible.io/data-policy", "https://cnil.fr/en/sheet-ndeg16-use-analytics-your-websites-and-applications", "https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web", "https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf"]
---
# Product events people can trust

Events answer product questions ("where do users drop out of a transfer?"). They are a data product with a schema, an owner and personal-data risk, not a free-for-all of `track()` calls. The one idea: **a small tracking plan in git, few events with rich typed properties, no personal data in properties, and consent rules decided before the first event ships.**

## Decision guide

**1. Tracking plan first.** One file in git lists every event: name, why it exists (the question it answers), when it fires, properties with types and allowed values, owner, and whether it is client- or server-side. Segment's guidance: start with a minimal number of core events tied to business objectives, rich properties, one naming convention enforced everywhere, and **never build event names dynamically** (no `User Signed Up (11-01-2019)`).

**2. Naming.** Object + action in the past tense: `Transfer Completed`, `Merchant Onboarded`, `Payment Failed` (Segment uses Title Case for events and `snake_case` for properties). Any convention works if it is enforced; mixing `transfer_completed`, `TransferComplete` and `completed transfer` makes three events. Variable detail goes in properties (`channel: ussd|app|web`, `failure_reason`), not names.

**3. Server events for facts, client events for behaviour.** Money and state changes (`Payment Completed`, `Loan Disbursed`) are emitted by the backend after commit, with the transaction id; ad blockers, flaky networks and app kills make client counts low and noisy. Client events cover UI behaviour (screen viewed, button tapped, form abandoned). Never compute revenue from client events; reconcile with the ledger.

**4. Identity.** Use an internal, random user id (not phone number or email) as the analytics id. Anonymous ids before login, linked at login if consent allows. Delete or anonymise the analytics profile when the account is erased (`data/history-retention`).

**5. What properties may contain.** Ids, enums, counts, amounts in minor units, coarse location (region, not GPS), app version, network type. **Not**: names, phone numbers/MSISDN, emails, national ID numbers, dates of birth, free-text fields, full URLs with query strings (they leak tokens and emails). The `eos-analytics-pii-*` Semgrep rules from `eos scaffold analytics` flag these keys in `track`/`capture`/`logEvent` calls. Pseudonymised ids are still personal data (WP29 Opinion 05/2014: pseudonymisation is not anonymisation).

**6. Tool choice by privacy posture.**
| Option | What the vendor documents | Fit |
|---|---|---|
| Plausible (cookieless) | no cookies or local storage; a daily identifier `hash(daily_salt + website_domain + ip_address + user_agent)`, salt rotated and deleted every 24 h, raw IP and User-Agent never stored | web traffic and funnels without per-user history |
| PostHog | EU cloud option; IP capture can be disabled per organisation/project (EU organisations default to disabled); `before_send` to strip properties; cookieless mode; opt-out by default (`opt_out_capturing_by_default`) | product analytics with funnels, cohorts, flags; self-host possible |
| Your own pipeline (events table → warehouse) | whatever you build | full control; you own deletion, access and retention |
Whatever you pick: data processing agreement, region, retention setting, and the vendor in your data inventory.

**7. Consent.**
- **EU/France (ePrivacy, CNIL):** trackers need consent, except audience-measurement trackers that meet all of CNIL's conditions: users informed and able to object; purpose limited to audience measurement (and A/B testing); no cross-checking with other processing; scope limited to one publisher; last byte of the IP truncated; tracker lifetime at most 13 months. CNIL notes national positions vary.
- **Cameroon (Law No. 2024/017, from an OCR of the official text):** Section 9(1) makes processing subject to the data subject's prior, informed, specific and unambiguous consent; the waivers in Section 9(2) are legal obligation, a public-interest task and protecting health; consent of a person under 18 requires a parent or legal representative (Section 9(3)). We found no general "legitimate interest" basis in that text, so plan analytics that identify users on consent, and confirm with counsel.
- Practical default: essential, aggregate, cookieless measurement on; identified product analytics, session replay and marketing pixels only after opt-in; a working opt-out everywhere; the choice stored and honoured by server-side events too.

## Examples
```yaml
# analytics/tracking-plan.yml (excerpt)
- event: Transfer Completed
  owner: payments-product
  question: Which channels complete transfers, and how fast?
  source: server            # emitted after the ledger commit
  properties:
    transfer_id: {type: string}
    channel: {type: string, enum: [app, ussd, web]}
    amount_xaf: {type: integer}
    seconds_from_start: {type: integer}
```
Bad: `posthog.capture("transfer_" + status, {phone: user.msisdn, note: form.note})`: dynamic name, a phone number and free text.

## Anti-patterns
- Autocapture everything and "figure it out later"; hundreds of unowned events.
- Phone numbers or emails as analytics ids or properties; session replay on payment or KYC screens.
- Revenue dashboards built on client events.
- A consent banner whose "refuse" button does nothing, or server-side events that ignore the user's choice.
- **When NOT to add a product analytics tool:** before you have questions; server logs, the database and a few SQL queries answer early ones.

## Checks
- [ ] Tracking plan in git; every `track` call matches a planned event (review in PRs).
- [ ] No personal data in event properties (Semgrep `eos-analytics-pii-*`); free text and full URLs stripped (`before_send` or equivalent).
- [ ] Consent decision documented per market; refusal and opt-out tested end to end.
- [ ] Analytics vendor in the data inventory with region, retention, DPA and deletion path.

## Sources
- Segment/Twilio, Data collection best practices (tracking plan, naming, no dynamic names): https://www.twilio.com/docs/segment/protocols/tracking-plan/best-practices.md
- PostHog privacy controls: https://posthog.com/docs/product-analytics/privacy
- Plausible data policy (daily salted hash): https://plausible.io/data-policy
- CNIL sheet 16, analytics and consent exemption: https://cnil.fr/en/sheet-ndeg16-use-analytics-your-websites-and-applications
- Cameroon Law No. 2024/017 (Sections 5 and 9): https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
- Article 29 Working Party, Opinion 05/2014 on anonymisation techniques: https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf
