---
id: architecture/api-performance
title: Data fetching and API performance (N+1, pagination, batching, BFF, GraphQL)
area: architecture
read_when: an endpoint or screen is slow, designing list endpoints or pagination, choosing REST vs GraphQL vs BFF, or fixing N+1 queries
verified: 2026-10-10
revisit_days: 365
sources: ["https://use-the-index-luke.com/no-offset", "https://google.aip.dev/158", "https://relay.dev/graphql/connections.htm", "https://graphql.org/learn/pagination/", "https://github.com/graphql/dataloader", "https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html", "https://docs.djangoproject.com/en/stable/ref/models/querysets/", "https://samnewman.io/patterns/architectural/bff/", "https://learn.microsoft.com/en-us/azure/architecture/patterns/backends-for-frontends"]
---
# Data fetching and API performance

Most slow endpoints are slow for one of four reasons: too many queries (N+1), too much data (no pagination, over-fetching), too many round trips (chatty clients), or work that should not be on the request path. Measure with a trace first: count queries and outbound calls per request.

## Decision guide

**N+1 queries.** Loading a list, then one query per item for a relation. 50 orders → 51 queries; latency grows with page size.
- ORM fixes: SQLAlchemy `selectinload()` (one extra `IN` query per relation, good default for collections) or `joinedload()` (one JOIN, good for many-to-one); Django `select_related()` (JOIN for FK/one-to-one) and `prefetch_related()` (separate query for many-to-many and reverse FK); Prisma `include`/`select`; ActiveRecord `includes`.
- Make lazy loads fail loudly: SQLAlchemy `raiseload("*")` or `lazy="raise"` on relationships turns a hidden N+1 into an error in tests.
- GraphQL resolvers: batch per request with DataLoader (or your server's equivalent). It collects keys requested in one tick and calls a batch function once; its cache is per request, not a shared cache.
- Across services: a batch endpoint (`GET /users?ids=1,2,3`, `BatchGetUsers`) instead of N calls.

**Pagination.** Every list endpoint is paginated from day one, with a max page size enforced server-side.
- **Cursor / keyset (default):** `WHERE (created_at, id) < ($last_created_at, $last_id) ORDER BY created_at DESC, id DESC LIMIT 50`, backed by an index on `(created_at DESC, id DESC)`. Cost stays flat however deep you go, and inserts don't shift pages. Use The Index, Luke calls this the seek method.
- **Offset:** `OFFSET 100000` reads and throws away 100,000 rows; pages shift when rows are inserted. Acceptable only for small admin tables or when users truly need "jump to page 7".
- Make the cursor opaque (base64 of the sort key, or a signed token) so you can change the implementation. Google AIP-158: `page_size` + `page_token` in, `next_page_token` out, empty token = last page; tokens are opaque. GraphQL: the Relay connection spec (`first`/`after`, `edges`, `pageInfo { hasNextPage endCursor }`).
- Total counts are expensive on big tables: make them optional, approximate, or cached.

**Payload size.** Return the fields the client needs: sparse fieldsets (`?fields=id,name`), separate summary vs detail representations, compression (gzip/brotli), and no unbounded nested arrays. Images: sized variants via a CDN, not originals.

**Round trips.** Mobile networks make each request expensive in latency.
- Compose server-side for a screen: a **Backend for Frontend** (one per client type, owned by the client team, per Sam Newman) aggregates calls, shapes payloads and holds client-specific logic. Costs: one more deployable per client; risk of duplicated logic across BFFs; keep domain rules in the services.
- **GraphQL** gives clients flexible selection and a typed schema, one round trip per screen. Costs: N+1 risk in resolvers (need batching), harder HTTP caching (POSTs; use persisted queries + GET for caching), query cost and depth limits needed against abusive queries, per-field authorisation. Good when many clients with different needs share a graph; overkill for one web app talking to its own backend.
- **REST + a few composite endpoints** is enough for most single-client products. Add HTTP caching (ETag, `Cache-Control`) for GETs.

| Situation | Pick |
|---|---|
| One web app, one team | REST/RPC endpoints shaped for the screens (the server is effectively your BFF) |
| Web + mobile with different needs, separate teams | BFF per client |
| Many clients, many teams, shared domain graph | GraphQL (with DataLoader, persisted queries, cost limits) |
| Public third-party API | REST with stable resources + cursor pagination, versioned |

**Move work off the request path.** Emails, PDFs, image processing, webhooks out, analytics: enqueue and return `202 Accepted` with a status URL, or do it after commit through the outbox (`architecture/event-driven`).

**Parallelise independent calls** on the server (`asyncio.gather`, `Promise.all`) with an overall deadline; sequential awaits of independent calls are a common hidden cost.

## Examples

- **Orders list, 1.8 s at 100 items:** trace shows 201 queries (customer + items per order). `selectinload(Order.items)`, `joinedload(Order.customer)` → 3 queries; add `raiseload("*")` to the query in tests to keep it fixed.
- **Infinite feed:** keyset cursor on `(posted_at, id)`; client sends `after=<opaque>`; server caps `limit` at 100.
- **Mobile home screen with 6 calls:** BFF endpoint `GET /mobile/home` fans out in parallel with a 300 ms budget, drops non-critical widgets on timeout, returns one compact payload.

## Anti-patterns

- Unpaginated list endpoints ("there are only 20 rows today").
- `OFFSET` pagination over large or fast-changing tables; exposing raw DB ids/offsets as the cursor contract.
- Caching to hide N+1 (see `architecture/caching`).
- A GraphQL server without batching, depth/cost limits or per-field auth.
- One "god" BFF shared by all clients (it becomes a monolith in front of your monolith).
- Sequential awaits for independent downstream calls.

## Checks

- Query-count assertions on hot endpoints (Django `assertNumQueries`, SQLAlchemy `raiseload` in tests, a query counter middleware in dev that logs > N queries per request).
- API lint: list operations declare pagination params and a max page size (Spectral/oasdiff rule or a contract test).
- Performance budget: p95 latency and payload size per key endpoint in CI smoke tests or synthetic checks.

## Sources

- Use The Index, Luke, No offset (seek method): https://use-the-index-luke.com/no-offset
- Google AIP-158, Pagination: https://google.aip.dev/158
- Relay, GraphQL Cursor Connections Specification: https://relay.dev/graphql/connections.htm
- GraphQL, Pagination: https://graphql.org/learn/pagination/
- DataLoader: https://github.com/graphql/dataloader
- SQLAlchemy 2.0, Relationship loading techniques: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- Django, QuerySet API (select_related, prefetch_related): https://docs.djangoproject.com/en/stable/ref/models/querysets/
- Sam Newman, Backends for Frontends: https://samnewman.io/patterns/architectural/bff/
- Azure Architecture Center, Backends for Frontends pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/backends-for-frontends
