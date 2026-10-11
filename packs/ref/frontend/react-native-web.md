---
id: frontend/react-native-web
title: Sharing code between React Native (Expo) and the web (React Native for Web, Expo web output, platform-specific files, DOM components, when to keep a separate Next.js app, shared packages for tokens, schemas, API clients and translations)
area: frontend
read_when: a product has both a React Native/Expo app and a website, someone proposes one codebase for web and mobile, adding Expo web output, setting up a monorepo with shared packages, a component must behave differently on web and native
verified: 2026-10-10
revisit_days: 180
sources: ["https://necolas.github.io/react-native-web/docs/", "https://necolas.github.io/react-native-web/docs/accessibility/", "https://docs.expo.dev/workflow/web/", "https://docs.expo.dev/router/web/static-rendering/", "https://docs.expo.dev/router/advanced/platform-specific-modules/", "https://docs.expo.dev/guides/dom-components/", "https://docs.expo.dev/guides/monorepos/"]
---
# React Native ↔ web sharing

Share logic aggressively, share UI deliberately. The question is not "can one codebase run everywhere" (it can) but which surface each audience needs: a marketing or SEO-heavy site and a logged-in app behave differently on the web than on phones. Mobile-specific practice is in the `mobile` pack and the `react-native-expo` stack pack.

## Decision guide

**1. Pick the shape.**
| Situation | Shape |
|---|---|
| app-first product; web is "the app in a browser" (dashboards, account, wallet) | one Expo Router app with web output: React Native for Web renders `<View>`/`<Text>` to DOM; Expo web can be statically rendered (SEO, speed) or client-rendered |
| public site with SEO, content, marketing, heavy forms and a separate mobile app | Next.js app + Expo app in a monorepo, sharing packages (not screens) |
| existing website moving to mobile gradually | Expo DOM components (`'use dom'`) render web components inside the native app per component, then replace them with native ones over time |
| web-only team, mobile later | Next.js now; keep business logic, schemas and API client framework-free so an Expo app can reuse them |

**2. What to share (monorepo packages, `docs.expo.dev/guides/monorepos`).**
- Always: API client and types generated from OpenAPI (`api/contract-first`), validation schemas (`frontend/state-forms`), translation catalogs and formatters (XAF, dates; `frontend/i18n-l10n`), design tokens exported from one source to CSS variables and a TS object (`frontend/design-system`), pure business logic and query-key factories (`frontend/state-forms`).
- Sometimes: UI primitives, if both apps use React Native components (RNW on the web) or a cross-platform kit (Tamagui, NativeWind/Tailwind). Expect platform tweaks for focus, hover, keyboard and scrolling.
- Rarely: whole screens and navigation. Mobile patterns (tab bars, stacks, gestures) and web patterns (URLs, links, wide layouts, keyboard and mouse) differ; forcing one onto the other hurts both.

**3. Platform differences in shared code.**
- Expo Router supports `.web.tsx` / `.native.tsx` / `.ios.tsx` / `.android.tsx`; inside `src/app` a platform file only works if a non-platform version also exists (so every route is universal for deep linking). Outside `app`, use platform files for modules or `Platform.OS` for small branches.
- Keep web-only APIs (`window`, `localStorage`, DOM) and native-only modules behind platform files; the stack pack's review rule flags web APIs in native code.
- Storage: tokens in `expo-secure-store` on native, `HttpOnly` cookies on the web; never "localStorage on web because it's the same code" (`frontend/web-security`).

**4. Web quality bar still applies to RNW output.** Check the generated DOM for semantics: RNW maps the `role` prop to HTML elements where it can (`role="heading"` + `aria-level={2}` → `<h2>`, `role="article"` → `<article>`), passes `aria-*` through, and renders `<a>` when `href` is set (or use Expo Router `<Link>`), keyboard focus, `lang`, Core Web Vitals and bundle size (`eos bundle-size` reads Expo web output under `dist/`). RNW adds runtime JS compared with plain React DOM, which matters on low-end phones (`frontend/low-bandwidth`); measure before committing a content site to it.

**5. Versions.** Expo SDKs pin compatible `react`, `react-native` and `react-native-web` versions; install with `npx expo install` so they match. A Next.js app in the same monorepo may run a different React minor than the Expo SDK pins: share framework-free packages, or align versions deliberately.

## Examples
```
apps/
  web/        # Next.js 16 (SEO pages, logged-in web)
  mobile/     # Expo Router app (iOS/Android, optional web output)
packages/
  api/        # generated OpenAPI client + zod schemas
  i18n/       # messages/fr.json, messages/en.json, format.ts (XAF, Africa/Douala)
  tokens/     # tokens.json (DTCG) → css variables + tokens.ts
  domain/     # pure business logic, query keys
```

## Anti-patterns
- Rewriting a working Next.js site in RNW "to share code", losing SEO and server rendering.
- Sharing screens with `if (Platform.OS === 'web')` scattered through every component.
- Duplicated translation files and money formatting in each app, drifting apart.
- Two API clients written by hand for web and mobile.
- Shipping Expo web output without checking accessibility and bundle size in a browser.

## Checks
- Shared packages have their own unit tests and are imported by both apps in CI builds.
- `eos i18n check` on the shared catalogs; `eos bundle-size` on each web build.
- e2e for web (`testing/e2e-playwright`) and device tests for native (`testing/mobile-qa`) on the same critical flows.

## Sources
- React Native for Web, Introduction: https://necolas.github.io/react-native-web/docs/
- React Native for Web, Accessibility: https://necolas.github.io/react-native-web/docs/accessibility/
- Expo, Develop websites with Expo: https://docs.expo.dev/workflow/web/
- Expo Router, Static rendering: https://docs.expo.dev/router/web/static-rendering/
- Expo Router, Platform-specific extensions and modules: https://docs.expo.dev/router/advanced/platform-specific-modules/
- Expo, DOM components: https://docs.expo.dev/guides/dom-components/
- Expo, Work with monorepos: https://docs.expo.dev/guides/monorepos/
