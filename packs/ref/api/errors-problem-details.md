---
id: api/errors-problem-details
title: API errors with RFC 9457 problem details (types, stable codes, validation errors, framework wiring)
area: api
read_when: designing error responses, adding a new error case, mapping exceptions to HTTP, returning validation errors, reviewing error leakage
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.rfc-editor.org/rfc/rfc9457", "https://www.rfc-editor.org/rfc/rfc9110", "https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/193", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://docs.stripe.com/api/errors"]
adapted_from: ["https://opensource.zalando.com/restful-api-guidelines/", "https://google.aip.dev/193", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md"]
---
# Errors: RFC 9457 problem details

Every error from every endpoint uses one shape, so clients write one error handler. eos uses **RFC 9457 problem details** (`application/problem+json`; it obsoletes RFC 7807) plus a stable machine-readable `code`. Error codes are part of the contract: clients branch on them, so adding, renaming or removing one is an API change (Azure's guidelines treat new top-level codes as needing a new version).

## Decision guide

**1. The shape.**
```json
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/insufficient-funds",
  "title": "Insufficient funds",
  "status": 422,
  "detail": "Balance is 3000 XAF; the transfer needs 5000 XAF.",
  "instance": "/transfers/tr_01J9Z...",
  "code": "INSUFFICIENT_FUNDS",
  "request_id": "req_7f3a..."
}
```
| Member | Rule |
|---|---|
| `type` | URI naming the problem *type*; absent means `about:blank` (then `title` is the HTTP reason phrase). If it is a URL, it should lead to a human-readable page. Clients must not fetch it automatically. RFC 9457 warns relative URIs confuse some clients; Zalando uses relative ones like `/problems/out-of-stock`. eos default: absolute https URLs under your docs domain |
| `title` | short, same for every occurrence of the type; not localised per request unless you negotiate language |
| `status` | same as the HTTP status (advisory copy for logs and proxies) |
| `detail` | this occurrence, written to help the client **fix** the problem; not debugging output. Clients SHOULD NOT parse it: put anything machine-useful in extension members |
| `instance` | URI of this occurrence (resource path or an error id) |
| extensions | eos adds `code` (UPPER_SNAKE_CASE, stable, documented per operation) and `request_id` (matches logs and the `X-Request-Id`/`traceparent` you return). Add typed fields per type (`balance`, `retry_after_seconds`) instead of encoding them in text |

**2. Validation errors: one problem, many field errors.** RFC 9457 shows an `errors` extension; use it for request validation:
```json
{ "type": "https://api.example.com/problems/validation", "title": "Request validation failed", "status": 422,
  "code": "VALIDATION_FAILED",
  "errors": [ { "pointer": "#/items/0/quantity", "code": "MIN_VALUE", "detail": "must be at least 1" },
              { "pointer": "#/email", "code": "INVALID_FORMAT", "detail": "not an email address" } ] }
```
Use JSON Pointer (RFC 6901) for body fields and `{"parameter": "page_size"}` or `{"header": "If-Match"}` for others. When problems of *different* types occur together, RFC 9457 recommends returning the most relevant one rather than a "batch" of unrelated problems.

**3. Catalogue the codes.** Keep an error catalogue next to the spec (one entry per `code`: HTTP status, meaning, client action, retryable yes/no). Document in each operation which codes it can return. In OpenAPI, define a shared `Problem` schema and shared responses in `components/responses`, and reference them from every operation (the Spectral rule `eos-errors-problem-json` checks the media type).

**4. Retryable or not.** Tell clients what to do:
| Status | Client action |
|---|---|
| 400, 401, 403, 404, 409, 412, 422 | do not retry unchanged; fix the request, refresh credentials or state |
| 408, 429, 503 | retry after `Retry-After` (or backoff with jitter) |
| 500, 502, 504 | retry with backoff only if the operation is idempotent or carries an Idempotency-Key (`api/reliability`) |

**5. What never goes in an error.** Stack traces, SQL, internal hostnames, library versions, raw upstream bodies, or another tenant's data. Zalando: "MUST not expose stack traces". Log the detail server-side under the `request_id`. Authentication errors stay vague ("invalid credentials", not "user not found"; `security/authentication`). Hide existence of forbidden resources with 404 (`security/authorization`).

**6. Framework wiring (one global handler, not per-route).**
| Stack | How |
|---|---|
| FastAPI | exception handlers for `RequestValidationError`, `HTTPException` and a base `DomainError` returning `JSONResponse(media_type="application/problem+json")`; declare `responses={422: {"model": Problem}}` so the spec matches |
| Django REST Framework | custom `EXCEPTION_HANDLER` that renders problem JSON; map `ValidationError` detail dict to `errors[]` |
| Flask | `@app.errorhandler(Exception)` and `HTTPException` mapping |
| Express / Fastify / Hono | final error middleware or `setErrorHandler`; map zod issues to `errors[]` with pointers |
| Next.js route handlers | a `problem(status, code, detail)` helper returning `Response.json(body, { status, headers: { "content-type": "application/problem+json" } })`; wrap handlers so thrown errors become 500 problems without stack |
| Spring | `ProblemDetail` / `ErrorResponse` (built in since Spring 6) |
| ASP.NET Core | `AddProblemDetails()` |
| Laravel | render exceptions in `bootstrap/app.php` (`withExceptions`) to problem JSON for `api/*` |
Unknown exceptions map to 500 with a generic `title`, `code: INTERNAL`, and the `request_id`.

**7. Clients.** Generated clients should expose `status`, `code` and `errors` as typed fields. UIs show `detail` (or a localised message keyed by `code`) and map `errors[].pointer` to form fields. Mobile apps must handle unknown codes gracefully (fallback message), because new codes will appear.

## Anti-patterns
- `200 OK` with `{"error": ...}`; GraphQL is the exception, handled in `api/graphql`.
- Clients matching on `detail` or `title` text.
- A different error shape per service or per framework default (FastAPI's `{"detail": [...]}` leaking next to custom ones).
- New error codes shipped without updating the spec and catalogue.
- Returning 500 for validation errors, or 400 for server bugs.
- Echoing user input unescaped in `detail` (reflected into HTML error pages, logs).

## Checks
- `.spectral.yaml`: `eos-errors-problem-json` (4xx/5xx offer `application/problem+json`), `eos-operation-documents-4xx`.
- Schemathesis `content_type_conformance` and `response_schema_conformance` verify the running API returns the documented problem shape (`api/testing`).
- Unit test: an unhandled exception returns 500 problem JSON without a stack trace.
- Review: every new `code` appears in the catalogue and the spec.

## Sources
- RFC 9457 Problem Details for HTTP APIs: https://www.rfc-editor.org/rfc/rfc9457
- RFC 9110 HTTP Semantics (status codes): https://www.rfc-editor.org/rfc/rfc9110
- Zalando RESTful API Guidelines (problem JSON, no stack traces): https://opensource.zalando.com/restful-api-guidelines/
- Google AIP-193 Errors: https://google.aip.dev/193
- Microsoft Azure REST API Guidelines (error codes as contract): https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- Stripe API errors (example of typed error codes): https://docs.stripe.com/api/errors

## Attribution
Adapted from "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/), "AIP-193 Errors" by Google (https://google.aip.dev/193) and "Microsoft Azure REST API Guidelines" by Microsoft (https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined with RFC 9457, and eos defaults and framework notes added. Not endorsed by the original authors.
