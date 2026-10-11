---
id: mobile/performance-low-end
title: Mobile performance on low-end Android (startup TTID/TTFD, Baseline Profiles, list virtualisation, JS/UI threads, memory, app size budgets, Android vitals thresholds, Cameroon device and OS mix)
area: mobile
read_when: app feels slow or janky, setting startup or size budgets, building long lists, optimising for cheap Android phones (Tecno, Infinix, itel, Samsung A-series), or reading Android vitals
verified: 2026-10-10
revisit_days: 180
sources: ["https://developer.android.com/topic/performance/vitals", "https://developer.android.com/topic/performance/vitals/launch-time", "https://developer.android.com/topic/performance/baselineprofiles/overview", "https://developer.android.com/topic/performance/reduce-apk-size", "https://reactnative.dev/docs/performance", "https://shopify.github.io/flash-list/docs/", "https://docs.flutter.dev/perf/app-size", "https://docs.expo.dev/faq/", "https://gs.statcounter.com/vendor-market-share/mobile/cameroon", "https://gs.statcounter.com/android-version-market-share/mobile-tablet/cameroon", "https://transsion.com/en/about"]
---
# Performance on low-end Android

Most of your users will not have your phone. Build for an entry-level Android device on a slow network, then let better phones be faster. The budget template is `docs/mobile/performance-budget.md` from `eos scaffold mobile`; size is checked by `eos mobile size`.

## Decision guide

**1. Know the device mix (Cameroon, StatCounter, Sept 2026; web pageview shares, a proxy for devices in use).**
- Mobile vendors: Tecno 22.7%, Samsung 20.1%, Apple 16.7%, Xiaomi 10.8%, Infinix 8.4%, Huawei 5.0%, itel 4.5%. Tecno, Infinix and itel are all Transsion brands (Transsion's own site), together about 36%.
- Android versions: 14 (17.3%), 13 (15.4%), 16 (14.0%), 15 (13.9%), 12 (12.7%), 11 (8.6%), 10 (6.2%), 9 and older about 10%.
- So: support Android 7+ (Expo SDK 57's minimum) unless analytics say otherwise; test on an Android 9 or 10 phone with 2–3 GB of RAM and on a current mid-range phone. Replace these numbers with your own analytics once you have users.

**2. Startup.** Android measures **TTID** (first frame) and **TTFD** (usable; call `reportFullyDrawn()` when the real content is shown). Keep the cold-start path short: no network call before the first frame, lazy-initialise SDKs (analytics, maps, payments) after first render, show cached data first, use the platform splash screen only while loading what the first screen needs. Native Android: ship **Baseline Profiles**, which Google says make code run about 30% faster from the first launch. React Native: Hermes (default) precompiles bytecode; avoid big synchronous work at module load, and lazy-load screens. Flutter: defer heavy plugin initialisation; profile startup with `flutter run --profile --trace-startup`.

**3. Lists.** Never render a long list with `ScrollView` / `Column`. React Native: FlashList (v2, built for the New Architecture) or FlatList with stable `keyExtractor`, memoised rows, fixed-height rows where possible; Flutter: `ListView.builder` / slivers with `itemExtent` or `prototypeItem`; native: `LazyColumn` / `List`. Paginate from the server; downscale images to the cell size.

**4. Threads.** React Native: the UI renders on the main thread, your JS runs on the JS thread; a busy JS thread drops frames for anything JS-driven. Run animations on the UI thread (Reanimated worklets), keep heavy work off the JS thread (native modules, SQLite queries in native code), test in release builds (dev mode is much slower), and strip `console.log` from release bundles (the RN docs call it a big bottleneck). Flutter: keep the UI isolate free; move parsing of large JSON to `Isolate.run` / `compute`. Native: no disk or network on the main thread (StrictMode on in debug).

**5. Memory.** Entry-level phones kill background apps quickly. Decode images at display size; cap in-memory caches; release large objects on screen exit; persist drafts so a killed process loses nothing (`mobile/architecture-state-navigation`). Watch Android vitals' memory and low-memory-kill metrics per device RAM tier in Play Console.

**6. Android vitals thresholds (Play visibility).** Google may reduce your app's visibility above: user-perceived crash rate 1.09% overall or 8% on any phone model; user-perceived ANR rate 0.47% overall or 8% per phone model. A single popular low-end model can push you over the per-model line: check vitals by device.

**7. App size budget.** Google's size guide notes that users often avoid downloading apps that seem too large, especially in emerging markets on 2G/3G and pay-by-the-byte plans. An Expo "hello world" production app is under 3 MB (Expo FAQ), so size growth is mostly your dependencies and assets.
- Ship Android App Bundles (Play serves per-ABI, per-density APKs); turn on R8 code and resource shrinking.
- Audit: Flutter `--analyze-size`; Android Studio's APK Analyzer; for RN, inspect the JS bundle and native libraries per dependency.
- Set a budget in `.eos/config.json` (`"mobile": {"size_budget_mb": {"aab": 30, "ipa": 60}}` as an example, choose yours) and ratchet: `eos mobile size --update` records a reviewed baseline; risky/full lanes fail on growth above the tolerance.
- Prefer vector icons and WebP; download large optional assets on demand.

**8. Measure on real low-end devices.** Profile release builds: Android Studio profiler / Perfetto, React Native DevTools and the Perf Monitor, Flutter DevTools in profile mode, Xcode Instruments. Record cold start (median of several runs), scroll jank on the longest list, and memory after 5 minutes of use in the performance budget doc each release.

## Examples
```kotlin
// Native Android: tell the system when the screen is really usable (TTFD)
viewModel.items.observe(this) { items -> adapter.submit(items); reportFullyDrawn() }
```
```bash
adb shell am start-activity -W -S com.example.app/.MainActivity   # prints TotalTime for a cold start
```

## Anti-patterns
- Testing only on a flagship phone or an emulator on a fast laptop.
- Initialising every SDK before the first frame; blocking start-up on the network.
- Rendering whole lists; full-size images in thumbnails.
- Adding a large native dependency for one small feature without checking size impact.
- Debug-build performance numbers.

## Checks
- [ ] Performance budget doc filled for this release (cold start, jank, memory, download size) on a named low-end device.
- [ ] `eos mobile size` within budget / ratchet; R8 shrinking on.
- [ ] Android vitals per phone model reviewed before raising a staged rollout.
- [ ] Long lists virtualised; no `console.log` in release bundles.

## Sources
- Android vitals (bad-behaviour thresholds, memory): https://developer.android.com/topic/performance/vitals
- App startup time (TTID/TTFD): https://developer.android.com/topic/performance/vitals/launch-time
- Baseline Profiles overview: https://developer.android.com/topic/performance/baselineprofiles/overview
- Reduce your app size: https://developer.android.com/topic/performance/reduce-apk-size
- React Native performance overview: https://reactnative.dev/docs/performance
- FlashList: https://shopify.github.io/flash-list/docs/
- Flutter, measuring app size: https://docs.flutter.dev/perf/app-size
- Expo FAQ (app size): https://docs.expo.dev/faq/
- StatCounter Cameroon: vendors https://gs.statcounter.com/vendor-market-share/mobile/cameroon · Android versions https://gs.statcounter.com/android-version-market-share/mobile-tablet/cameroon
- Transsion brand portfolio: https://transsion.com/en/about
