---
id: react-native-expo
title: React Native with Expo
kind: stack
mode: files
when: editing an Expo / React Native app (app.json, app/ routes, native config, EAS)
description: Expo + React Native conventions - Expo Router, dev builds, config plugins, EAS Build/Update, secure storage, offline, performance, Maestro tests.
globs: ["**/app.json", "**/app.config.*", "**/eas.json", "**/app/**/*.tsx", "**/src/**/*.tsx", "**/metro.config.*", "**/babel.config.*"]
markers: ["app.json", "app.config.ts", "app.config.js"]
contains: ["expo"]
requires: ["typescript"]
fast_check: ""
full_check: "{pm} exec expo install --check"
ci: ""
---
# Stack: React Native + Expo (adds to TypeScript pack)

## Ground truth
Check `expo` in package.json and read the docs for *that* SDK (docs MCP). At the time of writing, Expo SDK 57 ships React Native 0.86 (SDK 58 in beta). The New Architecture is mandatory since SDK 55; RN supports only its latest 3 minors. Upgrade one SDK at a time: `npx expo install expo@^<next> --fix`, then `npx expo-doctor@latest`.

## Rules
1. **Versions come from Expo.** Add native-touching packages with `npx expo install <pkg>` (it picks SDK-compatible versions), never a bare `npm install`. CI runs `expo install --check`.
2. **Dev builds, not Expo Go**, for real apps (`expo-dev-client`). Native changes go through config plugins and Continuous Native Generation (`expo prebuild`). Don't hand-edit `ios/`/`android/` unless the project committed them on purpose (ADR).
3. **Routing.** Use Expo Router (file-based, in `app/`) with typed routes. Deep links and universal links validate their params, and auth-gated routes check the session.
4. **Secrets and storage.** Tokens go in `expo-secure-store`, never AsyncStorage. `EXPO_PUBLIC_*` variables ship inside the app, so nothing secret goes there. API keys that cost money stay on your server.
5. **Offline-first.**
   - Local SQLite (`expo-sqlite`) or a sync engine for app data; a query cache (e.g. TanStack Query) with persistence for server data.
   - Queued writes carry idempotency keys.
   - Use `@react-native-community/netinfo` to show offline state.
6. **Performance.**
   - FlashList (or FlatList tuned) for long lists, `expo-image` with caching, and memoised list items.
   - Run animations on the UI thread (Reanimated).
   - Check bundle size and startup time on a low-end Android device in a release build. Dev mode is not representative.
7. **Builds and updates.**
   - EAS Build in CI with credentials stored in EAS or the CI secret store.
   - Set the `runtimeVersion` policy so OTA updates (EAS Update) only reach compatible binaries.
   - Use update channels (preview → production) with staged rollout. OTA updates carry JS/assets only and must follow store rules.
8. **Platform behaviour.** Safe areas (`react-native-safe-area-context`), Android back button, keyboard avoidance, dynamic type, and `accessibilityLabel`/`accessibilityRole` on every touchable.
9. **Observability.** Crash and error reporting (e.g. Sentry for React Native) with source maps uploaded by the build, and release health per channel.

## Testing
- Jest with `jest-expo` + React Native Testing Library for components and hooks. Mock native modules at the boundary only.
- E2E with Maestro flows (`.maestro/*.yaml`) on a release-like build. Use Detox if you need gray-box sync for complex async flows.
- Test on one small, cheap Android phone and one iPhone before release.

## Pitfalls the AI often makes
- Uses web-only APIs (`window`, `localStorage`, DOM elements) or React DOM components.
- Installs packages with npm/pnpm directly and gets versions that don't match the SDK.
- Writes old-architecture-only native module code. Ignores Android-specific behaviour (back, permissions, edge-to-edge).
- Stores tokens in AsyncStorage. Tests only in Expo Go or dev mode.
