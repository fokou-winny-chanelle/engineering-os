---
id: testing/integration
title: Integration tests with real dependencies - Testcontainers, ephemeral databases, fakes for third parties, contract tests
area: testing
read_when: testing code that talks to a database, queue, cache or another service; replacing mocks of your own DB; setting up CI services; deciding between contract tests and end-to-end tests
verified: 2026-10-10
revisit_days: 365
sources: ["https://testcontainers.com/", "https://testcontainers-python.readthedocs.io/en/latest/", "https://node.testcontainers.org/", "https://node.testcontainers.org/modules/postgresql/", "https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md", "https://engineering.atspotify.com/2018/01/testing-of-microservices", "https://abseil.io/resources/swe-book/html/ch14.html", "https://docs.pact.io/"]
---
# Integration tests with real dependencies

An integration test runs your code against the real thing it depends on (the same database engine and version as production, the real broker) and nothing else. It catches what mocks hide: SQL errors, constraints, transactions, serialisation, migrations, time zones.

## Decision guide

**1. What to run for real, what to fake.**
| Dependency | In integration tests |
|---|---|
| Your database (Postgres, MySQL), cache (Redis), broker (RabbitMQ, Kafka), object store (MinIO for S3) | **real**, in a container, same major version as production |
| Another service your team owns | its contract (OpenAPI/Pact) plus a fake or stub server; real only in a few E2E tests |
| Third-party APIs (payments, email, SMS, maps) | a fake or recorded responses at the HTTP boundary; their sandbox in a small scheduled contract check |
| Clock, randomness, IDs | injected and fixed |

**2. Testcontainers** (MIT): throwaway, lightweight instances of anything that runs in Docker, started from test code.
- Python: `with PostgresContainer("postgres:18") as pg: url = pg.get_connection_url()` in a session-scoped fixture (`eos scaffold tests-python` does this and skips when Docker is missing).
- Node (`@testcontainers/postgresql`): `await new PostgreSqlContainer("postgres:18").start()` in a global setup; pass the URL through an env var.
- Start one container per test session (seconds), not per test; isolate tests inside it (below).
- Pin the image tag to production's major version; a newer engine hides incompatibilities.

**3. Isolation inside a shared database** (fastest first; details in `data/orm-sql-testing`).
- Wrap each test in a transaction and roll back (fast; not for code that commits itself or uses several connections).
- Truncate the touched tables after each test (simple, works with commits).
- Template database: migrate once, `CREATE DATABASE test_n TEMPLATE app_template` per worker for parallel runs.
- Unique data per test (random tenant/user ids) so parallel tests never collide.

**4. Migrations are code.** Run every migration from empty in CI, run the test suite on the migrated schema, and test the data migrations with representative rows (`data/migrations`).

**5. CI services.** Testcontainers works on GitHub-hosted Ubuntu runners (the image ships Docker). The alternative is a `services:` container in the workflow; either way, never point tests at a shared staging database.

**6. Contract tests vs end-to-end.** Between services you own, consumer-driven contracts (Pact) or spec conformance (Schemathesis against the OpenAPI document) give most of the confidence of E2E at a fraction of the cost and flakiness. Spotify calls tests whose result depends on another system being correct *integrated tests* and aims for none. API-level details, Pact fit and the must-have API cases: `api/testing`.

**7. Hermetic larger tests** (SWE at Google ch. 14): the system under test plus all dependencies started fresh for the test, no shared environments; seed data from code, not from a dump of production (`testing/test-data`).

## Anti-patterns
- Mocking your own repository or ORM and calling it an integration test.
- SQLite in tests, Postgres in production (different SQL, locking and types).
- One container per test function; `sleep` waiting for a port instead of the library's wait strategies.
- Tests that depend on data another test created.
- Running integration tests against shared staging or production.

## Checks
- `eos scaffold tests-python`: Postgres fixture via Testcontainers, integration marker, factories.
- `eos scaffold compose`: same services locally with health checks.
- CI: integration tests on every PR; migrations up from empty; API spec conformance (`eos scaffold api-contract`).
- Review: a new query, constraint or transaction comes with a test against the real database.

## Sources
- Testcontainers: https://testcontainers.com/ · Python: https://testcontainers-python.readthedocs.io/en/latest/ · Node: https://node.testcontainers.org/ · Node PostgreSQL module: https://node.testcontainers.org/modules/postgresql/
- GitHub Ubuntu 24.04 runner image contents (Docker): https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md
- Spotify Engineering, Testing of Microservices: https://engineering.atspotify.com/2018/01/testing-of-microservices
- Software Engineering at Google, ch. 14 Larger Testing (CC BY-NC-ND, linked only): https://abseil.io/resources/swe-book/html/ch14.html
- Pact documentation: https://docs.pact.io/
