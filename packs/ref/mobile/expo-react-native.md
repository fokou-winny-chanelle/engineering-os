---
id: mobile/expo-react-native
title: React Native with Expo in practice (SDK cadence, New Architecture, Expo Router, CNG, EAS Build/Update, OTA policy, app config hardening)
area: mobile
read_when: setting up or upgrading an Expo/React Native app, configuring EAS Build or EAS Update, choosing a runtimeVersion policy, shipping OTA updates, or hardening app.json/app.config
verified: 2026-10-10
revisit_days: 120
sources: ["https://docs.expo.dev/versions/latest/", "https://docs.expo.dev/guides/new-architecture/", "https://docs.expo.dev/router/introduction/", "https://docs.expo.dev/workflow/continuous-native-generation/", "https://docs.expo.dev/eas-update/runtime-versions/", "https://docs.expo.dev/eas-update/rollouts/", "https://docs.expo.dev/eas-update/code-signing/", "https://docs.expo.dev/build-reference/app-versions/", "https://docs.expo.dev/guides/environment-variables/", "https://docs.expo.dev/versions/latest/sdk/build-properties/", "https://docs.expo.dev/faq/"]
---
# React Native with Expo in practice

Expo is the default way to build React Native apps: it generates the native projects, builds and signs them in the cloud (EAS Build), and can push JavaScript/asset updates over the air (EAS Update). The stack pack `react-native-expo` holds the always-on rules; this ref holds the detail.

## Decision guide

**1. Versions and upgrades.** Stable is SDK 57 (RN 0.86, React 19.2, Android 7+, iOS 16.4+); SDK 58 is in beta. Expo ships about three SDKs a year and React Native supports only its latest three minors, so plan an upgrade at least every second SDK. Upgrade with `npx expo install expo@^<n> --fix`, read the SDK changelog, then `npx expo-doctor`. Since SDK 55 the New Architecture is the only one; any library you add must support it.

**2. Continuous Native Generation (CNG).** Keep `android/` and `ios/` out of git (new projects already ignore them) and generate them with `npx expo prebuild` or inside EAS Build. Native changes go through config plugins and `app.config.ts`, so an SDK upgrade regenerates clean native projects instead of hand-merging Xcode/Gradle files. Eject from CNG only with a written reason.

**3. Development builds, not Expo Go, for real apps.** Expo Go cannot load your own native modules or config; use `expo-dev-client` builds for development and testing.

**4. Expo Router.** File-based routing in `app/`: every screen is deep-linkable, typed routes catch broken links at compile time, layouts (`_layout.tsx`) define stacks and tabs, and route groups `(auth)` / `(app)` split signed-in and signed-out areas. Protect routes with `Stack.Protected guard={!!session}` (or a redirect in the layout); deep links still need parameter validation (`mobile/security-masvs`). Navigation patterns are in `mobile/architecture-state-navigation`.

**5. EAS Build and versions.** Use build profiles in `eas.json` (development, preview, production). Set `"cli": {"appVersionSource": "remote"}` and `"autoIncrement": true` on production so EAS owns the Android `versionCode` / iOS `buildNumber`; you own the user-facing `version`. Credentials (keystore, certificates) stay in EAS or your secret manager, never in git. Release steps are in `mobile/release-ci`.

**6. EAS Update (OTA) policy.**
- **Runtime version** decides which binaries can run an update. `appVersion` (the default and recommended policy) ties updates to `version`; `fingerprint` hashes the native project so an incompatible update is "extremely unlikely". Pick one, write it down, and bump the native version for every native change.
- **Channels and branches:** builds point at a channel (`production`, `preview`); you publish to a branch mapped to that channel. Test an update on the preview channel with a production-like build first.
- **Rollouts:** `eas update --channel production --rollout-percentage 10`, watch crash-free sessions and errors, then raise; republish the previous update to roll back.
- **Code signing** for updates needs the Production or Enterprise plan; with money or personal data, use it or self-host updates with signatures.
- **Store rules:** OTA may fix bugs and change JS/asset behaviour, but must not change the app's primary purpose or add features that bypass review. Apple's licence (3.3.1(B)) allows interpreted code that does not change the primary purpose, create a storefront or bypass security; Google Play's rule on downloading code excludes code run in a virtual machine or interpreter. Ship new features through store review.

**7. Environment variables and secrets.** Anything prefixed `EXPO_PUBLIC_` is inlined into the JavaScript bundle at build time and readable by anyone with the app. Expo's docs: do not store sensitive info such as private keys in `EXPO_PUBLIC_` variables. API keys that must stay secret live on your server; the app calls your API, which calls the provider. EAS environment variables marked secret are for build-time use (e.g. a Sentry upload token), not for the bundle.

**8. Harden `app.json` / `app.config.ts` (checked by `eos mobile check`).**
- `android.allowBackup: false` unless you need Android backup; if you do, exclude tokens and databases with backup rules. Expo keeps the Android default, which is `true`.
- Do not set `usesCleartextTraffic: true` (expo-build-properties; HTTPS-only is the default on Android 9+); never `NSAllowsArbitraryLoads: true` in `ios.infoPlist`.
- `android.blockedPermissions` for permissions that libraries add but you do not use.
- App Links / Universal Links: `intentFilters` with `autoVerify: true` and `ios.associatedDomains`, instead of only a custom scheme.
- Release size: expo-build-properties `enableMinifyInReleaseBuilds` (R8) and `enableShrinkResourcesInReleaseBuilds` on Android.

## Examples
```jsonc
// eas.json (excerpt)
{ "cli": { "appVersionSource": "remote" },
  "build": { "preview": { "channel": "preview", "distribution": "internal" },
             "production": { "channel": "production", "autoIncrement": true } } }
```
```ts
// app.config.ts (excerpt)
export default { expo: {
  runtimeVersion: { policy: "appVersion" },
  android: { allowBackup: false, blockedPermissions: ["android.permission.RECORD_AUDIO"] },
  plugins: [["expo-build-properties", { android: { enableMinifyInReleaseBuilds: true,
    enableShrinkResourcesInReleaseBuilds: true } }]] } };
```

## Anti-patterns
- `EXPO_PUBLIC_PAYMENT_SECRET`, a service-account key, or any private key in the bundle.
- Committing `android/` and `ios/` and then editing them by hand while also using CNG.
- OTA updates to 100% with no rollout, no rollback plan, or with a native change that the runtime version does not catch.
- Shipping a new feature or payment flow by OTA to avoid review.
- Staying on an SDK whose React Native minor is no longer supported.

## Checks
- [ ] `npx expo-doctor` clean; dependencies installed with `npx expo install`.
- [ ] `eos mobile check` passes (backup, cleartext, ATS, public-env secrets, runtime version).
- [ ] Runtime version policy and rollout steps written in the release doc.
- [ ] Release builds have R8/minify on; app size within budget (`eos mobile size`).

## Sources
- Expo SDK reference: https://docs.expo.dev/versions/latest/
- New Architecture: https://docs.expo.dev/guides/new-architecture/
- Expo Router introduction: https://docs.expo.dev/router/introduction/
- Continuous Native Generation: https://docs.expo.dev/workflow/continuous-native-generation/
- EAS Update runtime versions: https://docs.expo.dev/eas-update/runtime-versions/ · rollouts: https://docs.expo.dev/eas-update/rollouts/ · code signing: https://docs.expo.dev/eas-update/code-signing/
- App versions (remote version source): https://docs.expo.dev/build-reference/app-versions/
- Environment variables (EXPO_PUBLIC_ warning): https://docs.expo.dev/guides/environment-variables/
- expo-build-properties: https://docs.expo.dev/versions/latest/sdk/build-properties/
- Expo FAQ (store rules on OTA updates, app size): https://docs.expo.dev/faq/
