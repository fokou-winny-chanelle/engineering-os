---
id: mobile/observability-a11y-i18n
title: Crash reporting and analytics with privacy, store privacy disclosures, mobile accessibility (TalkBack/VoiceOver, font scaling to 200%, touch targets) and French/English localisation on mobile
area: mobile
read_when: adding crash reporting or analytics to an app, filling Play Data safety or Apple privacy details, making screens work with screen readers and large text, or localising an app in French and English
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.sentry.io/platforms/react-native/data-management/sensitive-data/", "https://firebase.google.com/docs/crashlytics", "https://developer.apple.com/documentation/bundleresources/privacy-manifest-files", "https://support.google.com/googleplay/android-developer/answer/10787469", "https://developer.android.com/about/versions/14/features", "https://developer.android.com/guide/topics/ui/accessibility/apps", "https://reactnative.dev/docs/text", "https://docs.flutter.dev/ui/accessibility", "https://developer.android.com/guide/topics/resources/app-languages", "https://docs.expo.dev/versions/latest/sdk/localization/", "https://docs.flutter.dev/ui/accessibility-and-internationalization/internationalization"]
---
# Observability, accessibility and FR/EN on mobile

Three things teams leave to the end and then rush: knowing when the app crashes, making it usable by everyone, and speaking the user's language. Each is cheap at the start. Legal privacy duties (GDPR, Cameroon Law 2024/017) are in `security/privacy`; shared i18n and accessibility detail in `frontend/i18n-l10n` and `frontend/accessibility`; catalogs are checked by `eos i18n check`.

## Decision guide

**1. Crash reporting.** Install one crash reporter on day one: Sentry (React Native, Flutter, native; self-hostable) or Firebase Crashlytics. Upload source maps (RN), Dart symbols (`--split-debug-info`) and R8 mapping files from CI, or obfuscated stack traces are unreadable. Tag events with app version, build number, OTA update ID and release channel, so a staged rollout can be judged per build (`mobile/release-ci`). Alert on crash-free users or sessions dropping below the stop threshold of the rollout plan.

**2. Privacy in telemetry.**
- Sentry's `sendDefaultPii` controls automatic user data (IP, user context); leave it off unless you have a reason, identify users with an opaque ID, and scrub in `beforeSend` (amounts, phone numbers, tokens, query strings in breadcrumbs).
- No personal data, tokens or full URLs with secrets in logs or analytics events. Product analytics: count events, not content; sample; keep retention short; make it opt-in where the law or your policy requires.
- **Apple privacy manifest** (`PrivacyInfo.xcprivacy`): declares the data your app and each third-party SDK collect and the "required reason" APIs used; SDKs ship their own. **Google Play Data safety form**: what you collect and share, including through third-party SDKs; check each SDK's published guidance. Keep both in sync with what the code actually sends: review on every SDK addition.

**3. Accessibility (screen readers).**
- Every interactive element has a role and a short label in the user's language: RN `accessibilityRole` / `role` and `accessibilityLabel`; Flutter `Semantics` (most Material widgets provide it; add labels to icon-only buttons); native: `contentDescription` / `accessibilityLabel`.
- Test each changed screen with **TalkBack** (Android) and **VoiceOver** (iOS): reading order, labels, state ("selected", "disabled"), focus after navigation and dialogs. Flutter's docs ask that a screen reader can describe all controls intelligibly.
- Group related text (amount + currency + status) into one announcement; announce async results ("Paiement confirmé").
- Contrast at least 4.5:1 for text (Flutter and WCAG); colour is never the only signal.

**4. Text size.** Android 14 supports font scaling up to 200% with non-linear scaling (large text grows less than small text). React Native's `allowFontScaling` defaults to `true`: keep it; use `maxFontSizeMultiplier` only to stop a few fixed elements (tab labels) from breaking layout, never globally to 1. Flutter respects `TextScaler`; don't clamp it app-wide. Layouts must reflow: no fixed heights on text containers, allow wrapping, scroll when needed. Test at the largest system setting.

**5. Touch targets and motion.** At least 48×48dp touch targets on Android (Material components enforce it; custom ones must too); Apple's guidance is in `design/ia-navigation-platforms`. Respect "reduce motion" settings for non-essential animation.

**6. French and English.**
- One message catalog per language, keys not sentences in code: RN with `expo-localization` (`getLocales()`) plus i18next or similar; Flutter `gen-l10n` with ARB files (`l10n.yaml`, `app_en.arb`, `app_fr.arb`); native string resources. Run `eos i18n check` on JSON catalogs.
- Let users pick the language in the app; on Android 13+ also declare supported locales for the system's per-app language setting.
- French needs ICU plural rules (0 and 1 are singular in French), longer strings (allow about 30% more width), non-breaking spaces before `:` `;` `?` `!` and in numbers ("15 000 FCFA"), and dates in `Africa/Douala` time. Format money with `Intl.NumberFormat('fr-CM', { style: 'currency', currency: 'XAF' })` or Dart `intl` (details in `frontend/i18n-l10n`).
- Push notifications, SMS and emails are localised on the server using the user's saved language, not the device's at send time.

## Examples
```tsx
<Pressable accessibilityRole="button" accessibilityLabel={t("invoice.pay", { amount })} onPress={pay}>
  <Icon name="send" />
</Pressable>
<Text maxFontSizeMultiplier={1.6} style={styles.tabLabel}>{t("tabs.invoices")}</Text>
```
```dart
Semantics(button: true, label: l10n.payInvoice(amount), child: IconButton(icon: const Icon(Icons.send), onPressed: pay));
```

## Anti-patterns
- Shipping without a crash reporter or without symbol/source-map upload.
- Phone numbers, amounts or tokens in analytics events or breadcrumbs; `sendDefaultPii: true` by default.
- Privacy labels written once at launch and never updated when SDKs change.
- `allowFontScaling={false}` everywhere; icon buttons with no label; testing accessibility only in an emulator without a screen reader.
- Hard-coded French or English strings; concatenated sentences that break plural and word order.

## Checks
- [ ] Crash reporter wired with release tags; symbols/source maps uploaded in CI; rollout dashboards per build.
- [ ] Telemetry scrubbing reviewed; Apple privacy manifest and Play Data safety match the SDK list.
- [ ] TalkBack and VoiceOver pass on changed screens; layout works at 200% font scale.
- [ ] FR and EN catalogs complete (`eos i18n check`); money/dates formatted for `fr-CM` / `en-CM`.

## Sources
- Sentry React Native, sensitive data: https://docs.sentry.io/platforms/react-native/data-management/sensitive-data/
- Firebase Crashlytics: https://firebase.google.com/docs/crashlytics
- Apple privacy manifest files: https://developer.apple.com/documentation/bundleresources/privacy-manifest-files
- Google Play Data safety: https://support.google.com/googleplay/android-developer/answer/10787469
- Android 14 features (font scaling to 200%): https://developer.android.com/about/versions/14/features
- Android, make apps more accessible (48dp targets): https://developer.android.com/guide/topics/ui/accessibility/apps
- React Native Text (allowFontScaling, maxFontSizeMultiplier): https://reactnative.dev/docs/text
- Flutter accessibility: https://docs.flutter.dev/ui/accessibility
- Android per-app language preferences: https://developer.android.com/guide/topics/resources/app-languages
- expo-localization: https://docs.expo.dev/versions/latest/sdk/localization/
- Flutter internationalization: https://docs.flutter.dev/ui/accessibility-and-internationalization/internationalization
