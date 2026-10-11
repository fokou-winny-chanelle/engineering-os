---
id: testing/strategy
title: Test strategy - pyramid vs trophy vs honeycomb, test sizes, what to test and what not, tests per lane
area: testing
read_when: choosing how to test a new project or service, deciding where a test belongs, a suite that is slow or catches nothing, arguing "unit vs integration"
verified: 2026-10-10
revisit_days: 365
sources: ["https://martinfowler.com/articles/practical-test-pyramid.html", "https://martinfowler.com/articles/2021-test-shapes.html", "https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications", "https://engineering.atspotify.com/2018/01/testing-of-microservices", "https://testing.googleblog.com/2010/12/test-sizes.html", "https://abseil.io/resources/swe-book/html/ch12.html"]
---
# Test strategy

A test suite exists to let you change code with confidence, quickly. Pick the shape from where your bugs come from and what is cheap to run, not from a diagram. Unit-test design is in `testing/unit-design`; real dependencies in `testing/integration`; browser tests in `testing/e2e-playwright`.

## Decision guide

**1. The shapes are about the same thing.** All three say: many fast tests, few slow ones. They disagree mainly because "unit test" means different things (Fowler, 2021: *sociable* unit tests use real collaborators, *solitary* ones replace them with doubles).
| Shape | Says | Fits |
|---|---|---|
| **Pyramid** (Cohn; Fowler/Vocke) | lots of small fast unit tests, some coarser tests, very few end-to-end | libraries, domain-heavy code (pricing, ledgers, state machines), most backends |
| **Trophy** (Kent C. Dodds) | static checks at the base, some unit, **mostly integration**, few E2E; "the more your tests resemble the way your software is used, the more confidence they can give you" | frontends and UI components (test through the DOM, not internals) |
| **Honeycomb** (Spotify, 2018) | mostly integration tests of one service with its real database, few implementation-detail tests, ideally no *integrated* tests (tests whose result depends on another system being correct) | microservices that are thin over a database or queue |
For a solo dev or small team: a modular monolith with the pyramid for domain logic, honeycomb-style integration tests at the API/database boundary, a handful of E2E smoke journeys, and static checks (types, lint) everywhere.

**2. Size by resources, not by name** (Google test sizes). Small: one process, no network, no DB, no sleeps (time limit 60 s). Medium: one machine, localhost network, a real DB in a container (300 s). Large: several machines or real external systems (900 s+). Keep small tests the majority; medium tests run in CI on every PR; large tests run before release or nightly.

**3. What to test (in order of payoff).**
- Money, auth, permissions, data integrity: every rule and edge (zero, negative, rounding, currency, time zones, cross-tenant access).
- Business rules and state machines: each transition and each forbidden transition.
- The contract at your boundaries: API requests and responses, events, DB migrations (`api/testing`, `data/migrations`).
- Every bug fixed: a regression test at the lowest layer that would have caught it.
- Critical user journeys end to end (sign-up, pay, refund), a few, not every path.

**4. What not to test.**
- Framework and library behaviour (the ORM saves rows, React renders a div).
- Private helpers directly: test them through the public behaviour that uses them.
- Trivial getters, generated code, configuration constants.
- Exact copy, pixel positions or log text unless they are the requirement.
- Third-party services live: use their sandbox in a contract test, fakes elsewhere.

**5. Tests per lane (eos).** trivial: no new tests, hooks only. standard: related tests (`eos verify`), the full suite at push and in CI. risky/one-way-door: full check, changed-line coverage (`eos diff-coverage`), and mutation testing of the changed money/auth code in CI (`testing/mutation`). Load tests and long fuzzing run on schedule, never in the commit loop.

**6. Budgets that keep the loop fast.** Unit suite in seconds, PR CI under about 10 minutes, E2E smoke in minutes. When a layer gets slower, fix the layer (`testing/flaky-speed`) before adding more tests to it.

## Anti-patterns
- The ice-cream cone: mostly manual or E2E tests, few unit tests; slow and flaky.
- Mock-everything "unit" tests that pass while the integrated system is broken.
- Testing the same rule at every layer.
- Coverage targets chased with tests that assert nothing (`testing/coverage-ai-code`).
- A shared staging environment as the only integration test.

## Checks
- `docs/testing/strategy.md` (`eos scaffold tests-python`) states the layers, where each lives and what runs when.
- CI: unit + integration on every PR, diff coverage on changed lines, E2E smoke when `playwright.config.*` exists.
- Review: each new feature names its tests by acceptance criterion; each bug fix starts with a failing test.

## Sources
- Fowler/Vocke, The Practical Test Pyramid: https://martinfowler.com/articles/practical-test-pyramid.html
- Fowler, On the Diverse And Fantastical Shapes of Testing: https://martinfowler.com/articles/2021-test-shapes.html
- Kent C. Dodds, The Testing Trophy: https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications
- Spotify Engineering, Testing of Microservices: https://engineering.atspotify.com/2018/01/testing-of-microservices
- Google Testing Blog, Test Sizes: https://testing.googleblog.com/2010/12/test-sizes.html
- Software Engineering at Google, ch. 12 Unit Testing (CC BY-NC-ND, linked only): https://abseil.io/resources/swe-book/html/ch12.html
