---
id: testing/test-data
title: Test data management - factories, builders, object mothers, fixtures, seeds, synthetic data and anonymised production data
area: testing
read_when: creating test data, choosing factories vs fixture files, seeding dev/staging, generating load-test data, or someone wants to copy production data into tests or staging
verified: 2026-10-10
revisit_days: 180
sources: ["https://factoryboy.readthedocs.io/en/stable/", "https://martinfowler.com/bliki/ObjectMother.html", "https://fakerjs.dev/guide/usage", "https://postgresql-anonymizer.readthedocs.io/en/stable/", "https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/", "https://hypothesis.readthedocs.io/en/latest/reference/api.html"]
---
# Test data management

Good test data is minimal (only what the test needs), explicit (visible in the test), independent (no test relies on another's leftovers) and safe (no real people's data). Database specifics (real engine, transactions per test, seed scripts) are in `data/orm-sql-testing`; privacy law in `security/privacy`.

## Decision guide

**1. Pick the tool for the job.**
| Tool | Use for | Watch out |
|---|---|---|
| Inline literals | the one or two values a test is about | none: prefer them |
| Factory (factory_boy, a small TS `makeUser({...})`) | valid objects with sensible defaults, override what matters | defaults that hide the value the test depends on |
| Builder (`anOrder().withItem(...).paid().build()`) | complex objects with many valid states | over-engineering for simple types |
| Object Mother (`Customers.vipWithExpiredCard()`) | named, shared personas the team talks about | grows into a god-object; tests coupled to its changes |
| Fixture files (JSON/SQL) | reference data (currencies, countries), golden files for parsers | big shared files every test depends on |
| Generators (Faker, Hypothesis strategies) | varied realistic values, property tests | randomness without a seed |

**2. Factories done well.** Defaults produce a valid object; each test overrides the field it asserts on, so the reason is visible. factory_boy offers `Sequence` for unique values (emails), `LazyAttribute` for values derived from other fields and `SubFactory` for related objects. Keep one factory per aggregate, next to the tests. Create through the same code paths the app uses (or the API) when invariants matter.

**3. Deterministic randomness.** Seed generators so a failure reproduces: `faker.seed(123)` in Faker.js (setting the seed again resets the sequence), Hypothesis's printed reproduction. Log the seed when you pick one at random.

**4. Isolation.** Each test creates its own data and cleans up by transaction rollback or a fresh schema/container (`testing/integration`). Use unique keys (sequences, UUIDs) so parallel workers do not collide. E2E tests seed through an API or fixture, one account per worker if tests mutate state (`testing/e2e-playwright`).

**5. Dev, staging and load-test data.** Use an idempotent seed script (code, reviewed) for dev; generate production-*shaped* synthetic data at production *volume* for performance work (`testing/performance-k6`). Keep large generated files out of git; commit the generator.

**6. Production data: default no.** Copying production into tests, dev or staging copies personal data into less protected places.
- Prefer synthetic data. If production shape really is needed (a migration rehearsal, a bug that only real data shows), mask it first, inside a controlled environment, with rules the developers own: PostgreSQL Anonymizer declares masking rules in the schema and offers anonymous dumps, static masking, dynamic masking and anonymised replicas.
- Pseudonymised data (names swapped for ids or hashes) is still personal data for anyone who holds the extra information to re-identify it (ICO). Dropping names but keeping birth date, postcode and phone is not anonymisation (`security/privacy`).
- Never put production data, real card numbers or real credentials in fixtures, screenshots, bug reports or LLM prompts. Use the payment provider's test cards (`security/payments`).
- A human approves any use of production-derived data, with a written purpose and deletion date.

## Anti-patterns
- A 2,000-line `fixtures.json` that every test loads; tests that break when someone adds a row.
- Tests depending on data created by an earlier test or on auto-increment ids.
- Unseeded random data, so failures cannot be reproduced.
- "Anonymised" production dumps on laptops, in CI caches or shared drives.
- Factories with so many defaults that the test's real precondition is invisible.

## Checks
- Review: each test shows the data it depends on; no shared mutable fixtures.
- `data/orm-sql-testing` checklist: tests run on the real engine; no production data in fixtures.
- Secret scanning (gitleaks in the commit hooks) and review catch real tokens or keys pasted into fixtures; personal data needs human review.

## Sources
- factory_boy: https://factoryboy.readthedocs.io/en/stable/
- Martin Fowler, Object Mother: https://martinfowler.com/bliki/ObjectMother.html
- Faker.js usage (seeding): https://fakerjs.dev/guide/usage
- PostgreSQL Anonymizer: https://postgresql-anonymizer.readthedocs.io/en/stable/
- ICO, Pseudonymisation: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/
- Hypothesis reproduction and seeds: https://hypothesis.readthedocs.io/en/latest/reference/api.html
