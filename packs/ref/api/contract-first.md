---
id: api/contract-first
title: Contract-first with OpenAPI 3.1 - spec workflow, linting, client codegen (Next.js, mobile), docs and developer experience
area: api
read_when: starting a new API, choosing spec-first vs code-first, generating TypeScript/Kotlin/Swift/Dart clients, keeping spec and code in sync, publishing API docs or SDKs
verified: 2026-10-10
revisit_days: 180
sources: ["https://spec.openapis.org/oas/v3.1.2.html", "https://spec.openapis.org/oas/v3.2.0.html", "https://opensource.zalando.com/restful-api-guidelines/", "https://github.com/stoplightio/spectral", "https://redocly.com/docs/cli/", "https://github.com/openapi-ts/openapi-typescript", "https://openapi-ts.dev/openapi-fetch/", "https://heyapi.dev/", "https://openapi-generator.tech/docs/generators/", "https://github.com/oasdiff/oasdiff"]
---
# Contract-first with OpenAPI

The OpenAPI document is the contract: reviewed before code, linted, diffed for breaking changes, used to generate clients and to fuzz the server. It must never drift from what the server does, so CI regenerates or verifies it on every change.

## Decision guide

**1. Spec-first or code-first?**
| Approach | How | Fits | Risk |
|---|---|---|---|
| **Spec-first** (design-first) | write `openapi.yaml`, review it as the design, generate server stubs or validate requests against it | public/partner APIs, several client teams, mobile, polyglot | spec and handlers drift unless validated at runtime or by fuzz tests |
| Code-first with export | framework emits the spec (FastAPI, NestJS swagger, drf-spectacular, springdoc, zod-openapi); CI exports it to a committed file | one team owns server and clients, fast iteration | design review happens in code; annotations get lazy (missing errors, examples) |
Either way: **one committed spec file per API** (`openapi.yaml`), regenerated in CI and failing the build if the committed copy differs (`git diff --exit-code`). That committed file is what Spectral, oasdiff, codegen and Schemathesis read. Zalando requires API-first design with the spec as the single source of truth.

**2. Version of OpenAPI.** Author **3.1** (3.1.2 is the latest patch). 3.1 uses JSON Schema 2020-12 (`type: [string, "null"]` instead of `nullable`, `examples` arrays, `const`). OpenAPI 3.2.0 (September 2025) adds streaming/sequential media types such as server-sent events and more; adopt it only once every tool in your chain (linter, diff, generator, docs, fuzzer) supports it. Most generators still accept 3.0 best; check yours before using 3.1-only features.

**3. Writing a good spec (review checklist).**
- `info` with description, contact, `servers`; `tags` with descriptions.
- Every operation: `operationId` (stable, becomes the client method name: `listOrders`, `createOrder`), summary, description, tags.
- Shared `components`: `Problem` schema and error responses, `Money`, pagination params, `Idempotency-Key` header, security schemes.
- Every schema property typed with formats (`date-time`, `uuid`, `email`), `maxLength`/`maximum` on inputs (bounds are security), `required` lists, `additionalProperties` decided.
- Realistic `examples` for requests, responses and errors (docs and mock servers use them).
- `security` declared globally, `security: []` on public endpoints explicitly.
- Split large specs into files with `$ref`, bundle for tools (`redocly bundle`).

**4. Lint and gate (scaffold `api-contract`).** `.spectral.yaml` extends `spectral:oas` and adds eos rules (naming, problem details, pagination, idempotency, sunset, security, money, timestamps). `oasdiff breaking` blocks incompatible changes (`api/evolution`). Exempt a rule with a Spectral `overrides` entry and a comment saying why, not by disabling it globally. Redocly CLI (`redocly lint`, `bundle`, `build-docs`) is an alternative or complement.

**5. Generate clients; never hand-write fetch calls against a documented API.**
| Client | Tool (versions checked 2026-10-10) | Notes |
|---|---|---|
| Next.js / React / Node (types only) | `openapi-typescript` 7.13 + `openapi-fetch` 0.17 | types from the spec, tiny runtime; type-checked paths, params and bodies; works in Server Components, Route Handlers and the browser |
| Next.js with SDK + query hooks + validators | `@hey-api/openapi-ts` 0.99 | plugins for Next.js client, TanStack Query, Zod; pre-1.0, so pin the exact version |
| TypeScript, alternative | Orval 8.x | React Query/SWR hooks, MSW mocks |
| Android (Kotlin), iOS (Swift), Flutter (Dart) | OpenAPI Generator 7.26 (`kotlin`, `swift6`, `dart`/`dart-dio`) | `swift5` is marked deprecated; run it via Docker or the npm wrapper with a pinned version |
| Python consumers | `openapi-python-client` or OpenAPI Generator `python` | |
- Generate in CI or a `make gen` target, and commit the output or a lockfile-pinned generator; CI fails if regenerating changes files ("generated code is fresh", api-design pack).
- Next.js: call the API from server code with the user's token forwarded (or a BFF route), not with a privileged service key in the browser. Keep `NEXT_PUBLIC_*` free of secrets (`security/secrets-keys`).
- Mobile: generated models must tolerate unknown fields and unknown enum values (configure the generator: e.g. Kotlin serialization `ignoreUnknownKeys`, an `unknown` enum fallback), because old app versions live for years.
- Validate at the edges: zod/valibot schemas generated from the spec in the client are optional; server-side validation is mandatory.

**6. Docs and developer experience.**
- Publish reference docs from the same spec (Redocly, Scalar, Swagger UI, Stoplight Elements); never maintain a second hand-written reference.
- Add guides the spec cannot express: authentication walkthrough, pagination loop, idempotency and retries, webhooks verification, error catalogue, rate limits, changelog and deprecation schedule.
- A quickstart that works in under five minutes with copy-paste `curl`, a sandbox/test mode with test credentials, and request ids in every response so support can find logs.
- Mock server from examples (Prism, MSW) lets frontend and mobile start before the backend is ready.
- Changelog per release generated with `oasdiff changelog`.

## Anti-patterns
- Spec written once for a proposal and never updated; generated docs that lie.
- Clients hand-coded from reading docs, or copied types drifting from the server.
- `operationId`s auto-generated from paths (`get_orders_v1_orders_get`) that become ugly, unstable SDK method names.
- Inline anonymous schemas everywhere (unreadable generated types); no `components`.
- Unbounded strings and arrays in request schemas.
- Committing generated code without a freshness check.

## Checks
- CI: export or bundle the spec, `git diff --exit-code` on it; Spectral lint; oasdiff breaking; regenerate clients and diff.
- Schemathesis against a running server proves spec and behaviour agree (`api/testing`).
- Review: new endpoint PRs include the spec change, examples and the error codes.

## Sources
- OpenAPI Specification 3.1.2: https://spec.openapis.org/oas/v3.1.2.html · 3.2.0: https://spec.openapis.org/oas/v3.2.0.html
- Zalando RESTful API Guidelines (API first): https://opensource.zalando.com/restful-api-guidelines/
- Spectral: https://github.com/stoplightio/spectral · Redocly CLI: https://redocly.com/docs/cli/
- openapi-typescript: https://github.com/openapi-ts/openapi-typescript · openapi-fetch: https://openapi-ts.dev/openapi-fetch/
- Hey API: https://heyapi.dev/ · OpenAPI Generator generators: https://openapi-generator.tech/docs/generators/
- oasdiff (breaking, changelog): https://github.com/oasdiff/oasdiff
