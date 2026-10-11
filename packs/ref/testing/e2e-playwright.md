---
id: testing/e2e-playwright
title: End-to-end, visual regression and accessibility tests with Playwright - selectors, fixtures, auth state, flakiness, sharding, traces, axe
area: testing
read_when: writing or fixing browser tests, setting up Playwright in CI, flaky E2E tests, adding screenshot comparisons or automated accessibility checks
verified: 2026-10-10
revisit_days: 180
sources: ["https://playwright.dev/docs/best-practices", "https://playwright.dev/docs/locators", "https://playwright.dev/docs/auth", "https://playwright.dev/docs/test-retries", "https://playwright.dev/docs/test-cli", "https://playwright.dev/docs/test-sharding", "https://playwright.dev/docs/trace-viewer", "https://playwright.dev/docs/test-snapshots", "https://playwright.dev/docs/accessibility-testing", "https://playwright.dev/docs/test-fixtures", "https://playwright.dev/docs/mock", "https://playwright.dev/docs/clock"]
---
# E2E, visual and accessibility tests (Playwright)

E2E tests prove the wiring of a few critical journeys through the real UI. They are the slowest and flakiest layer, so keep them few, deterministic and debuggable. Strategy: `testing/strategy`; API-level tests: `api/testing`.

## Decision guide

**1. What gets an E2E test.** Sign-up/login, the money path (checkout, pay, refund), the main create/edit flow, and anything that broke in production because parts did not fit. Everything else is covered lower down. Tag the smoke set (`@smoke`) and run it on every PR; the rest nightly or before release.

**2. Selectors** (Playwright locators). Prefer what the user perceives: `getByRole('button', { name: 'Pay' })`, `getByLabel`, `getByText`, `getByPlaceholder`, `getByAltText`, `getByTitle`; `getByTestId` when there is no stable accessible name. Never CSS chains or XPath tied to layout. Narrow with chaining and `filter({ hasText })`. A test that cannot find a button by role often reveals an accessibility bug.

**3. Assertions that wait.** Use web-first assertions, `await expect(locator).toBeVisible()`, which retry until a timeout; never `expect(await locator.isVisible()).toBe(true)`, which checks once. No `waitForTimeout` sleeps.

**4. Isolation and fixtures.** Each test gets a fresh browser context (own cookies and storage). Create the data a test needs through the API or a seed fixture, not through other tests. Custom fixtures (`test.extend`) hold setup such as a seeded tenant; worker-scoped fixtures share expensive setup per worker process.

**5. Auth state.** Log in once in a *setup project*, save `storageState` to `playwright/.auth/` (add it to `.gitignore`: it holds session cookies), and declare the setup project as a dependency. Use one shared account when tests do not change server state, one account per parallel worker when they do.

**6. Control the outside world.** Do not test third-party sites you do not control. Stub external APIs with `page.route()` or replay a HAR file; freeze time with `page.clock.setFixedTime()` for dates, countdowns and expiry.

**7. Flakiness, retries, traces.** In CI: `retries: 1`, `trace: 'on-first-retry'`, `forbidOnly: true`. Playwright reports a test that fails then passes as **flaky**: treat that as a bug, quarantine it with an expiry (`eos quarantine add "<title>"`; the scaffold's config skips active entries) and fix it (`testing/flaky-speed`). `--fail-on-flaky-tests` (or `failOnFlakyTests`, since 1.52) makes any flaky result fail the run once the suite is clean. Find flakes with `--repeat-each=20`; re-run only failures with `--last-failed`.

**8. Speed.** `fullyParallel: true`; split across CI machines with `--shard=1/4` … `4/4`, the `blob` reporter, then `npx playwright merge-reports`. Install only the browsers you test (`playwright install --with-deps chromium`). Locally, `--only-changed=main` runs test files changed since a ref.

**9. Visual regression.** `await expect(page).toHaveScreenshot()` compares with a stored baseline. Rendering differs by OS, browser, fonts, hardware and headless mode, so generate and compare baselines in the same environment (the CI image or a pinned Playwright Docker image), commit them, and review every baseline update like code. Mask or hide dynamic regions (dates, avatars, ads) with `mask` or a `stylePath` stylesheet; tolerate tiny differences with `maxDiffPixels` or `threshold` rather than retrying. Keep visual tests to stable, high-value screens.

**10. Accessibility.** Run axe with `@axe-core/playwright` on key pages and states (forms with errors, dialogs open) and fail on serious and critical violations (the e2e-node scaffold does this for WCAG 2 A/AA tags). Automated checks find only some problems; keyboard-only and screen-reader passes stay manual (`testing/mobile-qa` for the release checklist).

## Anti-patterns
- Hundreds of E2E tests covering what unit and API tests could; login through the UI in every test.
- `page.waitForTimeout(3000)`; `isVisible()` inside `expect`.
- Tests that depend on order or on data left by others; one shared account for tests that mutate state.
- Raising retries or timeouts until the suite is green; committing `playwright/.auth`.
- Screenshot baselines generated on a laptop and compared on Linux CI.

## Checks
- `eos scaffold e2e-node`: config (CI retries 1 with traces, forbidOnly, quarantine skip) + smoke test with axe.
- The node stack CI runs `test:e2e` when `playwright.config.*` exists; to debug CI failures, keep `test-results/` traces as a build artifact.
- `eos quarantine check` (in `eos check`) fails CI when a quarantined E2E test is past its expiry.

## Sources
- Playwright: best practices https://playwright.dev/docs/best-practices · locators https://playwright.dev/docs/locators · authentication https://playwright.dev/docs/auth · fixtures https://playwright.dev/docs/test-fixtures
- Retries https://playwright.dev/docs/test-retries · CLI https://playwright.dev/docs/test-cli · sharding https://playwright.dev/docs/test-sharding · trace viewer https://playwright.dev/docs/trace-viewer
- Visual comparisons https://playwright.dev/docs/test-snapshots · accessibility testing https://playwright.dev/docs/accessibility-testing · mock APIs https://playwright.dev/docs/mock · clock https://playwright.dev/docs/clock
