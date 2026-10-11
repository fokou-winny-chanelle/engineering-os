# Decision matrices (read on demand by the decisions pack)

How to use these matrices:

1. Answer §0. Write "unknown" where you don't know.
2. In each matrix, start from the **Default**.
3. Leave the default only if a listed **Switch when** condition is true for this product. Name that condition in the ADR.
4. One-way doors (marked 🚪) need a human decision.

Check versions, prices and limits against the vendor's current docs. Nothing here is a price quote.

## 0. Questionnaire (copy into the ADR context)

| # | Question | Answer |
|---|---|---|
| 1 | Product type: web app, API, mobile, data/ML, internal tool, CLI/library? | |
| 2 | Users in 12 months (order of magnitude) and peak concurrent? | |
| 3 | Where are users? Network and device quality (low-end Android, 3G, data cost)? | |
| 4 | Money flows (payments, wallets, mobile money)? Card data? | |
| 5 | Personal or sensitive data? Which laws apply (e.g. GDPR, Cameroon Law 2024/017)? Residency limits? | |
| 6 | Availability need (minutes of downtime per month acceptable)? | |
| 7 | Team: size, languages they know well, who runs production at 3 a.m.? | |
| 8 | Budget ceiling per month for infra and SaaS (from a human, not guessed)? | |
| 9 | Time to first release? | |
| 10 | Must integrate with (existing systems, identity provider, ERP, telco/USSD)? | |
| 11 | Offline use required? | |
| 12 | LLM/agent features in the product? | |

## 1. Application stack 🚪

**Default:** what the team already knows best, as long as it is mainstream: TypeScript (Next.js / Node) or Python (FastAPI / Django / Flask), with PostgreSQL. Agents also produce better code in well-known, stable stacks.

| Switch when | Consider |
|---|---|
| Heavy CPU, low latency, small memory | Go, Rust, Java/Kotlin |
| Big existing JVM/.NET estate or team | Kotlin/Java (Spring), C#/.NET |
| Realtime with many concurrent connections | Elixir/Phoenix, Go, Node with care |
| Data/ML heavy | Python for ML code; keep the product API in the team's main stack |
| CRUD admin, small team, speed matters most | Django or Rails-style "batteries included" frameworks, or the internal-tool options in §8 |

## 2. Database 🚪

**Default:** PostgreSQL (managed). It covers relational data, JSONB, full-text search, queues for small volumes, and vectors (pgvector) for small/medium use.

| Need | Default answer | Switch when |
|---|---|---|
| Cache / rate limits / sessions | Redis-compatible store | — |
| Search beyond Postgres FTS | OpenSearch/Elasticsearch, Meilisearch, Typesense | Relevance tuning, facets at scale, many languages |
| Analytics | Postgres read replica, then a column store (ClickHouse, BigQuery, DuckDB for local) | Scans over millions of rows slow down the OLTP DB |
| Huge write-heavy key/time-series | Cassandra/ScyllaDB, DynamoDB, TimescaleDB | Measured write rate beyond a tuned Postgres; access by key only |
| Offline-first mobile sync | SQLite on device, plus a sync engine or your own sync API | Always for offline apps; pick the sync approach in an ADR |
| Documents with no relations | Still Postgres JSONB | Only if a specific document DB feature is required |

Never: a different database per microservice "because microservices", before there is a team per service.

## 3. Hosting 🚪 (partly)

**Default:** a managed platform (PaaS or serverless containers) in one region close to users, with managed Postgres. Use infrastructure as code from day one.

| Situation | Consider |
|---|---|
| Small team, web app/API, no special compliance | PaaS / container platforms (e.g. Fly.io, Render, Railway, Google Cloud Run, AWS App Runner, Azure Container Apps). Check region availability |
| Static/edge-heavy frontend | Vercel, Netlify, Cloudflare Pages |
| Enterprise, compliance, many services | AWS / GCP / Azure with a landing zone; Kubernetes only with a platform team |
| Data must stay in-country, or there's a latency need in Central/West Africa | Check local or regional data centres and the law (§0 Q5). Measure latency from user networks before deciding |
| Cost-sensitive steady load | VMs or containers on a cheaper provider plus managed DB; more ops work |

Kubernetes is a one-way door for team skills. Choose it for a reason (many services, platform team), not by default.

## 4. Authentication 🚪

**Default:** don't build it. Use a managed identity provider or a well-maintained library, with sessions in httpOnly cookies, MFA for admins and OAuth/OIDC for social or enterprise login.

| Situation | Consider |
|---|---|
| B2C web/mobile, small team | Managed auth (e.g. Auth0, Clerk, Firebase Auth, Supabase Auth, Amazon Cognito) |
| Self-hosted / data residency | Keycloak, Ory, Authentik, or a framework library (e.g. Better Auth, Django allauth) |
| Enterprise customers | SSO via SAML/OIDC and SCIM provisioning. Pick a provider that supports both |
| Phone-first users (Africa) | Phone number + OTP. Plan for SMS cost and fraud (SMS pumping), and offer WhatsApp/voice fallback |
| Passwordless | Passkeys (WebAuthn) where devices support them |

Always: rate-limit login and OTP, log auth events, and support account recovery that can't be socially engineered easily.

## 5. Monolith vs services 🚪

**Default:** a modular monolith with clear modules and one database (schemas per module). Plus a separate worker process for background jobs.

| Switch when (needs all of: measured need + team to own it) | Do |
|---|---|
| One module needs very different scaling or runtime (e.g. ML inference, video) | Extract that one service |
| Separate teams blocked by shared deploys | Split along team boundaries |
| Hard isolation for security or compliance (e.g. card data) | Isolate that part (smaller PCI scope) |
| Very different availability needs | Separate the critical path |

Signs you split too early: distributed transactions, chatty calls between services, one team owning many services, and local dev needing 10+ containers.

## 6. Mobile approach 🚪

| Option | Choose when | Watch out |
|---|---|---|
| **React Native + Expo** (default for TS/React teams) | Shared logic or people with a React web app; fast iteration; OTA updates for JS | Native modules for unusual hardware; keep the SDK current (about 1-year support window) |
| **Flutter** | Custom, pixel-consistent UI, heavy animation, Dart team, also targeting desktop | App size; platform look needs care; web output is less suited to SEO sites |
| **Native (Swift / Kotlin)** | Deep platform APIs (background, BLE, AR, wearables), best performance, platform-first UX | Two codebases. Consider Kotlin Multiplatform for shared logic |
| **PWA** | Content, forms, internal tools; users won't install; very low storage devices | iOS limits (push needs install to home screen, background limits); no store presence |
| **USSD / SMS** (alongside an app) | Feature-phone users, critical flows in low-connectivity areas | Telco integration and session time limits; very simple flows only |

Questions: who are the users and on which devices? Is offline needed? Which hardware APIs? What does the team know? Is a web app shared?

## 7. Build vs buy

| Capability | Default | Build when |
|---|---|---|
| Payments / mobile money | Buy (aggregator or PSP that supports local methods) | Never build card processing; build only your ledger and reconciliation |
| Email / SMS / push | Buy | — |
| Error tracking, logs, APM | Buy or managed open source (Sentry, Grafana stack, OpenTelemetry backend) | Data residency forbids SaaS → self-host |
| Search | Postgres first, then a managed engine | — |
| Feature flags | Simple in-house table first, then a vendor or OpenFeature-compatible tool | — |
| Your core domain logic | Build | Always |

Score each option on fit, total cost (build + run + maintain + exit), lock-in and how easy it is to swap, security and compliance, and team skills. Write the scores in the ADR.

## 8. Internal tools

**Default:** the main stack with an admin framework (e.g. Django admin, React-admin, Refine) when the data lives in your DB and needs real permissions. Low-code builders (e.g. Retool, Appsmith, Budibase) fit quick dashboards. Check SSO, audit log and self-hosting needs.
