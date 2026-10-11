---
id: ops/africa-connectivity
title: Operating in low-connectivity regions and Africa (latency, cable outages, cloud regions, data residency, mobile-money provider outages and callbacks)
area: ops
read_when: serving users in Africa or other low-connectivity regions, choosing a cloud region, integrating MTN MoMo, M-PESA or another mobile-money API, planning for provider maintenance or a cable outage, data-residency questions
verified: 2026-10-10
revisit_days: 120
sources: ["https://www.itu.int/itu-d/reports/statistics/2025/10/15/ff25-internet-use/", "https://www.internetsociety.org/resources/doc/2024/2024-west-africa-submarine-cable-outage-report/", "https://blog.cloudflare.com/undersea-cable-failures-cause-internet-disruptions-across-africa-march-14-2024/", "https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html", "https://cloud.google.com/compute/docs/regions-zones", "https://azure.microsoft.com/en-us/explore/global-infrastructure/geographies/", "https://momodeveloper.mtn.com/content/html_widgets/qoftb.html", "https://www.safaricom.co.ke/media-center-landing/press-releases/m-pesa-service-resumption"]
---
# Operating in low-connectivity regions and Africa

Design for slow, expensive, intermittent networks and for providers that go down, and test that way. Your users' network is part of your system even though you do not run it.

## Decision guide

**1. Know the baseline.** ITU Facts and Figures 2025: 74% of the world's population is online, but the average for Africa is 36%. Many users are on mobile data, prepaid, on mid-range Android phones; bandwidth and data cost shape behaviour.

**2. Expect regional outages, not only your own.** On 13–14 March 2024 damage to the WACS, MainOne, SAT-3 and ACE submarine cables off Côte d'Ivoire affected Internet connectivity in 13 countries (Benin, Burkina Faso, Cameroon, Côte d'Ivoire, Gambia, Ghana, Guinea, Liberia, Namibia, Niger, Nigeria, South Africa, Togo), from degraded service to near-total outages, with repairs taking weeks (Internet Society report; Cloudflare's write-up of the same event). The report notes that Internet exchange points (IXPs) stayed operational, so content reachable through them stayed reachable.
- Consequence: a service hosted abroad can be unreachable for local users while local networks still work. Keep a degraded mode (cached content, queued actions) and status messages that do not depend on the same path. Where it matters, serve static assets from a CDN with local points of presence.
- Your incident comms (`ops/incident-runbooks`) should say "regional network issue" honestly when that is the cause; check public sources (Cloudflare Radar, operator notices) before blaming your code.

**3. Choose a region by latency, residency and services, not habit.** Hyperscaler regions on the continent are in South Africa: AWS `af-south-1` (Cape Town; an opt-in region you must enable), Google Cloud `africa-south1` (Johannesburg), Azure South Africa North and South Africa West. For West and Central Africa these may or may not beat a European region on latency: measure from your users' networks (synthetic checks from the target countries, RUM timings from real clients) before deciding. Check that each managed service you need exists in that region.

**4. Data residency is a legal question first.** Where data is stored and processed can be a cross-border transfer under local law (Cameroon Law No. 2024/017, GDPR Chapter V): see `security/privacy`. Record each processor's storage location; keep personal data in the region your legal review requires, and keep logs and traces (`ops/opentelemetry`) under the same rules, since they often contain personal data.

**5. Mobile money: assume callbacks get lost and providers pause.**
- MTN MoMo API: `requesttopay` and `transfer` return `202 Accepted` and the transaction is queued; the final result arrives by callback, and "The Wallet Platform will only send the callback once. There is no retry"; poll the GET status endpoint when no callback arrives. Production callbacks must be https on the registered host.
- So: store the request with your own reference before calling, treat the callback as a hint and confirm by querying status server-side (`security/payments`), run a reconciliation job that polls pending transactions with backoff and settles them, and show users "pending" honestly instead of failing or retrying the charge.
- Providers schedule maintenance: Safaricom announced an M-PESA upgrade on 19 September 2025 and published "M-PESA Service Resumption" on 22 September 2025. Subscribe to provider notices, put known windows on the team calendar, and switch the payment feature into a maintenance or queued mode with a kill-switch flag (`ops/feature-flags`) instead of letting requests time out.
- Alert on provider symptoms separately (callback rate, pending-transaction age, provider error rate) and route them to a runbook, not to a generic 5xx page.

**6. Build for weak networks** (client and API):
- Small payloads: compress, paginate, avoid chatty APIs; images sized for the device; cache aggressively with validators (`architecture/caching`).
- Timeouts and retries with backoff and jitter, idempotency keys on every write so a retried request does not pay twice (`architecture/resilience`, `api/reliability`).
- Offline-first where it fits: queue user actions locally and sync later, resolve conflicts explicitly (`testing/mobile-qa` covers testing offline and slow networks).
- SMS or USSD fallbacks for critical notifications where data is unreliable.

**7. Test under real conditions.** Throttle to slow 3G profiles in browser and device tests; run synthetic checks from the countries you serve; watch p95/p99 latency per country, not only the global average.

## Anti-patterns
- Hosting in the cheapest far-away region without measuring latency from users' networks.
- Treating a mobile-money callback as guaranteed or as proof of payment; no reconciliation job.
- A health check or readiness probe that fails when the payment provider is down, taking the whole app offline.
- Status page and support channel hosted on the same path that fails during a regional outage.
- Large JavaScript bundles and uncompressed images for users paying per megabyte.

## Checks
- `eos scaffold flags`: `payments-kill-switch` operational flag ready for provider outages.
- `eos scaffold ops`: SLO + burn-rate alerts; add provider-specific alerts (pending age, callback rate) with a runbook link.
- Review: region decision recorded in an ADR with latency measurements and the residency basis; reconciliation job exists for every async payment flow.

## Sources
- ITU, Facts and Figures 2025, Internet use: https://www.itu.int/itu-d/reports/statistics/2025/10/15/ff25-internet-use/
- Internet Society, 2024 West Africa Submarine Cable Outage Report: https://www.internetsociety.org/resources/doc/2024/2024-west-africa-submarine-cable-outage-report/
- Cloudflare, Undersea cable failures cause Internet disruptions across Africa: https://blog.cloudflare.com/undersea-cable-failures-cause-internet-disruptions-across-africa-march-14-2024/
- AWS Regions: https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html · Google Cloud regions and zones: https://cloud.google.com/compute/docs/regions-zones · Azure geographies: https://azure.microsoft.com/en-us/explore/global-infrastructure/geographies/
- MTN MoMo developer FAQ (callbacks): https://momodeveloper.mtn.com/content/html_widgets/qoftb.html
- Safaricom, M-PESA Service Resumption (22 Sep 2025): https://www.safaricom.co.ke/media-center-landing/press-releases/m-pesa-service-resumption
