---
id: mobile
title: Mobile apps (brief)
kind: phase
mode: files
when: working on iOS, Android, Flutter or React Native code
description: Use when working on native or cross-platform mobile apps (Swift, Kotlin, Flutter, React Native). Offline-first, secure storage, release trains, crash reporting, store rules.
globs: ["**/*.swift", "**/*.kt", "**/*.kts", "**/*.dart", "ios/**", "android/**", "**/pubspec.yaml", "**/app.json", "**/eas.json"]
next: [testing-qa, release]
---
# Mobile apps (brief)

## Entry
A story with ACs and UX for each platform, and a known API contract. Stack packs: `react-native-expo`, `flutter`; other stacks: `eos new-stack`. Choosing an approach (native / React Native / Flutter / PWA)? Use the decisions pack first.

## Standards
1. Offline and poor networks first.
   - Queue writes locally with idempotency keys and replay them safely.
   - Show sync state.
   - Expect long latency and dropped connections, which are common on mobile data.
2. Old clients never die. The API must stay backward compatible with versions in the wild. Use a minimum-supported-version check plus a forced-update path, and put server-driven feature flags on risky features.
3. Security per OWASP MASVS (L1 baseline, L2 with money or personal data). Tokens go in Keychain/Keystore, never plain prefs. No secrets in the binary (it is public). Pin certificates only with a rotation plan. Validate deep links.
4. Payments and identity. Follow store rules for in-app purchases versus external payments. Mobile-money and USSD flows need explicit pending and timeout states.
5. Performance and low-end devices. Watch cold start, frame drops, app size, battery and data use. Many users pay per MB on old Android phones: small downloads, compressed images, aggressive caching, SMS/USSD fallbacks for critical flows; test on a cheap Android phone with a 3G-class profile.
6. Accessibility. Support dynamic type and screen readers (VoiceOver/TalkBack), and provide labels on every icon button.
7. Releases. Staged rollouts (e.g. 1%→10%→100%), crash-free-sessions monitoring with a stop threshold, and signed builds from CI only, with signing keys in a secret manager. OTA updates (e.g. EAS Update) carry JS/assets only, follow store rules, and get the same staged rollout.
8. Privacy. Keep the permissions you request to a minimum, and keep the store privacy labels accurate.

## Deliverables
- Feature code plus unit/widget/UI tests, release notes, and a store-listing update if needed.

## Automated checks
- Platform lint/types, unit/widget tests, both platform builds, dependency audit.
- `eos mobile check` (manifest/app config) and `eos mobile size`; `eos scaffold mobile`: MASVS Semgrep rules, Maestro smoke.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `mobile/choosing-approach` (RN/Flutter/native, versions) · `mobile/expo-react-native` (EAS, OTA) · `mobile/flutter` · `mobile/architecture-state-navigation` · `mobile/offline-sync` (local DB, outbox, conflicts) · `mobile/networking-unreliable` (2G/3G) · `mobile/performance-low-end` (size, Cameroon devices) · `mobile/security-masvs` · `mobile/auth-payments` (PKCE, mobile money, store rules) · `mobile/push-notifications` · `mobile/release-ci` · `mobile/observability-a11y-i18n` · `testing/mobile-qa` · `api/evolution` (old app versions) · `security/authentication` · `frontend/react-native-web` · `design/ia-navigation-platforms`.

## Exit checklist (Definition of Done)
- [ ] Works offline or degrades gracefully, and retries are idempotent.
- [ ] Older app versions are still supported by the API (compatibility checked).
- [ ] Secrets and tokens are stored securely, and no keys are in the repo or binary.
- [ ] Crash and performance monitoring is wired, and the rollout plan is written.

## Handoff → testing-qa / release
Pass the build artefacts from CI, the test report and the rollout plan.

## Stop & escalate
Stop on store-policy questions, payment-rule questions, or any request to embed a secret in the app.
