---
id: flutter
title: Flutter / Dart
kind: stack
mode: files
when: editing a Flutter app or Dart package (lib/, test/, pubspec.yaml)
description: Flutter/Dart conventions - analyzer and lints, state management, null safety, platform channels, offline storage, performance, widget/integration tests.
globs: ["**/*.dart", "**/pubspec.yaml", "**/pubspec.lock", "**/analysis_options.yaml", "**/l10n.yaml", "**/*.arb"]
markers: ["pubspec.yaml"]
contains: ["flutter"]
requires: []
fast_check: "dart format . && flutter analyze"
full_check: "dart format --output=none --set-exit-if-changed . && flutter analyze && flutter test"
ci: flutter
---
# Stack: Flutter / Dart

## Toolchain
| Job | Tool | Command |
|---|---|---|
| SDK pin | FVM (`.fvmrc`) or `environment:` in pubspec plus a CI pin | `fvm use <version>` |
| Deps | pub (commit `pubspec.lock` for apps) | `flutter pub get`, `flutter pub outdated` |
| Lint | `flutter_lints` or a stricter set in `analysis_options.yaml` | `flutter analyze` |
| Format | dart format | `dart format .` |
| Tests | flutter_test, integration_test, mocktail | `flutter test`, `flutter test integration_test` |
| Codegen | build_runner (freezed, json_serializable) | `dart run build_runner build --delete-conflicting-outputs` |

Check the installed Flutter version (`flutter --version`) and read the docs for that version. At the time of writing, stable is 3.47.x with Dart 3.13; Impeller renders on iOS and Android 10+, older Android uses OpenGL.

## Rules
1. **Architecture.** UI → state (one approach per app, recorded in an ADR: Riverpod, Bloc or Provider) → repositories → data sources. Widgets hold no business logic or IO.
2. **Null safety and types.** No `!` without a proven invariant; no `dynamic` in domain code. Parse JSON into typed models at the boundary (freezed / json_serializable).
3. **Async.** Check `mounted` (or `context.mounted`) after `await` before using `BuildContext`. Cancel subscriptions and controllers in `dispose`.
4. **Secure storage.** `flutter_secure_storage` for tokens, never `shared_preferences`. No secrets in Dart code or `--dart-define` values (they ship in the binary).
5. **Offline-first.** Local DB (drift/sqflite or similar), a sync queue with idempotency keys, connectivity state shown in the UI.
6. **Performance.**
   - `const` constructors; `ListView.builder` for long lists; avoid rebuilding large subtrees (select or scoped state).
   - Use cached, resized images.
   - Profile in profile mode on a low-end Android device. Check app size with `flutter build apk --analyze-size`.
7. **Platform behaviour.** Material 3 and Cupertino conventions where expected, safe areas, Android back (`PopScope`), text scaling, and `Semantics` labels on custom widgets.
8. **i18n.** `flutter_localizations` + ARB files (`gen-l10n`). No hard-coded strings.
9. **Releases.** Signed builds from CI with keys in a secret store. Obfuscate (`--obfuscate --split-debug-info`) and upload symbols to crash reporting. Use staged rollouts.

## Testing
- Unit tests for logic, widget tests for every screen state, golden tests only for stable design-system widgets.
- `integration_test` or Maestro flows for critical journeys on a real device or emulator.

## Pitfalls the AI often makes
- Uses deprecated APIs from older Flutter versions (e.g. `WillPopScope`). Mixes several state-management libraries.
- Uses `BuildContext` across async gaps. Forgets `dispose`. Uses `setState` in huge widgets.
- Puts API keys in Dart code. Skips `const`. Tests only on a high-end device.
