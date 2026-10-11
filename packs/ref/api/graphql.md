---
id: api/graphql
title: GraphQL - when it fits, schema design and evolution, errors, persisted (trusted) documents, depth/complexity limits, N+1 and DataLoader, authorisation
area: api
read_when: choosing GraphQL vs REST/BFF, designing or reviewing a GraphQL schema, securing a GraphQL endpoint, fixing slow resolvers or N+1, evolving a schema without versions
verified: 2026-10-10
revisit_days: 365
sources: ["https://graphql.org/learn/security/", "https://graphql.org/learn/performance/", "https://graphql.org/learn/pagination/", "https://graphql.org/learn/serving-over-http/", "https://graphql.org/learn/schema-design/", "https://graphql.org/learn/response/", "https://github.com/graphql/dataloader", "https://relay.dev/graphql/connections.htm"]
---
# GraphQL

GraphQL lets clients ask for exactly the fields they need from a typed graph, through one endpoint. It shifts complexity to the server: arbitrary queries mean you must bound cost, batch data access and authorise every field path. Choose it for the client benefits, not because REST felt old.

## Decision guide

**1. When it fits.**
| Fits well | Prefer REST (+ OpenAPI) or a BFF |
|---|---|
| Several first-party clients (web, iOS, Android) with different screens over the same rich, connected data | Simple CRUD, few resources, one client |
| Teams iterating screens fast without new endpoints | Public/partner APIs where HTTP caching, simple tooling and per-endpoint rate limits matter |
| Aggregating several backends into one graph (gateway/federation) | File transfer, streaming, webhooks, heavy write workflows |
| Mobile bandwidth matters (no over-fetching) | Team has no capacity to run cost limits, persisted documents and resolver monitoring |
A BFF (one tailored REST/RPC endpoint per screen) solves over-fetching too, with less machinery (`architecture/api-performance`). tRPC or server actions fit a single TypeScript app with no external clients.

**2. Schema design.**
- Model the domain graph, not the database; name types as nouns (`Order`), mutations as verbs (`cancelOrder`).
- Mutations take one `input` object and return a payload type (`CancelOrderPayload { order, userErrors }`), leaving room to add fields.
- Lists are paginated connections (Relay spec: `first`/`after`, `edges`, `pageInfo { hasNextPage endCursor }`); graphql.org's security guide also recommends paginating list fields to bound response size. Cap `first` (e.g. 100).
- Global object ids (`id: ID!`, opaque) and a `node(id:)` field make client caching simple.
- Nullability: fields that may fail independently should be nullable so one failing resolver does not null out the whole parent; required arguments and inputs non-null.
- Custom scalars for `DateTime`, `Money`/`Decimal`, `URL` with validation.
- **Evolve without versions** (graphql.org's position): add fields freely, deprecate with `@deprecated(reason: "Use totalMoney")`, track usage of deprecated fields per client, remove after a published date. Run a schema diff in CI (GraphQL Inspector, Apollo/Hive schema checks) to block breaking changes, the same idea as oasdiff (`api/evolution`).

**3. Transport and errors.**
- POST for queries and mutations; GET may be accepted for queries only (enables HTTP/CDN caching, especially with persisted document ids); never run mutations over GET.
- The draft GraphQL-over-HTTP spec defines the `application/graphql-response+json` response media type; clients should accept it.
- Responses may carry partial `data` plus an `errors` array. Request errors (parse, validation) return no data. Put a stable machine code in `errors[].extensions.code`.
- Expected business failures (insufficient funds, validation) belong in the schema as typed results (`userErrors` or union result types), not only in `errors`.
- Mask internal errors in production: no stack traces or SQL in `errors[].message` (same rule as `api/errors-problem-details`).

**4. Security and demand control (graphql.org security guide).**
| Control | What it does | Default |
|---|---|---|
| **Trusted (persisted) documents** | build step registers each operation's hash; production accepts only known ids. Strongest control | **required** for APIs that only serve your own apps |
| Depth limit | rejects deeply nested queries (lower limit for nested lists) | e.g. 10-15 |
| Breadth, alias and batch limits | caps fields per level, aliases repeating an expensive field, operations per HTTP request | set explicitly |
| Cost/complexity analysis | estimated cost per field (lists multiply), reject above budget; rate-limit by cost | needed for public GraphQL |
| Pagination caps | `first <= 100` | always |
| Timeouts | per request and per resolver/data source | always |
| Introspection | may be disabled in production for first-party-only APIs, but that is obscurity, not protection | off in prod when trusted documents are on |
- **Authorisation in the business layer**, per object, called from resolvers, not only at the HTTP entry. Every path to an object (`order.customer.orders`) must hit the same check (`security/authorization`). Field-level rules for sensitive fields.
- Validate and sanitise argument values in business logic; custom scalars help.
- Rate limit by credential and by query cost, not only by request count (`api/rate-limits-auth`).
- CSRF: reject GET mutations and require a non-simple content type (`application/json`) on POST; with cookies, enforce SameSite and a CSRF token or custom header.

**5. Performance: N+1 and DataLoader.**
- Naive resolvers run one query per parent (`orders` → `customer` for each = N+1). Use DataLoader (or your server's built-in batching): it collects keys requested within one event-loop tick and calls a batch function once, e.g. `SELECT … WHERE id = ANY($1)`.
- Create loaders **per request** (cache is per request so users never see each other's data); the batch function must return values in the same order and length as the keys (return `null`/`Error` for missing ones).
- Python (Strawberry, Graphene) and JVM servers have equivalent dataloader libraries; Hot Chocolate, Apollo and others offer built-in batching.
- Trace resolver timings (OpenTelemetry) and log operation names; find slow fields before users do (`architecture/api-performance`).

## Anti-patterns
- Public GraphQL endpoint without depth, cost or pagination limits.
- Accepting arbitrary queries from first-party apps when trusted documents would do.
- Authorisation only on top-level query fields; nested paths bypass it.
- Global DataLoader instance shared across requests (data leaks between users, stale cache).
- `JSON` scalar everywhere instead of types; mutations returning `Boolean`.
- Versioned GraphQL endpoints (`/graphql/v2`) instead of additive evolution and deprecation.
- Business errors only as strings in `errors[].message`.

## Checks
- CI: schema diff against main blocks breaking changes; persisted-document manifest regenerated and committed.
- Tests: a query exceeding depth/cost limits is rejected; a nested path to another tenant's object returns null/forbidden; resolver query count stays constant as list size grows (N+1 regression test).
- Review: every new list field is a capped connection; every new type has an authorisation rule.

## Sources
- graphql.org Security: https://graphql.org/learn/security/ · Performance: https://graphql.org/learn/performance/ · Pagination: https://graphql.org/learn/pagination/
- graphql.org Serving over HTTP: https://graphql.org/learn/serving-over-http/ · Schema design: https://graphql.org/learn/schema-design/ · Response: https://graphql.org/learn/response/
- DataLoader: https://github.com/graphql/dataloader
- Relay cursor connections specification: https://relay.dev/graphql/connections.htm
