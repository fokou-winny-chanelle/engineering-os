---
id: mobile/networking-unreliable
title: Mobile networking on unreliable 2G/3G connections (timeouts, retries with backoff and jitter, request coalescing, compression, payload budgets, Data Saver and Low Data Mode)
area: mobile
read_when: writing the app's HTTP client, setting timeouts and retries, cutting data use, handling slow or flapping connections, or respecting Android Data Saver / iOS Low Data Mode
verified: 2026-10-10
revisit_days: 180
sources: ["https://raw.githubusercontent.com/square/okhttp/master/okhttp/src/commonJvmAndroid/kotlin/okhttp3/OkHttpClient.kt", "https://raw.githubusercontent.com/square/okhttp/master/okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/http/BridgeInterceptor.kt", "https://developer.apple.com/documentation/foundation/urlsessionconfiguration/timeoutintervalforrequest", "https://developer.apple.com/documentation/foundation/urlsessionconfiguration/waitsforconnectivity", "https://developer.apple.com/documentation/foundation/urlsessionconfiguration/allowsconstrainednetworkaccess", "https://developer.android.com/develop/connectivity/network-ops/data-saver", "https://raw.githubusercontent.com/cfug/dio/main/dio/lib/src/options.dart", "https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter", "https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages"]
---
# Networking on unreliable connections

On 2G/3G and congested 4G, requests are slow, drop halfway, and the radio costs battery and the user's money. Design the client so that a slow network makes the app slower, never broken or expensive. Server-side retry semantics are in `api/reliability`; regional connectivity and outages in `ops/africa-connectivity`; web-side data saving in `frontend/low-bandwidth`.

## Decision guide

**1. Set every timeout explicitly; know the defaults.**
| Client | Default | Note |
|---|---|---|
| OkHttp (Android, also under many RN libraries) | connect, read, write 10 s each; whole-call timeout none | set `callTimeout` so one request cannot hang forever |
| `URLSession` (iOS) | `timeoutIntervalForRequest` 60 s (idle time between packets); `timeoutIntervalForResource` 7 days | set `waitsForConnectivity = true` for background-tolerant requests so the session waits instead of failing |
| Dio (Flutter) | connect/receive/send timeouts are unset (`null`) | always set them |
| `fetch` (React Native) | no timeout of its own | wrap with `AbortController` and a timer |
Start points to tune with real data: connect about 10–15 s, a total budget per user action of about 20–30 s, longer for uploads. Show progress after about a second and a "still trying" state after several; never a frozen spinner.

**2. Retry safely.**
- Retry only idempotent requests (GET, PUT/DELETE by ID) or writes that carry an `Idempotency-Key` (the outbox in `mobile/offline-sync`).
- Retry on connection errors, timeouts, 408, 429 and 5xx; never on other 4xx. Honour `Retry-After`.
- Exponential backoff **with jitter** (random spread) and a cap, e.g. 1 s, 2 s, 4 s … up to 30–60 s, 3–5 attempts for interactive calls; the outbox keeps retrying in the background with longer gaps. Jitter stops thousands of phones retrying in lock-step after an outage (AWS Builders' Library).
- One retry layer only: if the HTTP library retries, the query library should not also retry the same call.

**3. Coalesce and cut requests.**
- One in-flight request per resource: if two screens ask for the same list, share the pending request instead of sending two.
- Batch small writes (send the outbox as one batch request when the API offers one).
- Prefer "changes since cursor" over refetching whole lists; paginate (cursor-based) with small first pages.
- Debounce search-as-you-type (about 300 ms) and cancel stale requests.
- Prefetch only on Wi-Fi or unmetered networks.

**4. Make responses small.**
- Compression: OkHttp adds `Accept-Encoding: gzip` and decompresses transparently; make sure the server actually compresses JSON (gzip or Brotli) and check it in the network inspector.
- Ask for only the fields you show (sparse fieldsets or a mobile-specific endpoint); avoid deeply nested includes.
- Images: request the size you render from an image CDN, in WebP/AVIF where supported; cache with long `Cache-Control` and content-hashed URLs; show placeholders, load full images on demand.
- Set and review a **payload budget** per screen (for example, the first screen of the app under a few hundred KB on a cold start); measure it in the `docs/mobile/performance-budget.md` template from `eos scaffold mobile`.

**5. Respect the user's data settings.**
- Android Data Saver (Android 7+): `ConnectivityManager.getRestrictBackgroundStatus()` tells you if it is on for your app; when on and the network is metered, the system blocks background data. Limit foreground data too (no autoplay video, lower image quality, no prefetch). Check `isActiveNetworkMetered()` before large downloads.
- iOS Low Data Mode: set `allowsConstrainedNetworkAccess = false` on non-essential requests so they do not use the network in Low Data Mode; give the user a lower-quality path.
- FCM: messages to a device in bandwidth-constrained mode are delivered only if you set `bandwidth_constrained_ok`, which Firebase says to enable only after testing that the app handles that mode.
- Offer an in-app "data saver" switch (images on tap, sync on Wi-Fi only) for users on small prepaid bundles.

**6. Detect connectivity honestly.** "Connected to Wi-Fi" does not mean "internet works" (captive portals, dead uplinks). Treat the first failed request as the signal, keep the app usable offline, and recheck on reconnect events (NetInfo / `expo-network` / `connectivity_plus`).

## Examples
```ts
// React Native: timeout + jittered retry for idempotent requests only
async function getJson(url: string, attempt = 0): Promise<unknown> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15_000);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { Accept: "application/json" } });
    if (res.status === 429 || res.status >= 500) throw new Error(`retryable ${res.status}`);
    if (!res.ok) throw Object.assign(new Error(`http ${res.status}`), { final: true });
    return await res.json();
  } catch (e: any) {
    if (e.final || attempt >= 3) throw e;
    const cap = Math.min(30_000, 1000 * 2 ** attempt);
    await new Promise((r) => setTimeout(r, Math.random() * cap)); // full jitter
    return getJson(url, attempt + 1);
  } finally { clearTimeout(timer); }
}
```
```dart
final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 20), sendTimeout: const Duration(seconds: 30)));
```

## Anti-patterns
- No timeout (Dio and `fetch` defaults), or one huge timeout that leaves users staring at a spinner.
- Retrying POSTs without an idempotency key; retry loops without jitter or a cap.
- Refetching every list on every screen focus over a metered connection.
- Full-resolution images in lists; JSON without compression.
- Ignoring Data Saver / Low Data Mode; background prefetch on metered networks.

## Checks
- [ ] Every HTTP client has explicit timeouts and a single retry policy with backoff and jitter.
- [ ] Network-throttling test (3G-class profile, 10% packet loss) on the main flows: no hang, no duplicate writes.
- [ ] Server responses compressed; payload per screen measured against the budget.
- [ ] Data Saver on (Android) and Low Data Mode on (iOS) tested: no background downloads, app still usable.

## Sources
- OkHttp client defaults: https://raw.githubusercontent.com/square/okhttp/master/okhttp/src/commonJvmAndroid/kotlin/okhttp3/OkHttpClient.kt · transparent gzip: https://raw.githubusercontent.com/square/okhttp/master/okhttp/src/commonJvmAndroid/kotlin/okhttp3/internal/http/BridgeInterceptor.kt
- Apple URLSessionConfiguration: timeoutIntervalForRequest: https://developer.apple.com/documentation/foundation/urlsessionconfiguration/timeoutintervalforrequest · waitsForConnectivity: https://developer.apple.com/documentation/foundation/urlsessionconfiguration/waitsforconnectivity · allowsConstrainedNetworkAccess: https://developer.apple.com/documentation/foundation/urlsessionconfiguration/allowsconstrainednetworkaccess
- Android, optimize network data usage (Data Saver): https://developer.android.com/develop/connectivity/network-ops/data-saver
- Dio options (timeouts): https://raw.githubusercontent.com/cfug/dio/main/dio/lib/src/options.dart
- AWS Builders' Library, timeouts, retries and backoff with jitter: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- FCM message reference (bandwidth_constrained_ok): https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages
