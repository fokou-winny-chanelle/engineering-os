---
id: mobile/choosing-approach
title: Choosing how to build a mobile app (React Native/Expo, Flutter, native Swift/Kotlin, Kotlin Multiplatform, PWA) with current versions
area: mobile
read_when: starting a mobile app or a major rewrite, choosing React Native/Expo vs Flutter vs native vs PWA, or deciding whether one feature needs native code
verified: 2026-10-10
revisit_days: 120
sources: ["https://docs.expo.dev/versions/latest/", "https://expo.dev/changelog/sdk-58-beta", "https://reactnative.dev/releases/overview", "https://docs.expo.dev/guides/new-architecture/", "https://docs.flutter.dev/perf/impeller", "https://docs.flutter.dev/app-architecture/recommendations", "https://kotlinlang.org/docs/multiplatform/supported-platforms.html", "https://gs.statcounter.com/os-market-share/mobile/cameroon"]
---
# Choosing how to build a mobile app

The default for a small team is **one cross-platform codebase** (React Native with Expo, or Flutter) and native code only where a feature needs it. Pick by the team's language and the hardest feature, not by benchmarks. The broader native/cross-platform/PWA matrix lives in `decision-matrices`; this ref adds the mobile detail and current versions.

## Decision guide

**1. Current versions (checked 2026-10-10; re-check before you start).**
| Stack | Stable | Notes |
|---|---|---|
| Expo SDK | 57 (React Native 0.86, React 19.2) | Android 7+, iOS 16.4+, compile/target SDK 36, Node 22.13+. SDK 58 is in beta (RN 0.88, built for iOS 27). Expo ships about three SDKs a year. |
| React Native | 0.87 (0.88 in RC) | The latest three minors are supported; older ones get no fixes. Hermes V1 is the default engine since 0.84. |
| New Architecture | mandatory | Expo SDK 55+ and RN 0.82+ run only on the New Architecture (Fabric, TurboModules); the legacy architecture is frozen. Libraries that never migrated will not work. |
| Flutter | 3.47 (Dart 3.13) | Impeller is the renderer on iOS and on Android API 29+; older Android or devices without Vulkan fall back to the OpenGL renderer. |
| Kotlin Multiplatform | core tech Stable on Android and iOS | Shares Kotlin business logic; UI can stay native (SwiftUI/Compose) per platform. |

**2. Pick the approach.**
| If… | Choose | Why |
|---|---|---|
| The team knows TypeScript/React, or you share code with a Next.js web app | React Native + Expo | One language with the web; Expo handles native builds (EAS), OTA updates and most device APIs. See `mobile/expo-react-native`. |
| You want pixel-identical UI on both platforms, heavy custom drawing/animation, or the team knows Dart | Flutter | Own rendering engine (Impeller), strong tooling, one UI everywhere. See `mobile/flutter`. |
| The app lives on one platform's newest APIs (widgets, watch, CarPlay, ARKit, background audio, deep Bluetooth), or performance must be best possible on old phones | Native Swift (SwiftUI) / Kotlin (Jetpack Compose) | No bridge, day-one OS APIs, smallest binaries. Two codebases cost about twice the work. |
| You need native UI on each platform but shared logic (sync, validation, money maths) | Kotlin Multiplatform | Share the hard non-UI code; keep platform UI. Needs Kotlin and Swift skills on the team. |
| Content and forms, no push-heavy or background features, installs are a hurdle | PWA (see `frontend/low-bandwidth`) | No store, no install size; weaker iOS push and background support. Keep SMS/USSD for critical alerts. |

**3. When native code is warranted inside a cross-platform app.** Write a native module (Expo Modules API, or a Flutter platform channel / Pigeon) only when: no maintained library exists for a device API you need; a hot loop measured on a low-end phone is too slow in JS/Dart; or a platform feature has no cross-platform surface (home-screen widgets, app extensions, Android foreground services with special types). Keep the module small, typed and tested on both platforms; everything else stays shared.

**4. Market fit for Cameroon and similar markets.** StatCounter (Sept 2026, web traffic, so a proxy for devices in use) shows Android at about 83% of mobile pageviews in Cameroon and iOS about 17%. Build and test Android first, on low-end hardware, and keep iOS working. Device and OS detail is in `mobile/performance-low-end`.

**5. Library health check before adding a dependency.** It supports the New Architecture (RN) or the current Flutter stable; it had a release or commit in the last 6–12 months; it is licensed for your use; its native code size is acceptable (`mobile/performance-low-end` app-size budget).

## Examples
- SME invoicing app, team of two TypeScript developers, Next.js admin already built → Expo + Expo Router, shared API types and validation via a workspace package, op-sqlite or expo-sqlite for offline data.
- Field data-collection app with signature capture, maps and custom charts used on cheap Android phones → Flutter, Drift for offline storage, test on an Android 9 device (OpenGL fallback path).
- Mobile-money agent app that needs a foreground service, NFC and SMS retriever → native Kotlin first; iOS later or never, if the agents only use Android.

## Anti-patterns
- Picking a stack from a framework benchmark instead of the team's skills and the hardest feature.
- Starting a new React Native app on a library that only supports the old architecture.
- Two native codebases for a two-person team without a platform-specific reason.
- A PWA for an app whose core value is push notifications or background work on iOS.
- Copying versions from memory or an old blog: Expo, RN and Flutter move several times a year.

## Checks
- [ ] Decision written as an ADR (approach, versions, what would make us switch).
- [ ] Every native dependency checked for New Architecture / current Flutter support and recent maintenance.
- [ ] Android-first test plan includes a low-end device (`testing/mobile-qa`).
- [ ] Version table above re-verified against the sources when starting or upgrading.

## Sources
- Expo SDK reference (versions, platform minimums): https://docs.expo.dev/versions/latest/
- Expo SDK 58 beta changelog: https://expo.dev/changelog/sdk-58-beta
- React Native release support policy: https://reactnative.dev/releases/overview
- Expo, New Architecture guide: https://docs.expo.dev/guides/new-architecture/
- Flutter, Impeller rendering engine: https://docs.flutter.dev/perf/impeller
- Flutter architecture recommendations: https://docs.flutter.dev/app-architecture/recommendations
- Kotlin Multiplatform supported platforms and stability: https://kotlinlang.org/docs/multiplatform/supported-platforms.html
- StatCounter, mobile OS share in Cameroon: https://gs.statcounter.com/os-market-share/mobile/cameroon
