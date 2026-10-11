# Test strategy
| Layer | What | Speed | Where | Share |
|---|---|---|---|---|
| Unit | pure logic: money maths, state machines, validation | ms | `tests/unit/` | most |
| Integration | real DB/Redis via testcontainers, repositories, migrations up/down | seconds | `tests/integration/` (`-m integration`) | some |
| Contract | OpenAPI breaking-change check in CI (`eos scaffold api-contract`), consumer tests for webhooks | seconds | CI | per API |
| E2E smoke | a few critical journeys (login, pay, refund) in a browser, plus a11y | minutes | `e2e/` | few |

Rules:
- Name tests after behaviour and the acceptance criterion: `test_ac2_partial_refund_keeps_fee`.
- Each bug fix starts with a failing test that reproduces it.
- Coverage gate: CI fails under `COVERAGE_MIN` (repo variable, default 80). Money/auth modules aim for branch coverage near 100%.
- Factories (`tests/factories.py`) build valid objects by default; tests override only what they are about.
- No sleeps, no real network, no shared mutable state between tests; time and randomness are injected.
- Flaky test = bug: quarantine with an issue link within a day, never retry silently.
