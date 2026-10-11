---
id: design/ia-navigation-platforms
title: Information architecture and navigation (labels, card sorting, tree testing, visible vs hidden navigation) and platform conventions (Apple HIG vs Material 3: tab/navigation bars, back, targets, adaptive layouts, dynamic colour)
area: design
read_when: designing site or app navigation, naming menu items, deciding between tabs, a drawer or a hamburger, adding a screen to a mobile app, porting a design between iOS, Android and web, implementing back behaviour or predictive back
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.nngroup.com/articles/hamburger-menus/", "https://www.nngroup.com/articles/card-sorting-definition/", "https://www.nngroup.com/articles/tree-testing/", "https://developer.apple.com/design/human-interface-guidelines/tab-bars", "https://developer.apple.com/design/human-interface-guidelines/buttons", "https://developer.android.com/develop/ui/compose/components/navigation-bar", "https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture", "https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes", "https://developer.android.com/develop/ui/compose/designsystems/material3", "https://developer.android.com/guide/topics/ui/accessibility/apps"]
---
# Information architecture, navigation and platforms

IA decides whether people can find things; navigation is how the IA shows up on screen. Platform conventions decide whether the app feels broken or native. A custom visual direction is fine; custom navigation behaviour usually is not.

## Decision guide

**1. Build the IA from users' words.**
- List the top tasks (5–10) from research, support messages and analytics. Navigation is for those, not for the org chart.
- **Card sorting** (NN/g): participants group labelled cards and name the groups; open sorts reveal mental models and vocabulary, closed sorts test a proposed structure. Works remotely and with paper cards in person (useful where people are not comfortable with web tools).
- **Tree testing** (NN/g): a text-only version of the hierarchy; participants say where they would look for X. It measures findability before any visual design.
- Labels: concrete nouns or verbs in the user's language, front-loaded, same word on the menu, the page title and the button. Test French and English labels separately; a good English label translated literally may be wrong.

**2. Keep main navigation visible.** NN/g's quantitative tests: hiding the main navigation (hamburger) cut discoverability almost in half, increased task time and perceived difficulty. Use a visible tab/navigation bar or top links for the 3–5 most important destinations; a "More" menu for the rest.

**3. Mobile platforms: same product, native behaviour.**
| Topic | iOS (Apple HIG) | Android (Material 3 / Compose) |
|---|---|---|
| primary navigation | tab bar for navigation, "not to provide actions"; if users can pick tabs, default to five or fewer | navigation bar with three to five destinations of equal importance; navigation rail or drawer on larger windows |
| unavailable sections | don't hide or disable tab buttons; explain inside the section | keep destinations stable |
| badges | reserve for critical information | small badges for counts or status |
| back | edge swipe and the back button in the navigation bar; keep the hierarchy shallow | system back (gesture or button); predictive back "is enabled by default" (Android 15 removed the developer option for its animations); support it via AndroidX Activity 1.6+ callbacks; opt out only with `android:enableOnBackInvokedCallback="false"` |
| touch targets | hit region at least 44×44 pt (60×60 in visionOS) | at least 48×48 dp (Android accessibility guidance); WCAG 2.5.8 floor 24 CSS px |
| adaptive layout | size classes (compact/regular) | window size classes: compact < 600 dp, medium 600–840, expanded 840–1200, then large and extra-large |
| colour | system colours, Dark Mode, Liquid Glass guidance (added to the HIG in 2025) | Material 3 colour roles; dynamic colour from the wallpaper on Android 12+ (optional; keep brand roles for key actions) |
- Safe areas and system bars: never put tappable controls under the home indicator, notch or gesture area.
- Don't copy iOS patterns to Android or the reverse (e.g. an iOS-style back chevron with no system back support). React Native/Expo and Flutter provide platform-adaptive components; use them (`mobile` pack).

**4. Web navigation.** Top navigation with visible links on desktop; on phones, a bottom bar or a visible short list for the top tasks, and a menu for the rest. Breadcrumbs for deep hierarchies; a skip link; the current page marked (`aria-current="page"`); search when the content is large and people know names (lower-literacy users struggle with spelling: support synonyms and typos, `design/cameroon-context`).

**5. Low-end devices and data.** Keep navigation in the initial HTML (no navigation that needs a big JS bundle to appear), cache the shell, and make the main tasks reachable in few taps. Every extra step loses people (GSMA/Grameen observed users faltering after 3–4 steps in mobile money flows; see `design/cameroon-context`).

## Examples
```
Android (compact)                         iOS (compact)
┌──────────────────────────┐              ┌──────────────────────────┐
│ ← Factures         ⋮     │  system back │ ‹ Accueil   Factures     │  edge swipe
│ …                        │              │ …                        │
├──────┬──────┬──────┬─────┤              ├──────┬──────┬──────┬─────┤
│Accueil│Payer│Reçus │Plus │ nav bar 3–5  │Accueil│Payer│Reçus │Plus │ tab bar
└──────┴──────┴──────┴─────┘              └──────┴──────┴──────┴─────┘
```

## Anti-patterns
- Navigation mirroring internal departments; clever labels ("Explore", "Hub") instead of task words.
- A hamburger as the only navigation on desktop; actions (like "+ New") placed as tab-bar items on iOS.
- Hiding or disabling tabs when a section is empty.
- Overriding Android back to do nothing, or breaking predictive back with custom gesture handlers.
- Identical pixel-perfect UI on both platforms that ignores safe areas and back conventions.

## Checks
- Tree test the IA (remote tool or paper) before building navigation; fix labels that people miss.
- Critique rubric row 12 on both platforms' screenshots (simulator and emulator, compact and expanded widths).
- Android: test predictive back on a device with gesture navigation; iOS: edge-swipe back works on every pushed screen.
- e2e: main destinations reachable from every page; `aria-current` set.

## Sources
- NN/g, Hamburger menus and hidden navigation hurt UX metrics: https://www.nngroup.com/articles/hamburger-menus/
- NN/g, Card sorting: https://www.nngroup.com/articles/card-sorting-definition/
- NN/g, Tree testing: https://www.nngroup.com/articles/tree-testing/
- Apple HIG, Tab bars: https://developer.apple.com/design/human-interface-guidelines/tab-bars
- Apple HIG, Buttons: https://developer.apple.com/design/human-interface-guidelines/buttons
- Android, Navigation bar (Compose): https://developer.android.com/develop/ui/compose/components/navigation-bar
- Android, Predictive back gesture: https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture
- Android, Use window size classes: https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes
- Android, Material Design 3 in Compose: https://developer.android.com/develop/ui/compose/designsystems/material3
- Android, Make apps more accessible (touch target size): https://developer.android.com/guide/topics/ui/accessibility/apps
