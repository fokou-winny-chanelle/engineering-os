---
id: data/keys-money-time
title: Keys, money and time (identity vs UUIDv7/ULID, numeric vs minor units, ledgers, timestamptz)
area: data
read_when: choosing primary keys or public ids, storing amounts, designing a ledger or balance, or storing dates and times
verified: 2026-10-10
revisit_days: 365
sources: ["https://www.rfc-editor.org/rfc/rfc9562", "https://www.postgresql.org/docs/current/functions-uuid.html", "https://github.com/ulid/spec", "https://wiki.postgresql.org/wiki/Don't_Do_This", "https://www.postgresql.org/docs/current/datatype-numeric.html", "https://www.postgresql.org/docs/current/datatype-money.html", "https://www.postgresql.org/docs/current/datatype-datetime.html", "https://docs.stripe.com/currencies"]
---
# Keys, money and time

Three choices that are expensive to change later. Decide them once per project and write the decision in an ADR.

## Decision guide

**1. Primary keys.**
| Option | Pick when | Costs |
|---|---|---|
| `bigint GENERATED ALWAYS AS IDENTITY` | Default for internal keys in one database | Guessable and leaks volume if exposed; needs the DB to allocate |
| UUIDv7 (`uuid`, 16 bytes) | Ids created by clients or several services, merged datasets, ids safe to expose | 16 bytes in every FK and index; embeds creation time (ms) |
| ULID (26-char text, or stored as `uuid`) | Existing ULID ecosystem; human-friendly sortable strings | Store as `uuid` (16 bytes) not `text` (26+ bytes) |
| UUIDv4 | Only when no time leak is acceptable at all | RFC 9562: non-time-ordered UUIDs have "poor database-index locality" (inserts land at random B-tree pages) |
- Use identity, not `serial` (wiki: serial has "weird behaviors" for schema, dependency and permission management; squawk's `prefer-identity` flags it). Use `bigint`, not `int` (squawk `prefer-bigint-over-int`): running out of 2,147,483,647 is a painful migration.
- UUIDv7 = 48-bit Unix millisecond timestamp in the most significant bits + 74 random bits (RFC 9562 §5.7), so new keys sort roughly by time and stay index-friendly. PostgreSQL 18 ships `uuidv7()` (with an optional shift interval); on 17 or earlier, generate in the app.
- ULID: 128-bit, 26-character Crockford base32, lexicographically sortable, with a monotonic mode inside the same millisecond.
- A common split: `bigint` identity as the internal PK and FK, plus a unique `public_id uuid` (v7) used in URLs and APIs. Never expose sequential ids for objects whose count or existence is private, and never rely on unguessable ids for authorization (`security/authorization`).
- Natural keys (email, SKU) change; keep them as `UNIQUE` columns, not as the PK.

**2. Money.**
- **Never** binary floating point (`real`, `double precision`, JS `number` for arithmetic, Python `float`): the docs call them inexact and say to use `numeric` "if you require exact storage and calculations (such as for monetary amounts)".
- **Avoid** Postgres `money`: its fractional precision comes from the `lc_monetary` setting, it stores no currency, and changing the locale makes existing values wrong (wiki "Don't use money").
- **Choose one** and use it everywhere: `numeric(precision, scale)` (exact decimal; readable; slower than integers) or `bigint` minor units (`amount_minor`, fast and exact; you must know each currency's exponent). Always store the ISO 4217 currency next to the amount.
- Minor units differ by currency and provider: Stripe takes amounts in the smallest unit and lists JPY, XAF and XOF as zero-decimal, with ISK as a special case kept two-decimal for compatibility. Keep a currency table with its exponent instead of assuming 2.
- Round once, at a defined step (invoice line, tax total), with a named rounding mode; allocate remainders explicitly when splitting (largest remainder), and test that parts sum to the whole.
- In code: Python `decimal.Decimal` built from strings (`Decimal("0.10")`, never `Decimal(0.1)`), JS integer minor units or a decimal library; serialise amounts as strings or integers in JSON.

**3. Ledgers** (balances, wallets, credits, mobile money). Double-entry, append-only:
```sql
CREATE TABLE ledger_accounts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,                       -- 'cash', 'customer:42:wallet'
  currency char(3) NOT NULL,
  normal_side text NOT NULL CHECK (normal_side IN ('debit', 'credit'))
);
CREATE TABLE ledger_transactions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE,             -- provider event id or request key
  description text NOT NULL,
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ledger_entries (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  transaction_id bigint NOT NULL REFERENCES ledger_transactions (id),
  account_id bigint NOT NULL REFERENCES ledger_accounts (id),
  amount_minor bigint NOT NULL CHECK (amount_minor <> 0),   -- + debit, - credit
  currency char(3) NOT NULL
);
CREATE INDEX ON ledger_entries (transaction_id);
CREATE INDEX ON ledger_entries (account_id, id);
```
- Invariant: entries of one transaction sum to zero per currency. Enforce in the single function that writes transactions (and test it); a deferred constraint trigger can enforce it in the database.
- Corrections are new reversing transactions, never `UPDATE`/`DELETE` (revoke those privileges from the app role on ledger tables).
- Balances: compute from entries; when that gets slow, keep a `balances` row updated in the same transaction with `UPDATE … SET balance = balance + $1 WHERE account_id = $2 AND balance + $1 >= 0` (atomic, no read-modify-write race), and reconcile it against the sum of entries in a scheduled job.
- External money (PSP, mobile money) also needs idempotency keys and reconciliation against provider reports (`security/payments`, `architecture/data-consistency`).
- Money and ledger code needs human review before merge.

**4. Time.**
- Instants (`created_at`, `paid_at`): `timestamptz`. Input with an explicit zone is converted to UTC for storage; output is shown in the session `TimeZone`. Do not store UTC in `timestamp without time zone` (wiki: the database cannot know it is UTC, and zone arithmetic gets convoluted). squawk `prefer-timestamptz` and `schema_lint.sql` flag naive timestamps.
- Calendar facts (birthday, invoice due date, business day): `date`. Future local events (a meeting at 09:00 in Douala next year): store local time + IANA zone name (`Africa/Douala`), because zone rules can change before the date.
- Ranges: `tstzrange`/`daterange` with half-open bounds `[start, end)`; avoid `BETWEEN` on timestamps (wiki), use `>= start AND < end`.
- Do not use `timestamp(0)`/`timestamptz(0)` (rounds, can produce times in the future) or `timetz` (wiki).
- Durations: `interval`, or integer seconds/milliseconds when crossing systems.

## Anti-patterns
- `float`/`double` money columns; `parseFloat(amount)`; summing floats then rounding for display.
- Amount without currency; assuming every currency has 2 decimals.
- Mutable balance column with no ledger behind it; `UPDATE balance = <value read earlier>`.
- Random UUIDv4 primary keys on large write-heavy tables without measuring index impact; `text` columns holding UUIDs.
- Local server time in `timestamp` columns; time zone offsets (`+01:00`) stored instead of zone names for future events.

## Checks
- [ ] ADR records the key strategy (internal vs public id) and the money representation.
- [ ] `eos scaffold db-safety`: semgrep money rules (`eos-money-float-*`) pass and `schema_lint.sql` reports no money-as-float column on the migrated schema.
- [ ] Ledger tests: transaction entries sum to zero; duplicate idempotency key → one transaction; app role cannot UPDATE/DELETE ledger rows; reconciliation job exists.
- [ ] squawk passes `prefer-identity`, `prefer-bigint-over-int`, `prefer-timestamptz` (or each exception has a `-- squawk-ignore` with a reason).

## Sources
- https://www.rfc-editor.org/rfc/rfc9562 (§5.7 UUIDv7 layout; §2.1 index locality of UUIDv4)
- https://www.postgresql.org/docs/current/functions-uuid.html (`uuidv7()`)
- https://github.com/ulid/spec
- https://wiki.postgresql.org/wiki/Don't_Do_This (money, serial, timestamp without time zone, BETWEEN, timestamp(0), timetz)
- https://www.postgresql.org/docs/current/datatype-numeric.html (numeric recommended for money; float inexact)
- https://www.postgresql.org/docs/current/datatype-money.html (precision from lc_monetary)
- https://www.postgresql.org/docs/current/datatype-datetime.html (timestamptz input converted to UTC)
- https://docs.stripe.com/currencies (smallest currency unit; zero-decimal list incl. XAF, XOF, JPY; ISK)
