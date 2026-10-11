---
id: mobile/flutter
title: Flutter in practice (current stable, Impeller and its OpenGL fallback, recommended architecture, state management options, go_router, obfuscation and size)
area: mobile
read_when: starting or upgrading a Flutter app, choosing Riverpod vs Bloc vs Provider/ChangeNotifier vs signals, structuring layers, or tuning rendering, size and release builds
verified: 2026-10-10
revisit_days: 120
sources: ["https://docs.flutter.dev/perf/impeller", "https://docs.flutter.dev/app-architecture/recommendations", "https://docs.flutter.dev/app-architecture/design-patterns/offline-first", "https://docs.flutter.dev/data-and-backend/state-mgmt/options", "https://pub.dev/packages/flutter_riverpod", "https://pub.dev/packages/flutter_bloc", "https://pub.dev/packages/go_router", "https://docs.flutter.dev/deployment/obfuscate", "https://docs.flutter.dev/perf/app-size", "https://gs.statcounter.com/android-version-market-share/mobile-tablet/cameroon"]
---
# Flutter in practice

Flutter draws every pixel itself, so the UI looks the same on every phone and you control performance end to end. The stack pack `flutter` holds the always-on rules; this ref holds the detail.

## Decision guide

**1. Versions.** Stable is Flutter 3.47 with Dart 3.13 (checked 2026-10-10). Pin the SDK per project (FVM `.fvmrc`, or `mise`) so CI and every developer build with the same version; upgrade on a branch with `flutter upgrade` and `dart fix --apply`, then run the full test suite and a release build on a low-end Android phone.

**2. Rendering: Impeller and the fallback.** Impeller is the only renderer on iOS and the default on Android API 29+ (Android 10+). On older Android, or devices without Vulkan, Flutter falls back to the legacy OpenGL renderer. In Cameroon about 10% of Android pageviews come from Android 9 or older (StatCounter, Sept 2026), so test animations and shaders on an Android 9 device as well as a modern one. Jank shows in DevTools' performance view; profile in `--profile` mode on a real device, never in debug.

**3. Architecture (Flutter team's recommendations).**
- Two layers: **UI** (widgets + view models) and **data** (repositories + services). Add a **domain** layer of use cases only when logic is complex or shared by several view models.
- **Repositories are the single source of truth**: the only place data is changed; they combine local and remote sources. **Services** wrap one data source each (an HTTP API, a SQLite database, platform plugins) and hold no state.
- **MVVM with unidirectional data flow**: the view renders state from the view model and sends events; the view model calls repositories. Models are immutable (`freezed` or `built_value`).
- Dependency injection with `provider` (recommended) or Riverpod; constructor-inject repositories so tests can pass fakes.
- **Offline-first** is a repository concern: emit local data first and then fresh remote data (a `Stream`), write locally first with a `synchronized` flag, and sync in the background (see `mobile/offline-sync`).

**4. State management: pick one per app.**
| Option | Fits | Notes (pub.dev, Oct 2026) |
|---|---|---|
| `ChangeNotifier` + `provider` | small/medium apps; what the official architecture guide uses | provider 6.1.x; least ceremony |
| Riverpod (`flutter_riverpod`) | medium/large apps wanting compile-safe DI, caching and async state | 3.4.x; actively released |
| Bloc (`flutter_bloc`) | teams wanting explicit events → states, strong testability and logging | 9.1.x (last release May 2025); stable API |
| `signals` | fine-grained reactive values | 7.1.x; smaller ecosystem |
Server data (fetch, cache, retry) belongs in repositories, not in widget state. Do not mix two state libraries without an ADR.

**5. Navigation.** `go_router` (18.x) is the Flutter team's preferred router for most apps: URL-based routes, deep links, redirects for auth guards, `StatefulShellRoute` for bottom-tab stacks. Validate every path and query parameter that arrives from a link (`mobile/security-masvs`).

**6. Release builds: size and obfuscation.**
- Build Android App Bundles (`flutter build appbundle`) so Play serves per-device APKs; measure with `--analyze-size` and open the result in DevTools' app size tool.
- `--obfuscate --split-debug-info=build/symbols` renames Dart symbols; upload the symbols to your crash reporter. The Flutter docs warn that obfuscation does not encrypt resources or stop reverse engineering, and that storing secrets in an app is poor practice.
- Turn on R8 shrinking for the Android host; remove unused plugins (each brings native code).

**7. Platform channels.** Use `pigeon` for typed platform channels when you need native code; keep native modules small and test them on both platforms.

## Examples
```dart
// Repository: local first, then remote; the only writer of profile data.
class ProfileRepository {
  ProfileRepository(this._api, this._db);
  final ApiService _api; final DbService _db;
  Stream<Profile> watch() async* {
    final local = await _db.profile();
    if (local != null) yield local;
    try { final remote = await _api.profile(); await _db.save(remote); yield remote; }
    catch (_) { /* offline: keep showing local, surface sync state */ }
  }
}
```
```bash
flutter build appbundle --release --obfuscate --split-debug-info=build/symbols --analyze-size
```

## Anti-patterns
- Business logic and HTTP calls inside widgets; several sources of truth for the same data.
- Profiling in debug mode, or only on a flagship phone running Impeller.
- `badCertificateCallback` returning `true` to "fix" TLS errors (flagged by the Semgrep mobile rules).
- Shipping release builds without symbol upload, so obfuscated crash reports are unreadable.
- Adding a state-management library per feature.

## Checks
- [ ] `flutter analyze` and tests clean; SDK pinned (FVM/mise) and the same in CI.
- [ ] Release build measured with `--analyze-size`; within the app-size budget (`eos mobile size`).
- [ ] Profile-mode run on a low-end Android device on API < 29 and on a modern one.
- [ ] Symbols uploaded for obfuscated builds; `eos mobile check` passes on the Android manifest.

## Sources
- Impeller rendering engine: https://docs.flutter.dev/perf/impeller
- Architecture recommendations: https://docs.flutter.dev/app-architecture/recommendations
- Offline-first design pattern: https://docs.flutter.dev/app-architecture/design-patterns/offline-first
- State management options: https://docs.flutter.dev/data-and-backend/state-mgmt/options
- flutter_riverpod: https://pub.dev/packages/flutter_riverpod · flutter_bloc: https://pub.dev/packages/flutter_bloc · go_router: https://pub.dev/packages/go_router
- Obfuscating Dart code: https://docs.flutter.dev/deployment/obfuscate
- Measuring app size: https://docs.flutter.dev/perf/app-size
- StatCounter, Android versions in Cameroon: https://gs.statcounter.com/android-version-market-share/mobile-tablet/cameroon
