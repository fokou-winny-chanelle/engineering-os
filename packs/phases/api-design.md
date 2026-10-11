---
id: api-design
title: API design & contracts
kind: phase
mode: both
when: designing or changing HTTP/gRPC/GraphQL/event contracts
description: Use when designing or changing an API or event contract (OpenAPI, GraphQL, webhooks): versioning, errors, pagination, idempotency.
globs: ["**/openapi*.yaml", "**/openapi*.yml", "**/openapi*.json", "**/contracts/**", "**/*.proto", "**/*.graphql", "**/asyncapi*", "**/routes/**", "**/routers/**", "**/controllers/**", "**/webhooks/**"]
next: [backend, frontend, testing-qa]
---
# API design & contracts

## Entry
Requirements (ACs) and the data model are known, and the consumers of the API are named.

## Standards
1. Contract first. The spec (OpenAPI 3.1, protobuf, GraphQL SDL, AsyncAPI) is the source of truth and is committed in `contracts/`. Clients and types are generated from it, never hand-written twice.
2. Consistency.
   - Plural resource nouns.
   - Use one casing convention across the whole API.
   - ISO-8601 UTC timestamps.
   - Opaque string IDs.
   - Money as `{amount_minor: int, currency: "XAF"}` or a decimal string, never a float.
3. Errors use RFC 9457 Problem Details (`type`, `title`, `status`, `detail`, `instance`) plus a stable machine `code`. Never leak stack traces or SQL.
4. Idempotency. POST endpoints that create money movements or other side effects accept an `Idempotency-Key`. Store the key with the response; replays return the same response.
5. Pagination. Use cursor-based pagination for lists, with a maximum page size. Filtering and sorting fields come from an allow-list.
6. Versioning and compatibility. Additive changes only within a version. Breaking changes need a new version or field plus a deprecation window (`Deprecation`/`Sunset` headers). Run a breaking-change diff in CI.
7. Security in the contract.
   - The auth scheme is declared on every operation.
   - Scopes and roles are documented.
   - Rate limits, request size limits and input bounds (`maxLength`, `minimum`, enums) are set.
   - Use `additionalProperties: false` where safe.
8. Webhooks and events.
   - Signed payloads (HMAC + timestamp) with replay protection.
   - At-least-once delivery, so consumers are idempotent.
   - Schemas are versioned. Ordering is not assumed.
9. Examples. Every operation has a request/response example, including at least one error example. Examples are validated against the schema.

## Deliverables
- An updated contract file plus a changelog entry and a migration note for consumers.
- Generated clients and types (stack pack command). Postman collection or API docs updated if used.

## Automated checks
- `eos scaffold api-contract`: Spectral lint (eos ruleset), oasdiff breaking-change gate, Schemathesis fuzzing (spec conformance).
- Proto: `buf breaking`. GraphQL: schema diff. Pact only for consumer-driven contracts.
- A generated-code-is-fresh check (regenerate, then `git diff --exit-code`).

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `api/resource-design` (naming, methods, status codes) · `api/errors-problem-details` · `api/collections` (cursors, filters) · `api/reliability` (idempotency, ETags, LRO, batch) · `api/evolution` (versioning, deprecation, oasdiff) · `api/contract-first` (OpenAPI, codegen, docs) · `api/webhooks` (outbound) · `api/rate-limits-auth` · `api/graphql` · `api/grpc-async` (proto, events, AsyncAPI) · `api/testing` (schemathesis, Pact) · `security/authorization` (BOLA) · `security/web-api-hardening` · `architecture/api-performance` (N+1, BFF).

## Exit checklist (Definition of Done)
- [ ] Spec lint is clean, and there are no unintended breaking changes (or they're versioned and announced).
- [ ] Errors, auth, limits, pagination and idempotency are defined for every new operation.
- [ ] Examples are valid, and clients are regenerated and committed.
- [ ] Consumers are informed of deprecations.

## Handoff → backend / frontend / testing-qa
Pass the contract file, the generated clients and the list of contract tests to implement.

## Stop & escalate
Stop when a breaking change is unavoidable, or when auth or permission semantics are unclear.
