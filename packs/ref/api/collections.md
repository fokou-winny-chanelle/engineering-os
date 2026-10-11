---
id: api/collections
title: Collections - cursor pagination, filtering, sorting, sparse fields and search endpoints
area: api
read_when: adding a list endpoint, choosing pagination, adding filter or sort parameters, exposing counts, designing search or export endpoints
verified: 2026-10-10
revisit_days: 365
sources: ["https://google.aip.dev/158", "https://google.aip.dev/132", "https://google.aip.dev/160", "https://opensource.zalando.com/restful-api-guidelines/", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md", "https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api", "https://www.rfc-editor.org/rfc/rfc8288", "https://graphql.org/learn/pagination/"]
adapted_from: ["https://google.aip.dev/158", "https://google.aip.dev/132", "https://opensource.zalando.com/restful-api-guidelines/", "https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md"]
---
# Collections: pagination, filtering, sorting

Every list endpoint is paginated **from the first release**. Google AIP-158 is blunt: adding pagination later is a backwards-incompatible change, because existing clients would silently receive only the first page. The response is an object (not a bare array) so paging fields fit next to the items.

## Decision guide

**1. Pagination style.**
| Style | How | Use when | Costs |
|---|---|---|---|
| **Cursor / keyset (eos default)** | opaque `next_cursor` encodes the last row's sort key + id; server runs `WHERE (created_at, id) < (:t, :id) ORDER BY created_at DESC, id DESC LIMIT :n+1` | feeds, large or fast-changing tables, public APIs | no "jump to page 37"; total count separate |
| Offset / page number | `?page=3&page_size=50` → `OFFSET 100` | small admin tables, stable data, UIs that need page numbers | rows skipped or repeated when data changes between calls; deep offsets get slower (database still reads the skipped rows) |
| Link header | `Link: <…?cursor=abc>; rel="next"` (RFC 8288; GitHub does this) | same cursor, carried in a header | clients must parse headers; also put it in the body |

SQL side (index on the sort key + id, row-value comparison): `data/postgres-queries`.

**2. Request and response contract (eos default).**
```
GET /orders?page_size=50&cursor=eyJ0IjoiMjAyNi0xMC0xMFQxNzowMFoiLCJpZCI6Im9yZF85In0&status=OPEN&order_by=-created_at

200 { "items": [ ... ], "next_cursor": "eyJ0Ijo...", "has_more": true }
```
- `page_size`: optional, documented default (e.g. 20) and maximum (e.g. 100). Values above the max are reduced to the max, not rejected; negative values → 400 (AIP-158, where an unset page size means "use the default"). The spec declares `maximum` (Spectral `eos-page-size-bounded`).
- The server may return **fewer** items than asked, even zero with a cursor, so clients loop until `next_cursor` is null, never until a short page.
- Cursors are **opaque** (base64url of a small JSON or a signed token). Clients must not build or parse them, so you can change the encoding. Sign or encrypt them if they contain anything a client should not tamper with. Bind them to the filter and sort: reject a cursor reused with different filters (400). A cursor grants nothing: authorise every page request as if it had none (AIP-158).
- Cursors may expire; document how long (AIP-158 suggests about three days as a rule of thumb). An expired cursor gives a clear 400 problem, not an empty page.
- Azure style is equivalent: `value` + absolute `nextLink` URL. Pick one style per API.

**3. Totals.** Avoid a total count by default. Zalando explains why: counting usually needs a full scan, gets slower as data grows, and once clients rely on it you cannot remove it. If the UI needs it, offer an opt-in (`?include_total=true`) or an estimate, and document that it may be approximate (AIP-158 allows `total_size` to be an estimate).

**4. Filtering.**
- Simple equality filters as typed query params: `?status=OPEN&customer_id=cus_1`. Repeat for "any of": `?status=OPEN&status=PAID` (declare `style: form, explode: true`).
- Ranges with clear suffixes: `created_after`, `created_before` (half-open: `>=` after, `<` before; RFC 3339 timestamps).
- A filter *language* (AIP-160: `filter="status = OPEN AND total > 100"`) only when clients really need arbitrary combinations. It needs a real parser, an allow-list of fields, and limits on complexity. Never pass it to SQL as text (`security/input-injection`).
- Only filter on indexed fields, or set a timeout and a max scan; an unindexed filter on a big table is a denial-of-service lever.
- Authorisation filters are applied **server-side first**; client filters only narrow further (`security/authorization`, BOLA).

**5. Sorting.** One param, allow-listed fields: `order_by=-created_at,name` (leading `-` for descending) or AIP-132 style `order_by="created_at desc"`. Always append a unique tie-breaker (id) internally so pages are stable. Changing the sort invalidates the cursor.

**6. Sparse fields and expansion.** `?fields=id,status,total` cuts payloads for mobile; `?expand=customer` inlines a related resource to avoid N+1 round trips (`architecture/api-performance`). Both must be allow-listed and typed in the spec, and authorisation applies to expanded objects too.

**7. Search, export, sync.**
- Complex search with a big body: `POST /orders:search` (custom method, read-only, idempotent in effect). Document that it changes nothing, so clients may retry.
- Bulk export of millions of rows: an asynchronous export job that produces a file (`api/reliability`, long-running operations), not deep pagination.
- Mobile/offline sync: `?updated_after=<cursor>` change feeds ordered by a monotonic change sequence, including tombstones for deletes.

## Anti-patterns
- Unpaginated list endpoints ("there will never be many").
- Bare JSON arrays as list responses.
- Unbounded `page_size` (`?limit=1000000`).
- Offset pagination on large, frequently written tables, or `COUNT(*)` on every page.
- Cursors that are raw database ids or offsets clients can edit; cursors that ignore the filter they were made with.
- Sort or filter on any column the client names (injection, unindexed scans, leaking hidden fields).
- Stopping the client loop on a short page instead of a missing cursor.

## Checks
- `.spectral.yaml`: `eos-list-response-is-object`, `eos-collection-paginated` (a GET whose body has an `items`/`data`/`results`/`value` array needs a page size and a cursor param), `eos-page-size-bounded`, `eos-no-offset-pagination` (info).
- Test: insert rows between page requests and assert no duplicates or gaps (cursor), and a cursor reused with different filters is rejected.
- `EXPLAIN` the list query with the largest realistic tenant (`data/postgres-queries`).

## Sources
- Google AIP-158 Pagination: https://google.aip.dev/158 · AIP-132 List methods (order_by): https://google.aip.dev/132 · AIP-160 Filtering: https://google.aip.dev/160
- Zalando RESTful API Guidelines (cursors, avoid total counts): https://opensource.zalando.com/restful-api-guidelines/
- Microsoft Azure REST API Guidelines (`value` + `nextLink`): https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- GitHub REST pagination (Link header): https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
- RFC 8288 Web Linking: https://www.rfc-editor.org/rfc/rfc8288
- GraphQL pagination (connections): https://graphql.org/learn/pagination/

## Attribution
Adapted from "AIP-158 Pagination", "AIP-132 Standard methods: List" by Google (https://google.aip.dev/158, https://google.aip.dev/132), "RESTful API Guidelines" by Zalando (https://opensource.zalando.com/restful-api-guidelines/) and "Microsoft Azure REST API Guidelines" by Microsoft (https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: condensed, reworded, combined, and eos defaults added. Not endorsed by the original authors.
