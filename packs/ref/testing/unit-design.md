---
id: testing/unit-design
title: Unit test design - behaviour not implementation, test doubles taxonomy, avoiding over-mocking, determinism
area: testing
read_when: writing or reviewing unit tests, deciding whether to mock something, tests that break on every refactor, tests that pass while the code is wrong
verified: 2026-10-10
revisit_days: 365
sources: ["https://abseil.io/resources/swe-book/html/ch12.html", "https://abseil.io/resources/swe-book/html/ch13.html", "https://martinfowler.com/bliki/TestDouble.html", "https://martinfowler.com/articles/mocksArentStubs.html", "https://kentcdodds.com/blog/testing-implementation-details", "https://martinfowler.com/articles/nonDeterminism.html"]
---
# Unit test design

A good unit test fails when behaviour breaks and only then. Tests that break on refactors teach people to ignore failures; tests that cannot fail prove nothing.

## Decision guide

**1. Test behaviour through the public API** (SWE at Google ch. 12).
- Call the code the way its users do; assert on results and observable state, not on which private functions ran.
- One test per behaviour, not one per method: `test_refund_over_balance_is_rejected`, not `test_refund`.
- Arrange / act / assert, with the setup a reader needs visible in the test ("DAMP, not DRY"): helpers may build objects, but the values that matter appear in the test.
- Name tests after the rule or acceptance criterion so a failure reads like a bug report.
- For UI: query what the user sees (role, label, text), never component state or CSS classes (Kent C. Dodds, Testing Library).

**2. Test doubles taxonomy** (Meszaros, via Fowler).
| Double | What it is | Use for |
|---|---|---|
| Dummy | passed but never used | filling a required argument |
| Stub | returns canned answers | forcing a branch: "payment gateway declines" |
| Spy | a stub that records calls | checking a side effect you cannot observe otherwise |
| Mock | pre-programmed with expected calls, fails if they do not happen | interaction is the behaviour (an email must be sent once) |
| Fake | a working lightweight implementation (in-memory repository, fake clock) | most replacements of slow or external dependencies |

**3. Order of preference** (SWE at Google ch. 13): real implementation if fast and deterministic → a fake, ideally owned and tested by the team that owns the real thing (high *fidelity*) → a stub → a mock. Prefer **state testing** (what the system ended up with) over **interaction testing** (which calls it made); use interaction tests only for state-changing calls you cannot observe, such as sending a message.

**4. Mock only what you do not own or cannot run.** Good: payment provider, email/SMS, clock, randomness, other teams' services. Bad: your own repository, your own domain objects, the ORM, value objects. For your database use a real one in a container (`testing/integration`).

**5. Determinism.** Inject the clock and freeze it (time zones and DST included); seed random generators and print the seed; no real network; no sleeps (poll for a condition with a timeout, Fowler); each test creates its own data and cleans up; tests pass in any order and in parallel.

**6. Assertions.** Assert the specific outcome (amount, status, error type and message key), not "no exception". Compare floats with tolerance (`pytest.approx`) and money as integers or decimals (`data/keys-money-time`). One behaviour per test; several asserts about that behaviour are fine.

## Examples
```python
def test_partial_refund_keeps_platform_fee():  # behaviour, named after the rule
    order = make_order(total=10_000, fee=300)  # factory; only relevant values shown
    refund(order, amount=4_000, clock=FixedClock("2026-10-10T12:00Z"))
    assert order.refunded == 4_000
    assert order.fee == 300
    assert outbox.sent == [RefundIssued(order.id, 4_000)]  # fake outbox: state, not a mock expectation
```

## Anti-patterns
- `assert_called_once_with` on your own internals; tests that mirror the implementation line by line.
- Mocks returning mocks (`a.b().c()` chains): a sign the design needs a seam.
- Snapshot tests of large objects nobody reads; they get blindly updated.
- Shared mutable fixtures; order-dependent tests; `sleep(2)`.
- Tests with no assertion, or asserting only that a mock was called.

## Checks
- Review: would this test still pass if I refactored without changing behaviour? Would it fail if the rule broke?
- Mutation testing on money/auth modules shows whether assertions really check behaviour (`testing/mutation`).
- `eos test-integrity` flags removed assertions and new skips; run `pytest -p randomly` or Vitest `--sequence.shuffle` to expose hidden order dependence.

## Sources
- Software Engineering at Google (CC BY-NC-ND, linked only), ch. 12 Unit Testing: https://abseil.io/resources/swe-book/html/ch12.html · ch. 13 Test Doubles: https://abseil.io/resources/swe-book/html/ch13.html
- Fowler, TestDouble: https://martinfowler.com/bliki/TestDouble.html · Mocks Aren't Stubs: https://martinfowler.com/articles/mocksArentStubs.html
- Kent C. Dodds, Testing implementation details: https://kentcdodds.com/blog/testing-implementation-details
- Fowler, Eradicating Non-Determinism in Tests: https://martinfowler.com/articles/nonDeterminism.html
