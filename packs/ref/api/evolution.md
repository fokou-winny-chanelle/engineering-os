---
id: api/evolution
title: API evolution - compatibility rules, versioning, deprecation (Deprecation/Sunset headers), oasdiff breaking-change gate
area: api
read_when: changing an existing endpoint or field, adding enum values, planning a v2, deprecating or removing an endpoint, a breaking-change CI failure
verified: 2026-10-10
revisit_days: 180
sources: ["https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/180", "https://google.aip.dev/185", "https://google.aip.dev/181", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design", "https://www.rfc-editor.org/rfc/rfc9745", "https://www.rfc-editor.org/rfc/rfc8594", "https://docs.stripe.com/api/versioning", "https://docs.github.com/en/rest/about-the-rest-api/api-versions", "https://github.com/oasdiff/oasdiff", "https://github.com/oasdiff/oasdiff/blob/main/docs/DEPRECATION.md", "https://github.com/oasdiff/oasdiff/blob/main/docs/STABILITY.md"]
adapted_from: ["https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/180", "https://google.aip.dev/185", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design"]
---
# API evolution: compatibility, versioning, deprecation

The cheapest version is the one you never ship. Evolve one version compatibly for as long as possible; when you must break, run old and new side by side, announce a date, measure usage, then remove. Every published client (mobile apps that users never update, partner integrations) pins you to old behaviour.

## Decision guide

**1. Compatible vs breaking (rules for one version).**
| Change | Compatible? |
|---|---|
| Add an endpoint, an optional request field/param/header, a response field or header | yes, *if clients ignore unknown fields* (make that a documented client rule) |
| Add a new **output** enum value | only if the enum was documented as open. Zalando: closed enums cannot be extended; mark growing enums open (list values in `examples`) and give clients a fallback. GitHub and Stripe treat new values as additive because they documented that up front |
| Add a required request field, make optional → required, tighten validation (shorter max, new pattern) | **breaking** |
| Remove or rename a field, endpoint, param or enum value; change a type or format | **breaking** |
| Change the meaning of a field, default value, sort order, or error code for the same input | **breaking** (semantic; no diff tool sees it; AIP-180 counts it) |
| Change auth requirements or required scopes | breaking (GitHub lists it) |
| Loosen validation, make a required request field optional | compatible for requests |
| Add a new error `code` | treat as breaking unless clients were told codes are open (Azure requires a new version for new top-level codes) |
Robustness rule for clients (Zalando): ignore unknown fields, follow redirects, handle unknown enum values and unknown error codes.

**2. Versioning scheme (pick one, write it in the API docs).**
| Scheme | Example | Used by | Notes |
|---|---|---|---|
| Major version in path | `/v1/orders` | Google (AIP-185: major only, `v1` never `v1.1`) | simple, cacheable, visible; eos default for public REST |
| Dated version header/param | `Stripe-Version: 2026-09-30.endive`, `X-GitHub-Api-Version: 2026-03-10`, `?api-version=2024-01-01` | Stripe, GitHub, Azure | fine-grained; needs server-side transforms per version |
| Media type | `Accept: application/vnd.example.order+json;version=2` | Zalando (if versioning at all; never URL versioning) | precise, harder for browsers and tooling |
| No version, evolve compatibly | | Zalando's first choice | requires strict discipline and the oasdiff gate |
- Internal APIs with all consumers in one repo: no versions; change producer and consumers in one PR, gated by contract tests.
- Mobile: you cannot force updates. Keep the old version until active installs on old app versions are negligible, and ship a minimum-supported-version check in the app.
- Stripe's model: monthly non-breaking releases plus twice-yearly breaking majors; each account pins a default version. GitHub supports the previous REST version for at least 24 months after a new one.

**3. Deprecation and removal.**
1. Mark it in the spec: `deprecated: true` plus `x-sunset: "2027-06-30"` (RFC 3339 date; oasdiff reads it). Docs say what to use instead.
2. At runtime, on every response from the deprecated endpoint:
   ```
   Deprecation: @1798675200
   Sunset: Wed, 30 Jun 2027 23:59:59 GMT
   Link: <https://api.example.com/docs/migrate-v2>; rel="deprecation"
   ```
   `Deprecation` is RFC 9745 (Standards Track, March 2025): a structured-field date, `@` + Unix seconds, meaning "deprecated since". `Sunset` is RFC 8594 (Informational): an HTTP-date after which the resource may stop responding; clients must treat it as a hint. GitHub's version headers predate RFC 9745 and use an HTTP-date in `Deprecation`; for new APIs use the RFC 9745 form.
3. Measure: log calls to deprecated operations by client id / app version. Contact the remaining callers (Zalando requires client approval before shutdown and partner consent on the deprecation time span).
4. After the sunset date and once usage is near zero: return `410 Gone` with a problem body pointing to the migration guide for a period, then remove.
- Grace period: the eos oasdiff gate requires an `x-sunset` at least **180 days** away for stable operations and **31 days** for beta (`x-stability-level: beta`). Shorter for internal-only APIs is a team decision.

**4. Stability levels.** oasdiff supports `x-stability-level: draft | alpha | beta | stable`; by default `draft`/`alpha` operations are excluded from breaking-change checks and operations without a level count as `stable`. Use `beta` for endpoints you are still shaping, and say so in docs (AIP-181 has the same idea).

**5. The gate (oasdiff).** The `api-contract` scaffold runs `oasdiff breaking` on pull requests touching the spec, comparing the base branch spec to the PR spec, failing on ERR-level changes. When it fails:
- Is the change really needed? Usually you can add a new field or endpoint instead.
- If the endpoint is unreleased, mark it `x-stability-level: draft` or `alpha`.
- If it is a planned removal, deprecate with `x-sunset` first, merge, wait, then remove.
- A genuine emergency break needs a human decision recorded in an ADR, plus a notice to clients. Do not edit the base spec to silence the gate.
For gRPC use `buf breaking` (`api/grpc-async`); for GraphQL, schema diff tools in CI (`api/graphql`).

## Anti-patterns
- `/v2` for every small change, or a version per endpoint.
- Breaking changes inside a version "because only our app uses it" while an old mobile build is still in stores.
- Removing a deprecated field without measuring usage or announcing a date.
- Closed enums in responses that you will extend later; clients crash on the new value.
- Changing behaviour without changing the schema (silent semantic break).
- Hand-maintained spec that drifts from code, so the gate checks fiction (`api/contract-first`).

## Checks
- CI: `oasdiff/oasdiff-action/breaking` (SHA-pinned, `fail-on: ERR`, `deprecation-days-stable: 180`, `deprecation-days-beta: 31`, no PR comment token).
- `.spectral.yaml`: `eos-deprecated-has-sunset`.
- Runtime test: a deprecated endpoint returns `Deprecation` and `Sunset` headers.
- Dashboard or log query: calls to deprecated operations per client in the last 30 days.

## Sources
- Zalando RESTful API Guidelines (compatibility, versioning, deprecation): https://opensource.zalando.com/restful-api-guidelines/
- Google AIP-180 Backwards compatibility: https://google.aip.dev/180 · AIP-185 API versioning: https://google.aip.dev/185 · AIP-181 Stability levels: https://google.aip.dev/181
- Microsoft Azure REST API Guidelines: https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- Azure Architecture Center, API design (versioning options): https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design
- RFC 9745 Deprecation header: https://www.rfc-editor.org/rfc/rfc9745 · RFC 8594 Sunset header: https://www.rfc-editor.org/rfc/rfc8594
- Stripe API versioning: https://docs.stripe.com/api/versioning · GitHub REST API versions: https://docs.github.com/en/rest/about-the-rest-api/api-versions
- oasdiff: https://github.com/oasdiff/oasdiff · deprecation: https://github.com/oasdiff/oasdiff/blob/main/docs/DEPRECATION.md · stability: https://github.com/oasdiff/oasdiff/blob/main/docs/STABILITY.md

## Attribution
Adapted from "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/), "AIP-180 Backwards compatibility" and "AIP-185 API Versioning" by Google (https://google.aip.dev/180, https://google.aip.dev/185), "Microsoft Azure REST API Guidelines" by Microsoft (https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) and "Web API design best practices" by Microsoft, Azure Architecture Center (https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined with RFCs and vendor documentation, and eos defaults added. Not endorsed by the original authors.
