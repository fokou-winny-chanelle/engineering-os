---
id: architecture/data-consistency
title: Data architecture and consistency
area: architecture
read_when: choosing data stores, naming the consistency level of a flow, handling money or counters, retries that write, or read models (CQRS)
verified: 2026-10-10
revisit_days: 365
sources: ["https://jepsen.io/consistency", "https://www.postgresql.org/docs/current/transaction-iso.html", "https://docs.stripe.com/api/idempotent_requests", "https://brandur.org/idempotency-keys", "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", "https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs", "https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing", "https://dataintensive.net/"]
---
# Data architecture and consistency

Most production bugs that lose money are consistency bugs: a double charge on retry, a lost update between two requests, a read from a lagging replica. Decide the consistency each flow needs, then pick the cheapest mechanism that gives it.

## Decision guide

**Stores.** Default to one relational database (PostgreSQL) as the system of record. Add a specialised store only for a workload the primary measurably can't serve, and name it in an ADR:

| Workload | Add | Keep in mind |
|---|---|---|
| Full-text / faceted search | search engine (OpenSearch/Elasticsearch) or Postgres FTS first | derived data: rebuildable from the primary |
| Hot keys, sessions, rate limits | Redis/Valkey | a cache or ephemeral store, not the record |
| Files, media | object storage + CDN | store keys in the DB, never blobs in rows |
| Analytics over months of events | warehouse / columnar store via CDC or batch | never run reports on the OLTP primary |
| Very high write, simple key access | wide-column / key-value store | you give up joins and ad-hoc queries |

Every extra store is another backup, failover and consistency story. "Derived" stores must be rebuildable from the system of record.

**Name the consistency per flow** (write it in the overview's flow list):
- **Strong (linearizable/serializable)**: balances, stock that must not oversell, unique usernames, permissions changes. Jepsen's map of consistency models is the reference for what each name actually guarantees.
- **Read-your-writes**: a user sees their own edit immediately (route that user's reads to the primary for a few seconds after a write, or read from the primary for their own data).
- **Eventual**: feeds, counters shown to others, search indexes, analytics. State the expected lag ("search reflects edits within 1 min").

**Isolation levels (PostgreSQL).** Default READ COMMITTED allows lost updates in read-modify-write code. Pick one fix per hot spot:
- atomic update: `UPDATE accounts SET balance = balance - 10 WHERE id = $1 AND balance >= 10` and check the row count;
- row lock: `SELECT … FOR UPDATE` inside the transaction;
- optimistic concurrency: a `version` column, `UPDATE … WHERE id=$1 AND version=$2`, retry or report a conflict on 0 rows (also the right answer for "two people edited the form");
- SERIALIZABLE for complex invariants, with a retry loop on serialization failures (SQLSTATE 40001); the docs say applications must be ready to retry.
- Unique constraints and `INSERT … ON CONFLICT` beat "check then insert" every time.

**Idempotency for every write a client may retry.** Networks time out after the server committed; the client retries; without a key you do it twice.
- The client sends a unique key (UUIDv4) per logical operation (Stripe: `Idempotency-Key` header, up to 255 characters; keys can be pruned after at least 24 hours; a reused key with different parameters is an error).
- The server stores key → request fingerprint → response in the same transaction as the effect, returns the stored response on repeat, and rejects a concurrent duplicate while the first is in flight (Brandur's Postgres design uses recovery points for multi-step requests).
- Amazon's guidance: a caller-provided client request identifier in the API contract is the preferred way to make retries safe.

**Money and other ledgers.** Integers in minor units (or `numeric`), never floats. Append-only entries; corrections are new reversing entries. Double-entry (every movement debits one account and credits another, sum = 0) when you hold balances. Reconcile with the provider daily.

**CQRS and read models.** Separate the write model from query-optimised read models when reads need shapes the write model can't serve cheaply (dashboards, search, cross-module views). The read side is eventually consistent; the UI must tolerate lag. Don't apply CQRS to the whole system, only to the parts that need it.

**Event sourcing** stores the events as the source of truth and derives state. Worth it when the history itself is the product (ledgers, audit-heavy domains) or you need temporal queries. Costs: event schema versioning forever, projections to rebuild, harder ad-hoc queries, GDPR erasure needs a design (crypto-shredding or separate PII store). Not a default.

## Examples

- **Wallet top-up:** request with idempotency key → one transaction inserts ledger entries (+wallet, −provider-clearing), the idempotency record and an outbox row → provider callback matched by reference → daily reconciliation job flags mismatches for a human.
- **Seat booking:** `UNIQUE(event_id, seat_no)` on `bookings`; the losing concurrent insert gets a constraint error mapped to "seat just taken".
- **Profile edit:** `version` column; the second saver gets HTTP 409 with the current data to merge.

## Anti-patterns

- Floats for money; updating balances in place without a ledger.
- "Check, then insert" for uniqueness; read-modify-write at READ COMMITTED without a lock or version.
- Treating the cache or search index as the record.
- Retries on writes without idempotency keys (client, queue consumer or job runner).
- Reading from a replica right after writing and showing the user stale data.
- Event sourcing or CQRS everywhere because one flow needed it.

## Checks

- Migration lint (squawk) and a review rule: new uniqueness rules are DB constraints, not app code.
- A concurrency test per money or stock flow: run the same request twice in parallel and with the same idempotency key; assert one effect.
- Grep in review for `float`/`double` money fields and for `UPDATE … SET balance =` without a guard.

## Sources

- Jepsen, Consistency models: https://jepsen.io/consistency
- PostgreSQL, Transaction isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Stripe API, Idempotent requests: https://docs.stripe.com/api/idempotent_requests
- Brandur Leach, Implementing Stripe-like idempotency keys in Postgres: https://brandur.org/idempotency-keys
- Amazon Builders' Library, Making retries safe with idempotent APIs: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
- Azure Architecture Center, CQRS: https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs
- Azure Architecture Center, Event sourcing: https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- Martin Kleppmann, Designing Data-Intensive Applications: https://dataintensive.net/
