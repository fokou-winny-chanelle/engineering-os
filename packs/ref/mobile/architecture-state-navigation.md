---
id: mobile/architecture-state-navigation
title: Mobile app architecture, state and data layers, and navigation (layers, single source of truth, server vs local vs UI state, deep links, auth-gated routes)
area: mobile
read_when: structuring a mobile codebase, deciding where state lives (server cache, local DB, UI state), wiring navigation, tabs and deep links, or guarding signed-in routes
verified: 2026-10-10
revisit_days: 180
sources: ["https://developer.android.com/topic/architecture", "https://docs.flutter.dev/app-architecture/recommendations", "https://docs.expo.dev/router/introduction/", "https://docs.expo.dev/router/advanced/authentication/", "https://tanstack.com/query/latest/docs/framework/react/react-native", "https://tanstack.com/query/latest/docs/framework/react/guides/network-mode", "https://pub.dev/packages/go_router"]
---
# Mobile architecture, state and navigation

The same shape works for React Native, Flutter and native apps: a thin UI that renders state, a data layer that owns it, and navigation driven by URLs so deep links and notifications land in the right place. Android's and Flutter's official architecture guides agree on the core ideas below.

## Decision guide

**1. Layers.**
| Layer | Holds | Rules |
|---|---|---|
| UI (screens, components/widgets) | rendering, user events | no HTTP, no SQL; reads state, sends events |
| State holders (view models, hooks, Riverpod/Bloc) | screen state, loading/error, form drafts | one per screen or feature; testable without the UI |
| Domain (optional) | use cases that combine repositories | add only when logic is reused or complex (money rules, sync decisions) |
| Data (repositories + services) | the single source of truth per data type; API client, local DB, secure storage | repositories are the only writers; services wrap one source and hold no state |

Organise folders by feature (`features/invoices/{ui,data}`), with a small `core/` for the API client, DB, auth and design system. Share validation, API types and money formatting with the backend or web through a workspace package where the language allows (`api/contract-first` for generated clients).

**2. Single source of truth and one-way data flow.** Each data type has one owner that exposes it immutably and changes it only through functions or events (Android guide). In an offline-first app that owner is usually the **local database**: screens observe queries, the sync engine updates the database, and the UI re-renders. State flows down, events flow up.

**3. Three kinds of state; keep them apart.**
- **Server state** (lists, records from your API): cache with a query library (TanStack Query in RN, repositories with streams in Flutter). In React Native wire TanStack Query's `onlineManager` to NetInfo or `expo-network` and `focusManager` to `AppState`, because the browser events it uses on the web do not exist. Use `networkMode: 'offlineFirst'` when an HTTP cache or local layer may answer offline.
- **Local durable state** (drafts, outbox, offline records): SQLite-based storage (`mobile/offline-sync`). Not AsyncStorage/SharedPreferences for anything large, relational or sensitive.
- **UI state** (open sheet, selected tab, input text): local to the component or view model. Do not put it in a global store.
Secrets and tokens are a fourth kind: secure storage only (`mobile/security-masvs`).

**4. Navigation.**
- RN/Expo: Expo Router (file-based, typed routes, every screen deep-linkable). Flutter: `go_router` (URL routes, redirects, `StatefulShellRoute` for tabs). Native: Navigation Compose / SwiftUI `NavigationStack` with typed destinations.
- Platform conventions differ (back button and predictive back on Android, swipe-back and tab bars on iOS): see `design/ia-navigation-platforms`.
- **Auth-gated routes**: guard at the router (`Stack.Protected guard={!!session}` in Expo Router, `redirect:` in go_router), not in every screen. Keep the intended URL and continue there after sign-in.
- **Deep links and notification taps** go through the same router: parse, validate against an allowlist of routes and parameter formats, check auth and ownership on the server, then navigate. A link must never trigger a payment or a destructive action without a confirmation screen.
- Restore state after process death (Android kills background apps on low-RAM phones): keep drafts in the DB, not in memory; routes must be rebuildable from the URL.

**5. Old app versions.** Users stay on old builds for months. Keep the API backward compatible (`api/evolution`), send a minimum supported version from the server, and show a blocking "update required" screen only for security or breaking changes; otherwise a soft prompt. Feature flags let the server turn features off in old builds.

## Examples
```tsx
// Expo Router root layout: one place decides what a signed-out user can reach.
export default function RootLayout() {
  const { session } = useSession();
  return (
    <Stack>
      <Stack.Protected guard={!!session}><Stack.Screen name="(app)" /></Stack.Protected>
      <Stack.Protected guard={!session}><Stack.Screen name="sign-in" /></Stack.Protected>
    </Stack>
  );
}
```
```dart
// go_router: auth redirect + validated deep-link parameter
final router = GoRouter(
  redirect: (ctx, s) => auth.isSignedIn || s.matchedLocation == '/sign-in' ? null : '/sign-in?from=${Uri.encodeComponent(s.uri.toString())}',
  routes: [GoRoute(path: '/invoices/:id', builder: (ctx, s) {
    final id = s.pathParameters['id']!;
    return RegExp(r'^[0-9a-f-]{36}$').hasMatch(id) ? InvoiceScreen(id: id) : const NotFoundScreen();
  })],
);
```

## Anti-patterns
- Screens calling `fetch`/`http` directly and keeping their own copies of the same record.
- A global store holding server data, UI flags and tokens together.
- Deep links that jump straight into an action (pay, delete, change phone number) or skip the auth guard.
- Assuming the app process lives forever: drafts lost when Android reclaims memory.
- Breaking the API for old app versions with no minimum-version mechanism.

## Checks
- [ ] Every data type has one owner (repository/DB); screens observe it.
- [ ] Router guards cover all signed-in routes; deep-link parameters validated (allowlist, format).
- [ ] Process-death test: background the app, kill it (`adb shell am kill <package>`), reopen; the draft and route survive.
- [ ] Minimum-supported-version and forced-update path tested against an old build.

## Sources
- Android, Guide to app architecture (SSOT, UDF): https://developer.android.com/topic/architecture
- Flutter, architecture recommendations: https://docs.flutter.dev/app-architecture/recommendations
- Expo Router introduction: https://docs.expo.dev/router/introduction/ · authentication: https://docs.expo.dev/router/advanced/authentication/
- TanStack Query, React Native: https://tanstack.com/query/latest/docs/framework/react/react-native · network mode: https://tanstack.com/query/latest/docs/framework/react/guides/network-mode
- go_router: https://pub.dev/packages/go_router
