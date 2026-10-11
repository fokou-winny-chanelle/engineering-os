---
id: api/testing
title: API testing - contract lint, spec conformance, Schemathesis property-based fuzzing, consumer-driven contracts (Pact), breaking-change and security tests
area: api
read_when: setting up API tests or CI for an API, fuzzing an OpenAPI service, deciding whether Pact is worth it, testing webhooks, idempotency or auth at the API level
verified: 2026-10-10
revisit_days: 180
sources: ["https://schemathesis.readthedocs.io/en/stable/", "https://github.com/schemathesis/schemathesis", "https://pypi.org/project/schemathesis/", "https://docs.pact.io/", "https://docs.pact.io/getting_started/what_is_pact_good_for", "https://github.com/stoplightio/spectral", "https://github.com/oasdiff/oasdiff", "https://buf.build/docs/breaking/"]
---
# API testing

Layer the tests from cheap and static to slow and live. The spec is the oracle: tooling generates many requests from it and checks that the server keeps its promises, which finds crashes and drift that hand-written examples miss. Generic test strategy (pyramid, flaky tests, coverage) is in the testing-qa pack; security testing in `security/security-testing`.

## Decision guide

**1. The layers.**
| Layer | Tool | Runs | Catches |
|---|---|---|---|
| Contract lint | Spectral (`.spectral.yaml`) | every PR touching the spec, seconds | naming, missing errors/pagination/security, money as float |
| Breaking-change diff | oasdiff (OpenAPI), `buf breaking` (proto), GraphQL schema diff | every PR | incompatible changes before merge (`api/evolution`) |
| Handler unit/integration tests | pytest + httpx/TestClient, Vitest/Jest + supertest, Next.js route handler tests | every PR | business rules, auth per object, idempotency, error codes |
| **Spec conformance fuzzing** | **Schemathesis** against a running instance | PR (short) and nightly (long) | 5xx on odd input, responses not matching the schema, undocumented status codes, auth not enforced |
| Consumer-driven contracts | Pact | when consumers and provider are separate deployables you own | provider changes that break a specific consumer |
| End-to-end | Playwright / mobile UI tests on key journeys | pre-release | wiring, config |
| Load and soak | k6, Locust | before launch and big changes | latency, limits (`performance-scale` pack) |

**2. Schemathesis (property-based testing from the spec).** Version 4.30.1 (PyPI, MIT), run with `uvx` so nothing is installed into the app:
```bash
uvx schemathesis==4.30.1 run openapi.yaml --url http://127.0.0.1:8000 \
  -H "Authorization: Bearer $TEST_TOKEN" --max-examples 50 \
  --report junit --report-dir schemathesis-report
# or load the live spec: run http://127.0.0.1:8000/openapi.json --wait-for-schema 30
```
- All checks are on by default: `not_a_server_error`, `status_code_conformance`, `content_type_conformance`, `response_headers_conformance`, `response_schema_conformance`, `negative_data_rejection` (invalid input must be rejected), `positive_data_acceptance`, `missing_required_header`, `unsupported_method`, `allow_header_conformance`, `use_after_free` (deleted resources must stay gone), `ensure_resource_availability` (created resources are immediately fetchable), `ignored_auth` (secured endpoints must refuse requests without valid credentials). Narrow with `--checks` or `--exclude-checks` only with a written reason.
- Phases: `examples` (your spec examples), `coverage`, `fuzzing`, `stateful` (chains calls using OpenAPI links, e.g. create then get then delete). Use `--phases` to keep PR runs short; run everything nightly with a higher `--max-examples`.
- Run against a disposable environment with a seeded test database and test credentials, never production: fuzzing creates and deletes data and sends hostile input.
- Pytest integration exists for custom auth, hooks and per-endpoint tuning.
- The eos scaffold (`api-contract`) adds `api-fuzz.yml`: starts the app (a per-stack command you edit; disposable database only), waits for it, runs Schemathesis (short on PRs, with stateful tests nightly) and writes a JUnit report. It installs Schemathesis via `uvx` at a pinned version instead of the official action, because that action references third-party actions by tag and installs the latest Schemathesis.

**3. Pact: when it fits.** Pact's own guidance: valuable when you control both consumer and provider, both are under active development, and consumers can be identified, e.g. microservices inside one organisation or a mobile/web app and its BFF owned by one team. Not a good fit for public APIs (unknown consumers), for pass-through APIs such as BFFs that just forward, when the provider team will not run Pact, or for functional and performance testing. For a monorepo where one PR changes both sides, typed generated clients plus oasdiff and Schemathesis usually give most of the value with less machinery. Versions checked: pact-js 17.1.4, pact-python 3.4.1.

**4. Must-have API test cases (write them by hand; fuzzers do not know your rules).**
- **AuthZ:** user A cannot read, update or delete tenant B's object (expect 404); a lower role cannot call admin operations; scopes enforced (`security/authorization`).
- **Idempotency:** same key twice → one effect, same response; same key + different body → rejected; parallel duplicates → one 409 (`api/reliability`).
- **Concurrency:** stale `If-Match` → 412.
- **Validation and errors:** each documented `code` is produced by some test; error bodies are problem JSON; no stack traces.
- **Pagination:** walking all pages while inserting rows gives no duplicates or gaps; cursor reused with other filters → 400.
- **Rate limits:** burst → 429 with `Retry-After`.
- **Deprecation:** deprecated endpoints return `Deprecation` and `Sunset` headers.
- **Webhooks:** signature verifies with the library's test vectors; redelivery is deduplicated (`api/webhooks`).
- **Money:** amounts round-trip exactly (minor units or decimal strings).

**5. Frontend and mobile against the API.** Use generated clients so type errors surface at build time (`api/contract-first`); mock with MSW or Prism from spec examples, but keep at least one CI job against a real backend so mocks cannot drift silently.

## Anti-patterns
- Testing only the happy path with examples copied from the spec.
- Fuzzing production, or a shared staging database other people use.
- Excluding Schemathesis checks wholesale to get green.
- Pact for a public API or between two modules in one deployable.
- Mocks that never touch the real API in CI.
- No test proving cross-tenant access fails.

## Checks
- CI: Spectral + oasdiff on spec changes (`api-contract.yml`), Schemathesis on PRs or nightly (`api-fuzz.yml`), unit/integration tests for the cases in section 4.
- `eos scaffold security-tests` for authz and webhook-signature tests (`security/security-testing`).
- Review: every bug found in production gets a regression test at the lowest layer that would have caught it.

## Sources
- Schemathesis documentation: https://schemathesis.readthedocs.io/en/stable/ · repository: https://github.com/schemathesis/schemathesis · PyPI: https://pypi.org/project/schemathesis/
- Pact documentation: https://docs.pact.io/ · What Pact is good for: https://docs.pact.io/getting_started/what_is_pact_good_for
- Spectral: https://github.com/stoplightio/spectral
- oasdiff: https://github.com/oasdiff/oasdiff · buf breaking: https://buf.build/docs/breaking/
