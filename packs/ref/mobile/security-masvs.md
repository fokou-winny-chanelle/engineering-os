---
id: mobile/security-masvs
title: Mobile app security with OWASP MASVS v2 and MASTG (MAS profiles, secure storage, network security and pinning trade-offs, platform/IPC and deep-link hijacking, secrets, obfuscation, rooted/jailbroken-device detection, attestation)
area: mobile
read_when: storing tokens or personal data on a device, configuring network security, exported components or deep links, deciding on pinning, rooted/jailbroken-device detection, obfuscation or attestation, or planning a mobile security review
verified: 2026-10-10
revisit_days: 180
sources: ["https://mas.owasp.org/MASVS/", "https://mas.owasp.org/MASVS/03-Using_the_MASVS/", "https://mas.owasp.org/MASTG/", "https://developer.android.com/privacy-and-security/security-config", "https://developer.android.com/about/versions/12/behavior-changes-12", "https://developer.android.com/privacy-and-security/risks/backup-best-practices", "https://developer.android.com/privacy-and-security/risks/unsafe-use-of-deeplinks", "https://developer.android.com/privacy-and-security/keystore", "https://docs.expo.dev/versions/latest/sdk/securestore/", "https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html", "https://developer.android.com/google/play/integrity", "https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity", "https://docs.flutter.dev/deployment/obfuscate", "https://docs.expo.dev/guides/environment-variables/"]
---
# Mobile security with OWASP MASVS and MASTG

The app binary is public: anyone can download it, unpack it, read its strings and run it on a rooted phone. Security therefore lives on the server; the app protects the user's data on the device and in transit. MASVS v2.1 (OWASP) says what to achieve; MASTG (release v2.0, June 2026) says how to test it. Server-side controls are in `security/web-api-hardening` and `security/authentication`. Changes here need human review (risky lane).

## Decision guide

**1. Pick a MAS profile per app (a risk decision, write it in the threat model).**
| Profile | Meaning | Typical app |
|---|---|---|
| MAS-L1 Essential | baseline security for every app | catalogue, content, simple forms |
| MAS-L2 Advanced | defence in depth for sensitive data | money, health, identity, personal data at scale |
| MAS-R Resilient | resistance to reverse engineering and tampering | anti-fraud, wallets, apps protecting business logic or content |
| MAS-P Privacy | baseline privacy (data minimisation, transparency, user control) | every app that handles personal data |
Mobile-money or SME accounting app: L2 + P, plus R controls the threat model picks.

**2. MASVS control groups → what to do.**
- **STORAGE** (store sensitive data securely; prevent leakage): tokens and keys in Keychain (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`) / Android Keystore-backed storage; `expo-secure-store` (Keystore-encrypted on Android, Keychain on iOS) or `flutter_secure_storage`. Never AsyncStorage, SharedPreferences, `UserDefaults` or plain files for secrets. Disable or restrict backups (`allowBackup="false"` or `dataExtractionRules` on Android 12+ / `fullBackupContent` before) so tokens and databases are not copied off the device. No secrets in logs, screenshots of sensitive screens (`FLAG_SECURE` where justified), clipboard or crash reports.
- **CRYPTO**: use platform crypto and keys generated in the Keystore/Secure Enclave; never hard-coded keys or home-made crypto (`security/crypto`).
- **AUTH**: secure protocols (OAuth 2.0 + PKCE in the system browser), local biometrics bound to a key, step-up for sensitive operations (`mobile/auth-payments`).
- **NETWORK** (secure all traffic; pin only endpoints you control): HTTPS everywhere. Cleartext is off by default from Android 9; keep it off (`usesCleartextTraffic="false"`, no `cleartextTrafficPermitted="true"` in the network security config, no `NSAllowsArbitraryLoads` in iOS ATS). See point 3 for pinning.
- **PLATFORM** (IPC, WebViews, UI): on Android 12+ every component with an intent filter must declare `android:exported`; export only what must be, and protect exported components with permissions. WebViews: load only your own HTTPS origins; no JS bridges to untrusted content.
- **CODE**: keep the target SDK current (store deadlines in `mobile/release-ci`), enforce updates for security fixes (minimum-version check), scan dependencies, and validate all untrusted input (deep links, push payloads, QR codes, files).
- **RESILIENCE**: platform integrity (rooted or jailbroken devices, emulators), anti-tampering, anti-static and anti-dynamic analysis. These raise attacker cost; they are never a substitute for server-side checks. Prefer **attestation verified on your server** (Google Play Integrity API, which replaced SafetyNet Attestation; Apple App Attest) as a risk signal on sensitive calls over client-side root checks that are easily patched out.
- **PRIVACY**: minimise data and permissions, explain use, give users control (`mobile/observability-a11y-i18n`, `security/privacy`).

**3. Certificate pinning: usually no.** The OWASP Pinning Cheat Sheet says there is almost no situation where you should pin, because outages from rotated certificates usually outweigh the benefit. Android's network security config supports pins but warns you need backup pins, and that pin expiry avoids bricking old app versions at the cost of letting pins lapse. If a threat model (MAS-L2/R, hostile networks) requires pinning: pin the public key (SPKI) of your own intermediate or leaf, ship at least one backup key, set an expiry, plan rotation months ahead, and keep a remote kill switch. Never pin third-party endpoints you do not control.

**4. Deep links and hijacking.** Any Android app can register the same custom scheme (`myapp://`) and intercept it. Use verified **Android App Links** (`autoVerify="true"`, https, `assetlinks.json`) and **iOS Universal Links** (`apple-app-site-association`) for anything carrying tokens or opening sensitive screens. Validate every parameter against an allowlist; check auth state before showing data; never put OAuth codes or session tokens in custom-scheme links without PKCE.

**5. Secrets never in the bundle.** Everything in the app (JS bundle, `EXPO_PUBLIC_*`, `--dart-define`, `BuildConfig`, resources) can be extracted. Publishable keys meant for clients are fine (e.g. a map SDK key restricted by package name and signing certificate); provider secrets (payment API keys, service accounts, signing keys) live on your server. Flutter's docs: obfuscation renames symbols, it does not encrypt resources or protect against reverse engineering.

**6. Obfuscation and shrinking.** Turn on R8 for Android release builds and `--obfuscate --split-debug-info` for Flutter; upload mapping/symbol files to the crash reporter. Treat obfuscation as size reduction plus a speed bump (MAS-R), not as protection for secrets.

**7. Testing (MASTG).** Static: Semgrep rules (`.semgrep/eos-mobile.yml` from `eos scaffold mobile`) and `eos mobile check`. Dynamic: inspect traffic through a proxy on a test build, check what is left in app storage after logout, try deep links with hostile parameters. Map findings to MASVS IDs in the report.

## Examples
```xml
<!-- AndroidManifest.xml (release) -->
<application android:allowBackup="false" android:usesCleartextTraffic="false"
    android:networkSecurityConfig="@xml/network_security_config">
  <activity android:name=".MainActivity" android:exported="true">
    <intent-filter android:autoVerify="true">
      <action android:name="android.intent.action.VIEW" />
      <category android:name="android.intent.category.DEFAULT" />
      <category android:name="android.intent.category.BROWSABLE" />
      <data android:scheme="https" android:host="app.example.cm" />
    </intent-filter>
  </activity>
</application>
```

## Anti-patterns
- Auth tokens in AsyncStorage/SharedPreferences/`UserDefaults`; `allowBackup` left at its default `true`.
- `cleartextTrafficPermitted="true"`, `NSAllowsArbitraryLoads`, or a trust-all `TrustManager` / `badCertificateCallback` "for testing" that ships.
- API secrets in `EXPO_PUBLIC_*`, `--dart-define` or `BuildConfig`.
- Exported activities/services/receivers with no permission; deep links that skip auth or trigger actions.
- Relying on client-side root detection or obfuscation as the main defence; pinning third-party certificates.

## Checks
- [ ] MAS profile chosen and written in the threat model; MASVS IDs in security findings.
- [ ] `eos mobile check` clean (backup, cleartext, debuggable, exported components, ATS, public-env secrets).
- [ ] Semgrep `eos-mobile` rules clean or each finding justified (`nosemgrep: <id>` with reason).
- [ ] Sensitive calls verify Play Integrity / App Attest on the server; a human reviews auth/storage changes.

## Sources
- OWASP MASVS: https://mas.owasp.org/MASVS/ · using the MASVS (MAS profiles): https://mas.owasp.org/MASVS/03-Using_the_MASVS/
- OWASP MASTG: https://mas.owasp.org/MASTG/
- Android network security configuration: https://developer.android.com/privacy-and-security/security-config
- Android 12 behaviour changes (android:exported): https://developer.android.com/about/versions/12/behavior-changes-12
- Android backup best practices: https://developer.android.com/privacy-and-security/risks/backup-best-practices
- Android, unsafe use of deep links: https://developer.android.com/privacy-and-security/risks/unsafe-use-of-deeplinks
- Android Keystore: https://developer.android.com/privacy-and-security/keystore
- expo-secure-store: https://docs.expo.dev/versions/latest/sdk/securestore/
- OWASP Pinning Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html
- Play Integrity API: https://developer.android.com/google/play/integrity
- Apple App Attest (establishing your app's integrity): https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity
- Flutter obfuscation warning: https://docs.flutter.dev/deployment/obfuscate
- Expo environment variables: https://docs.expo.dev/guides/environment-variables/
