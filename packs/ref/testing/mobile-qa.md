---
id: testing/mobile-qa
title: Mobile app testing (Maestro, Detox, Flutter integration_test, device farms) and the QA process for a solo dev or small team (exploratory charters, release checklist, bug bash)
area: testing
read_when: testing a mobile app on devices, choosing Maestro vs Detox vs integration_test or a device farm, planning manual/exploratory testing, writing a release test checklist or running a bug bash
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.maestro.dev/get-started/what-is-maestro", "https://wix.github.io/Detox/docs/introduction/getting-started", "https://wix.github.io/Detox/docs/troubleshooting/flakiness", "https://docs.flutter.dev/testing/integration-tests", "https://wix.github.io/Detox/docs/introduction/environment-setup", "https://pub.dev/packages/patrol", "https://github.com/mobile-dev-inc/maestro/releases", "https://firebase.google.com/docs/test-lab", "https://docs.aws.amazon.com/devicefarm/latest/developerguide/welcome.html", "https://media.pragprog.com/titles/ehxta/charters.pdf", "https://less.works/papers/et.pdf"]
---
# Mobile testing and QA process

Automated tests prove what you thought of; a short, structured human pass finds what you did not. A small team needs both, sized to the risk of the release. Mobile platform guidance (offline, low-end Android, store review) is in the mobile pack; rollout and rollback in the release pack.

## Decision guide

**1. Mobile test layers.**
- Unit and widget/component tests for logic and screens (fast, on the dev machine and CI).
- A few E2E flows on a real build: login, the money path, offline→online sync, push-notification deep link, upgrade from the previous version.
- Manual checks on real devices for what automation misses: performance on a low-end phone, gestures, permissions dialogs, accessibility (TalkBack/VoiceOver).

**2. Pick the E2E tool.**
| Tool | Fits | Notes |
|---|---|---|
| Maestro | any stack (native, Flutter, React Native) and web; black-box flows in YAML | drives the device through the accessibility layer like a user; built-in tolerance for flakiness and automatic waiting, so no `sleep()` |
| Detox | React Native apps with complex flows | open-source; runs on a real device or simulator; tests in JS/TS |
| Flutter `integration_test` | Flutter apps, tests in Dart next to widget tests | `flutter drive` on a physical device or emulator; also runs in device farms |

Versions (2026-10-10): Maestro CLI 2.11.0 (pin it and verify the release checksum in CI; `eos scaffold mobile` does). Detox officially tests React Native 0.77–0.84 with the New Architecture; newer RN (Expo SDK 57 ships 0.86) "might work" but is not yet tested by the Detox team, so try it on a branch first. Flutter: `patrol` (4.x) adds native-UI interaction (permission dialogs, notifications) to integration tests.

Start with Maestro smoke flows unless the team already lives in Detox or Dart tests. Give elements stable accessibility labels or test ids; that helps both automation and screen-reader users. Flakes multiply with suite size (Detox docs: 100 tests at 0.5% flakiness fail about 40% of runs), so keep flows few and quarantine flakes with an expiry (`testing/flaky-speed`).

**3. Devices: emulators first, real devices for coverage.** Run E2E on emulators/simulators in CI. Before a release, run the smoke flows on real devices that match your users (check analytics for top models and OS versions, include an old low-RAM Android). Device farms rent real hardware: AWS Device Farm runs automated tests and offers remote access to physical devices in the browser. **Firebase Test Lab is deprecated and will shut down on 30 September 2027**: do not start new work on it; plan a migration if you use it. Check current pricing on the vendor's page before choosing.

**3b. Low-end device testing.** Keep one cheap Android phone (2–3 GB RAM, Android 9–11, a Tecno/Infinix/itel or Samsung A-series model if that matches your users) as the reference device; run cold start, the longest list, the payment flow and offline→online sync on it each release with a 3G-class network profile, and record the numbers in the performance budget doc (`mobile/performance-low-end`).

**4. Exploratory testing with charters** (Elisabeth Hendrickson). Instead of scripted test cases, write a charter: *Explore* (target) *with* (resources, tools, constraints) *to discover* (information). Example: "Explore checkout with a slow 3G profile and an expired card to discover how payment failures are shown and retried." Run a time-boxed session (pick a length, e.g. an hour), stay on charter, note bugs, questions and new charters, then debrief. Choose charters from risk: new features, recent incidents, support tickets, what changed in this release. Agree first what findings someone would act on.

**5. Release test checklist** (keep it in `docs/testing/release-checklist.md`, one page, owned by a person).
- CI green on the release commit: unit, integration, E2E smoke, `eos check`, no expired quarantine entries.
- Risky changes: changed-line coverage met, mutation job reviewed, contract tests passed (`api/testing`), migration rehearsed (release pack).
- Hot-path changes: k6 run against staging within thresholds (`testing/performance-k6`).
- Manual: one charter session on the main change; smoke on one real iOS and one real Android device (mobile); keyboard and screen-reader pass on changed screens; upgrade from the previous version with real-looking data.
- Ready to undo: rollback or flag-off tested, monitoring and alerts in place.

**6. Bug bash before big launches.** A short, time-boxed session with everyone who will support the product (devs, design, support, founders), each with a different charter, device or persona; one shared bug list with severity; triage at the end and decide ship / fix first / accept. Turn every serious bug found into an automated test where practical.

**7. Solo dev rhythm.** Automate the boring regressions; spend human time on exploration of what changed. Keep a running "things that broke before" list and turn it into charters and tests.

## Anti-patterns
- Only emulators, never a real low-end device; or only manual testing, never automation.
- Long scripted manual test cases nobody runs; exploratory testing with no charter, no notes, no debrief.
- A release checklist that grows forever and gets ticked without doing it.
- Bug bash findings left in chat with no owner or triage.
- Building new automation on a service with an announced shutdown.

## Checks
- Mobile pack checks: lint, types, unit/widget tests and both platform builds; E2E smoke flows with Maestro (or Detox).
- Release checklist file exists and is linked from the release PR.
- Charters and bug bash results stored with the release notes (what was explored, what was found).

## Sources
- Maestro, What is Maestro?: https://docs.maestro.dev/get-started/what-is-maestro
- Detox, getting started: https://wix.github.io/Detox/docs/introduction/getting-started · flakiness: https://wix.github.io/Detox/docs/troubleshooting/flakiness
- Flutter integration tests: https://docs.flutter.dev/testing/integration-tests · Patrol: https://pub.dev/packages/patrol
- Detox environment setup (supported RN versions): https://wix.github.io/Detox/docs/introduction/environment-setup · Maestro releases: https://github.com/mobile-dev-inc/maestro/releases
- Firebase Test Lab (deprecation notice): https://firebase.google.com/docs/test-lab · AWS Device Farm: https://docs.aws.amazon.com/devicefarm/latest/developerguide/welcome.html
- Hendrickson, Explore It! charters excerpt: https://media.pragprog.com/titles/ehxta/charters.pdf · Exploratory Testing in an Agile Context (draft): https://less.works/papers/et.pdf
