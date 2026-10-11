---
id: mobile/release-ci
title: Mobile release engineering and CI/CD (signing, versioning, Play Console tracks and the 12-tester rule, staged rollouts, TestFlight and phased release, target API deadlines, review guidelines, CI pipelines)
area: mobile
read_when: setting up mobile CI/CD, signing builds, numbering versions, publishing to Play Console tracks or TestFlight, planning a staged rollout or halting one, or preparing for store review
verified: 2026-10-10
revisit_days: 120
sources: ["https://support.google.com/googleplay/android-developer/answer/9842756", "https://developer.android.com/studio/publish/versioning", "https://support.google.com/googleplay/android-developer/answer/9845334", "https://support.google.com/googleplay/android-developer/answer/14151465", "https://support.google.com/googleplay/android-developer/answer/6346149", "https://developer.android.com/google/play/requirements/target-sdk", "https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/", "https://developer.apple.com/help/app-store-connect/update-your-app/release-a-version-update-in-phases/", "https://developer.apple.com/app-store/review/guidelines/", "https://docs.expo.dev/build-reference/app-versions/", "https://docs.expo.dev/eas/workflows/introduction/", "https://docs.fastlane.tools/actions/match/", "https://github.com/ReactiveCircus/android-emulator-runner"]
---
# Mobile release engineering and CI/CD

A mobile release cannot be rolled back like a web deploy: once a user installs a build, it stays until they update. So releases go out gradually, with a stop rule, from CI only. General rollout and rollback thinking is in the release pack and `ops/deploy-strategies`; OTA updates in `mobile/expo-react-native`.

## Decision guide

**1. Signing.**
- **Android:** use Play App Signing. Google holds the **app signing key** (it cannot be reset if lost, so let Google generate or hold it); you hold an **upload key** (RSA 2048+; Google can reset it if it leaks or is lost). Register the app signing key's SHA-256 fingerprint with APIs that check it (Google sign-in, maps keys, `assetlinks.json` for App Links), not only your upload key's.
- **iOS:** distribution certificate + provisioning profiles, managed by EAS credentials or fastlane `match` (encrypted in a private repo or storage).
- Keystores, `.p12`, API keys for App Store Connect / Play Console service accounts live in the CI secret store or EAS, never in git (the eos guard blocks `*.jks`, `*.keystore`, `*.p12`).

**2. Versioning.** A user-facing version (`1.4.0`, semantic) plus a build number that only goes up: Android `versionCode` (a positive integer, each upload greater; Play's maximum is 2100000000) and iOS `CFBundleVersion`. Let CI own build numbers (EAS remote version source with `autoIncrement`, or the CI run number) so two branches never collide. Tag the commit of every store build.

**3. Google Play tracks.**
| Track | Use | Notes |
|---|---|---|
| Internal testing | the team, every CI build | up to 100 testers; fast, minimal review |
| Closed testing | trusted users, field agents, pilots | email lists or Google Groups; required before production for new personal accounts |
| Open testing | public beta | listed on the store page |
| Production | everyone, through a staged rollout | |
**New personal developer accounts** (created after 13 Nov 2023) must run a closed test with at least 12 testers opted in for 14 consecutive days before applying for production access. Plan this into the first launch.

**4. Staged rollouts (Play).** For updates only (not the first release). Start small (e.g. 1–5%), watch crash-free users, ANRs, vitals per phone model and support tickets, then raise (e.g. 10% → 25% → 50% → 100%) over days. Write the stop rule beforehand (e.g. crash rate above the vitals threshold or a payment-flow error spike). Halting keeps users who already updated on the new version; resuming continues with the same user group; a fix ships as a new, higher `versionCode`.

**5. Apple.** TestFlight: up to 100 internal and 10,000 external testers; builds are testable for 90 days; the first build for external testers needs beta review. Phased release for automatic updates spreads an update over 7 days and can be paused; users can still update manually. App Review: no downloaded code that changes features (2.5.2), IAP rules for digital goods (3.1.1), account deletion inside the app when you offer account creation, a working demo account and notes for reviewers, and accurate privacy labels. Read the current guidelines before each major submission.

**6. Target API deadlines (Android).** From 31 Aug 2026 new apps and updates must target Android 16 (API 36); existing apps must target at least API 35 to stay available to new users; an extension to 1 Nov 2026 can be requested in Play Console. Check the page each year; Expo SDK 57 already targets 36.

**7. CI/CD pipeline.**
- **Every PR:** lint, types, unit/widget tests, `eos mobile check`, Semgrep (`.semgrep/eos-mobile.yml`), dependency audit.
- **Main / nightly:** release builds for both platforms, app-size check (`eos mobile size`), Maestro smoke flows on an Android emulator (`.github/workflows/mobile-e2e.yml` from `eos scaffold mobile`: `reactivecircus/android-emulator-runner`, pinned Maestro with checksum; or EAS Workflows, which can run Maestro).
- **Release:** build, sign and upload to internal testing / TestFlight automatically; promotion to production and raising rollout percentages stay human decisions.
- Options: EAS Build + EAS Submit (Expo), fastlane (any stack), Codemagic (Flutter-focused), GitHub Actions with macOS runners for iOS (more expensive minutes; check pricing). Pin every third-party action to a commit SHA.

## Examples
```yaml
# Promotion is a human step; CI only uploads to internal testing
release-android:
  if: startsWith(github.ref, 'refs/tags/v')
  steps:
    - run: eas build --platform android --profile production --non-interactive --auto-submit
```
Release doc (per version): what changed, risk lane, OTA vs binary, rollout steps with dates, stop rule, owner, rollback/fix-forward plan, store-review notes.

## Anti-patterns
- Building release binaries on a laptop; signing keys in the repo or in a chat.
- Losing the only copy of an app signing key outside Play App Signing.
- 100% rollout on day one; no stop rule; nobody watching vitals.
- Reusing or hand-editing build numbers across branches.
- Discovering the 12-tester/14-day rule the week of launch; missing the target-API deadline.

## Checks
- [ ] Release builds come only from CI; secrets in the CI store/EAS; actions SHA-pinned (`eos check`).
- [ ] Build numbers owned by CI; every store build tagged.
- [ ] Rollout plan with stop rule in the release doc; vitals reviewed before each increase.
- [ ] Target SDK meets the current Play deadline; review notes and demo account ready for Apple.

## Sources
- Play App Signing (upload vs app signing key): https://support.google.com/googleplay/android-developer/answer/9842756
- Android versioning (versionCode): https://developer.android.com/studio/publish/versioning
- Play testing tracks: https://support.google.com/googleplay/android-developer/answer/9845334
- Play testing requirements for new personal accounts: https://support.google.com/googleplay/android-developer/answer/14151465
- Play staged rollouts: https://support.google.com/googleplay/android-developer/answer/6346149
- Play target API level requirements: https://developer.android.com/google/play/requirements/target-sdk
- TestFlight overview: https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/
- Apple phased release: https://developer.apple.com/help/app-store-connect/update-your-app/release-a-version-update-in-phases/
- App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- EAS app versions: https://docs.expo.dev/build-reference/app-versions/ · EAS Workflows: https://docs.expo.dev/eas/workflows/introduction/
- fastlane match: https://docs.fastlane.tools/actions/match/
- android-emulator-runner: https://github.com/ReactiveCircus/android-emulator-runner
