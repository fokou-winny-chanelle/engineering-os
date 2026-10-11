---
id: mobile/auth-payments
title: Sign-in and payments on mobile (OAuth 2.0 + PKCE in the system browser, token storage and refresh, biometrics bound to keys, passkeys, mobile money with pending states and USSD fallback, App Store and Google Play payment rules)
area: mobile
read_when: building login, session refresh, biometric unlock or passkeys in a mobile app, integrating MTN MoMo / Orange Money or another mobile-money flow, or deciding whether a purchase must use Apple/Google in-app billing
verified: 2026-10-10
revisit_days: 180
sources: ["https://www.rfc-editor.org/rfc/rfc8252.html", "https://www.rfc-editor.org/rfc/rfc9700.html", "https://developer.android.com/identity/sign-in/credential-manager", "https://developer.android.com/identity/passkeys", "https://developer.apple.com/documentation/authenticationservices/supporting-passkeys", "https://developer.android.com/identity/sign-in/biometric-auth", "https://developer.apple.com/documentation/localauthentication/accessing-keychain-items-with-face-id-or-touch-id", "https://developer.apple.com/app-store/review/guidelines/", "https://support.google.com/googleplay/android-developer/answer/9858738", "https://momodeveloper.mtn.com/content/html_widgets/qoftb.html"]
---
# Sign-in and payments on mobile

Mobile adds three twists to web auth and payments: the app is a public client (no secret can hide in it), the device can unlock keys with biometrics, and the stores have rules about how money is taken. Server-side detail: `security/authentication`, `security/oauth-oidc-jwt`, `security/payments`; provider callbacks and outages: `ops/africa-connectivity`. Money and auth changes are risky-lane: human review.

## Decision guide

**1. OAuth/OIDC on a native app (RFC 8252, RFC 9700).**
- Use the **system browser** (Custom Tabs on Android, `ASWebAuthenticationSession` on iOS; `expo-auth-session`/`expo-web-browser`, `flutter_appauth`). RFC 8252: native apps MUST NOT use embedded user-agents (WebViews) for the authorization request, and MUST use **PKCE**. The app is a public client: no client secret in the binary.
- Redirect with a claimed https link (App Links / Universal Links) where possible; a private-use scheme only with PKCE.
- Short-lived access token in memory; refresh token in secure storage (Keychain / Keystore-backed), rotated on use and revocable server-side (RFC 9700 recommends refresh-token rotation or sender-constraining for public clients). Logout clears secure storage and revokes on the server.
- First-party simple login (phone + OTP, email + password) can be your own API instead of OAuth; the same storage and rotation rules apply. SMS OTP: use the platform SMS autofill (Android SMS Retriever / iOS one-time-code field) rather than reading the inbox.

**2. Biometrics: unlock a key, not a boolean.** A "biometric passed" flag in JS/Dart is trivially bypassed on a rooted device. Bind biometrics to cryptography: Android `BiometricPrompt` with a `CryptoObject` and `BIOMETRIC_STRONG` (Class 3) authenticators; iOS Keychain items protected with an access control that requires Face ID/Touch ID. Use biometrics to unlock the stored refresh token or sign a server challenge, and for **step-up** before sensitive actions (send money, change phone number), as MASVS-AUTH-3 expects. Always offer a PIN/password fallback; many entry-level phones have weak or no biometric sensors.

**3. Passkeys.** Android's Credential Manager supports passkeys on Android 9 (API 28) and higher; iOS supports passkeys through Authentication Services with associated domains. Passkeys need a relying-party domain you control (`assetlinks.json`, `apple-app-site-association`). Offer them alongside phone/OTP, not instead of it: shared phones and lost devices are common, so recovery must not depend on one device.

**4. Store rules for payments (re-check the current text before launch).**
| What is sold | Apple (App Review Guidelines) | Google Play (Payments policy) |
|---|---|---|
| Digital content/features used in the app (premium tier, credits) | in-app purchase required (3.1.1) | Google Play billing required |
| Physical goods, real-world services (delivery, transport, tickets) | must use other methods, not IAP (3.1.3(e)) | Play billing must **not** be used |
| Bill payments, peer-to-peer transfers | not IAP | Play billing must not be used (utility bills, P2P listed) |
| Banking/financial services | app must be submitted by the legal entity offering the service (5.1.1(ix)) | check Play's financial-services policy |
A mobile-money app for paying suppliers, bills or physical goods uses the operator's API, not store billing. Selling an app subscription (e.g. premium features of an SME tool) inside the app needs IAP/Play billing, or the rules for reader/multiplatform apps; get this checked before building. Apps that let users create accounts must let them delete the account in the app (Apple).

**5. Mobile money flows (MTN MoMo, Orange Money, and similar).**
- The app never talks to the operator with secrets: app → your API → operator. Your API creates the request with an idempotency key (MTN asks for a UUID v4 per transaction, which you generate and later use to check status).
- The request is **asynchronous**: MTN's collection `requesttopay` returns `202 Accepted`; the user approves on their phone (USSD push or the operator app); your server learns the result by callback or by polling status. MTN's FAQ says callbacks are sent once, with no retry, so poll when no callback arrives.
- The app shows explicit states: *initiated → waiting for approval on your phone (with the operator's name and amount) → success / failed / timed out*. Never show success from the client side; read the final state from your server. Keep the screen recoverable after the app is killed (state lives on the server and in the local DB).
- Timeouts: tell the user what to do ("dial your operator's menu to check", "we will notify you"); never auto-retry a payment without the same idempotency key.
- **USSD fallback** for users without data or a smartphone: keep the critical flows (pay, check balance/status) possible through a USSD menu or SMS run by your aggregator or operator; keep menus short because USSD sessions time out. Show the USSD code in the app as text for users who prefer it. Use only codes the operator publishes; never invent one.

## Examples
```ts
// Expo: OAuth with PKCE in the system browser
const discovery = useAutoDiscovery("https://auth.example.cm");
const [request, result, promptAsync] = useAuthRequest(
  { clientId: "mobile-app", redirectUri: makeRedirectUri({ scheme: "exampleapp" }),
    scopes: ["openid", "profile", "offline_access"], usePKCE: true }, discovery);
// exchange the code on result?.type === "success"; store the refresh token with expo-secure-store
```

## Anti-patterns
- Login in a WebView; a client secret in the app; tokens in AsyncStorage.
- `if (await LocalAuthentication.authenticateAsync()) unlock()` with no key bound to the result.
- Showing "payment successful" before the server confirms; retrying a payment with a new idempotency key.
- Using IAP for physical goods, or selling digital premium features through mobile money inside an iOS app without checking the rules.
- No path for users without data (USSD/SMS) on critical flows.

## Checks
- [ ] Authorization uses the system browser + PKCE; no client secret in the bundle (Semgrep `eos-mobile` rules).
- [ ] Biometric unlock bound to a Keystore/Keychain key; PIN fallback; step-up on sensitive actions.
- [ ] Payment screen states tested: approve, reject, timeout, app killed mid-flow, duplicate tap.
- [ ] Store payment rules for each product line written in the release doc and reviewed by a human.

## Sources
- RFC 8252, OAuth 2.0 for Native Apps: https://www.rfc-editor.org/rfc/rfc8252.html
- RFC 9700, OAuth 2.0 Security Best Current Practice: https://www.rfc-editor.org/rfc/rfc9700.html
- Android Credential Manager: https://developer.android.com/identity/sign-in/credential-manager · passkeys: https://developer.android.com/identity/passkeys
- Apple, supporting passkeys: https://developer.apple.com/documentation/authenticationservices/supporting-passkeys
- Android biometric authentication (CryptoObject, BIOMETRIC_STRONG): https://developer.android.com/identity/sign-in/biometric-auth
- Apple, keychain items with Face ID / Touch ID: https://developer.apple.com/documentation/localauthentication/accessing-keychain-items-with-face-id-or-touch-id
- App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- Google Play Payments policy: https://support.google.com/googleplay/android-developer/answer/9858738
- MTN MoMo developer FAQ (callbacks): https://momodeveloper.mtn.com/content/html_widgets/qoftb.html
