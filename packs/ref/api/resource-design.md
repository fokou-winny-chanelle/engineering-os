---
id: api/resource-design
title: REST resource modelling, naming, HTTP methods and status codes
area: api
read_when: designing new endpoints or resources, naming paths and fields, choosing a method or status code, adding an action that is not CRUD, reviewing an API for consistency
verified: 2026-10-10
revisit_days: 365
sources: ["https://google.aip.dev/121", "https://google.aip.dev/122", "https://google.aip.dev/136", "https://opensource.zalando.com/restful-api-guidelines/", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design", "https://www.rfc-editor.org/rfc/rfc9110", "https://www.rfc-editor.org/rfc/rfc6585", "https://www.rfc-editor.org/rfc/rfc7396", "https://www.rfc-editor.org/rfc/rfc3339"]
adapted_from: ["https://google.aip.dev/121", "https://opensource.zalando.com/restful-api-guidelines/", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design"]
---
# Resource design, naming, methods and status codes

An API is a set of **resources** (nouns) with a small, uniform set of **methods** (verbs). Consistency matters more than any single choice: a client that learned one endpoint should be able to guess the next. Write the decision down once (this page plus the Spectral ruleset) and apply it everywhere.

## Decision guide

**1. Model resources from the domain, not the database.**
- List the things clients care about (orders, invoices, members) and how they nest. A sub-resource exists only inside its parent (`/orders/{order_id}/lines`); anything with its own life gets a top-level collection and a reference field (`customer_id`).
- Keep nesting to two levels. Deeper paths make clients carry ids they do not need.
- Do not expose tables one-to-one. Joins, internal flags and audit columns are not part of the contract; once published, they are hard to take back.
- Each resource has a stable, opaque, server-assigned id (string in JSON, even if numeric inside; JavaScript loses precision above 2^53). See `data/keys-money-time` for UUIDv7 vs sequential ids.

**2. Naming (pick one style, lint it).**
| Element | eos default (Zalando style) | Notes |
|---|---|---|
| Path segments | lowercase kebab-case, plural nouns: `/purchase-orders` | no verbs, no file extensions, no trailing slash |
| Path params | `{order_id}` | name says which resource |
| JSON properties, query params | snake_case: `created_at`, `page_size` | camelCase is fine if the whole API uses it; never mix |
| Enum values | `UPPER_SNAKE_CASE` strings | output enums that may grow must be documented as open (clients need a fallback) |
| Timestamps | `*_at`, RFC 3339 string with offset (`2026-10-10T17:00:00Z`) | dates without time: `*_on` / `YYYY-MM-DD` |
| Money | object `{ "amount_minor": 1250, "currency": "XAF" }` or decimal string | never a JSON float (`data/keys-money-time`) |
| Booleans | `is_*` / `has_*` only when it reads better; prefer an enum if a third state is likely | |

**3. Methods and their guarantees (RFC 9110).**
| Method | Use for | Safe | Idempotent | Typical success |
|---|---|---|---|---|
| GET | read one or a list | yes | yes | 200 (304 with conditional GET) |
| POST | create in a collection; custom actions | no | **no** (add an Idempotency-Key: `api/reliability`) | 201 + `Location` (create), 200, or 202 (long-running) |
| PUT | full replace at a known id (client-chosen id, upsert) | no | yes | 200 or 201; 204 if no body |
| PATCH | partial update | no | not by default | 200 with the updated resource |
| DELETE | remove | no | yes (second call → 404 or 204; document which) | 204 or 200 |

- PATCH body: JSON Merge Patch (RFC 7396, `application/merge-patch+json`) is simplest (send only changed fields; `null` removes a field). Use JSON Patch (RFC 6902) only if you need ordered operations on arrays. Clients in some languages cannot tell "absent" from "null", so define that "absent = unchanged, null = clear" and test it.
- Safe methods must not change state. Never put side effects behind GET (crawlers, prefetchers and retries call GET freely).

**4. Actions that are not CRUD: custom methods.** Prefer modelling state as a field (`status: CANCELLED` via PATCH) when the change is simple. When it has its own rules or side effects (refund, cancel, publish), use a custom method: `POST /orders/{order_id}:cancel` (Google AIP-136 style; GET for read-only computations). Or model the action as a resource (`POST /orders/{order_id}/refunds`), which also gives history. Never `POST /cancelOrder`.

**5. Status codes: a small, predictable set.**
| Code | When |
|---|---|
| 200 / 201 / 202 / 204 | OK with body / created (+`Location`, and `ETag` if you use them) / accepted for async work / OK, no body |
| 304 | conditional GET, unchanged |
| 400 | malformed request (bad JSON, wrong type, unknown query param if you are strict) |
| 401 | no or invalid credentials; MUST send `WWW-Authenticate` |
| 403 | authenticated but not allowed. For resources the caller should not know exist, answer **404** (RFC 9110 allows it; prevents id probing; `security/authorization`) |
| 404 / 405 / 406 / 415 | not found / method not allowed (+`Allow`) / cannot produce the `Accept` type / unsupported body type |
| 409 | state conflict (duplicate unique key, wrong state for the action, idempotency key in flight) |
| 412 / 428 | `If-Match` failed / precondition required (`api/reliability`) |
| 422 | well-formed but fails business validation (Unprocessable Content) |
| 429 | rate limited (+`Retry-After`; `api/rate-limits-auth`) |
| 500 / 502 / 503 / 504 | bug / bad upstream / overloaded or maintenance (+`Retry-After`) / upstream timeout |

Pick 400 vs 422 once and document it (eos default: 400 for syntax and type errors, 422 for rule violations). All error bodies are problem details (`api/errors-problem-details`).

**6. Response shape.**
- Top-level JSON is always an object, never a bare array: `{ "items": [...], "next_cursor": "..." }` leaves room to add fields later (`api/collections`).
- Return the full resource after create/update so clients need no second GET.
- Absent and `null` mean the same thing in responses; do not use both to signal different states.
- Clients must ignore unknown fields (say so in the docs); servers decide whether to reject unknown input fields (strict = fewer silent typos, Azure's choice; lenient = easier rollouts). Be explicit either way.

## Anti-patterns
- Verbs in paths (`/getUsers`, `/orders/create`) or RPC over POST for reads.
- One endpoint returning different shapes depending on flags; `?fields=` or `?expand=` is fine if typed in the spec.
- 200 with `{ "success": false }`; error status hidden in the body.
- 500 for client mistakes (validation leaking as exceptions).
- 403 that confirms another tenant's resource exists.
- Mixed casing, plural/singular mix, or dates as epoch numbers in one place and strings in another.
- Exposing auto-increment database ids as the public id of sensitive resources (enumeration).

## Checks
- `.spectral.yaml` (scaffold `api-contract`): `eos-path-kebab-case`, `eos-path-no-crud-verbs`, `eos-list-response-is-object`, `eos-timestamp-format`, `eos-money-not-float`, `eos-operation-documents-4xx`.
- Review: for each new endpoint, which resource is it, and could a client guess the path?
- Schemathesis `status_code_conformance` and `unsupported_method` checks catch undocumented codes (`api/testing`).

## Sources
- Google AIP-121 resource-oriented design: https://google.aip.dev/121 · AIP-122 names: https://google.aip.dev/122 · AIP-136 custom methods: https://google.aip.dev/136
- Zalando RESTful API Guidelines: https://opensource.zalando.com/restful-api-guidelines/
- Microsoft Azure REST API Guidelines: https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- Azure Architecture Center, RESTful API design: https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design
- RFC 9110 HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110 · RFC 6585: https://www.rfc-editor.org/rfc/rfc6585
- RFC 7396 JSON Merge Patch: https://www.rfc-editor.org/rfc/rfc7396 · RFC 3339: https://www.rfc-editor.org/rfc/rfc3339

## Attribution
Adapted from "API Improvement Proposals" by Google (https://google.aip.dev/121), "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/), "Microsoft Azure REST API Guidelines" by Microsoft (https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) and "Web API design best practices" by Microsoft, Azure Architecture Center (https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design), all licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined with each other and with RFC text, and eos defaults added. Not endorsed by the original authors.
