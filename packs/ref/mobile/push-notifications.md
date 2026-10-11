---
id: mobile/push-notifications
title: Push notifications (FCM and APNs limits, message types, priority and deprioritisation, collapse keys and TTL, background updates, Android 13 permission, token hygiene, SMS fallback)
area: mobile
read_when: sending push notifications or silent data messages, choosing priority, TTL or collapse keys, handling notification permission, cleaning stale device tokens, or deciding when SMS must back up push
verified: 2026-10-10
revisit_days: 180
sources: ["https://firebase.google.com/docs/cloud-messaging/customize-messages/set-message-type", "https://firebase.google.com/docs/cloud-messaging/customize-messages/collapsible-message-types", "https://firebase.google.com/docs/cloud-messaging/customize-messages/setting-message-lifespan", "https://firebase.google.com/docs/cloud-messaging/android/message-priority", "https://firebase.google.com/docs/cloud-messaging/manage-tokens", "https://firebase.google.com/docs/cloud-messaging/error-codes", "https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages", "https://developer.android.com/develop/ui/views/notifications/notification-permission", "https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns", "https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app", "https://docs.expo.dev/push-notifications/overview/"]
---
# Push notifications

Push is best-effort: delivery can be delayed, collapsed or dropped, and the user can turn it off. Use it to tell the user something or to wake the app to sync, never as the only carrier of something critical (payment results, OTPs, security alerts need SMS or in-app state too). Firebase Cloud Messaging (FCM) delivers to Android and, through APNs, to iOS; Expo's push service sits on top of both.

## Decision guide

**1. Limits to design around.**
| Item | FCM | APNs |
|---|---|---|
| Payload | 4096 bytes (2048 for topic messages; the console limits text to 1000 characters) | 4 KB (5 KB for VoIP) |
| Expiry | TTL 0 to 2,419,200 s (28 days); default 4 weeks | `apns-expiration`; stored for 30 days or less |
| Collapsing | at most 4 different collapse keys per device at a time | `apns-collapse-id` |
| Stored when offline | up to 100 non-collapsible messages per app on Android; beyond that all are discarded and the app is told (`onDeletedMessages`) → do a full sync | only one notification per bundle ID (usually the latest) |
| Background/silent | data messages; normal priority is delayed in Doze | background notifications are low priority and may be throttled; Apple: don't send more than two or three per hour |

**2. Pick the message type.**
- **Notification message** (title/body shown by the system): user-facing alerts. Keep the payload small and localised (send the user's language, FR or EN, from the server).
- **Data message**: the app handles it (sync, update a badge). Put an ID in it, not the data; the app fetches details over HTTPS, so payload limits and stale content do not matter and nothing sensitive sits in the push channel.
- Never put personal or financial details (amounts, balances, OTP codes) in the visible text if the lock screen can show it; let the user choose.

**3. Priority honestly.** FCM high priority wakes the device immediately; FCM expects high-priority messages to result in a user-visible notification and deprioritises apps that send high priority without showing one (judged over a 7-day window). Use normal priority for sync nudges; high priority only for time-sensitive, visible alerts (incoming payment request, delivery arriving).

**4. Collapse and expire.** Use a collapse key for "latest state wins" messages (sync available, order status) so a phone that was offline gets one message, not twenty. Set a TTL that matches meaning: a "your driver is here" alert is useless after minutes (short TTL); a weekly summary can wait days.

**5. Permission.** Android 13+ requires the runtime `POST_NOTIFICATIONS` permission; iOS always asks. Ask in context, after the user did something that makes the value clear ("Notify me when the payment arrives"), not on first launch. Respect a denial; offer a settings link later. Create Android notification channels per category (payments, reminders, marketing) so users can mute marketing without losing payments.

**6. Token hygiene.** Store each device token with a timestamp; refresh it from the app on start and periodically (Firebase suggests updating timestamps regularly, e.g. monthly). Delete tokens when FCM returns `UNREGISTERED` (404), or `INVALID_ARGUMENT` (400) for a valid payload. FCM treats Android registrations inactive for 270 days as expired. On logout, delete the token server-side so the next user of a shared phone does not get the previous user's alerts.

**7. Delivery reality on low-end Android.** Some vendor skins freeze background apps (see `mobile/offline-sync`), and cheap phones are often offline or in Data Saver; FCM delivers to bandwidth-constrained devices only when `bandwidth_constrained_ok` is set (test first). For must-arrive messages, combine: push → in-app inbox read on next open → SMS for critical events (payment confirmations, security changes), with deduplication by event ID.

**8. Send from the server, with retries.** Use the FCM HTTP v1 API (OAuth service account on the server, never in the app) or Expo's push service; retry 429/5xx with exponential backoff and jitter; log message IDs; measure delivery and open rates without logging message contents.

## Examples
```json
{ "message": {
    "token": "<device token>",
    "data": { "type": "invoice_paid", "invoice_id": "0192f1c3-…" },
    "android": { "priority": "normal", "collapse_key": "sync", "ttl": "3600s" },
    "apns": { "headers": { "apns-priority": "5", "apns-push-type": "background" },
              "payload": { "aps": { "content-available": 1 } } } } }
```

## Anti-patterns
- Push as the only channel for payment results or OTPs.
- High priority for silent sync (FCM deprioritises the app); hourly silent pushes on iOS (throttled).
- Amounts, balances or codes in lock-screen text; sensitive data in the payload.
- Asking for notification permission on the first screen; one channel for marketing and payments.
- Never pruning tokens; keeping the previous user's token after logout.

## Checks
- [ ] Each push type has a documented type, priority, TTL and collapse key.
- [ ] Payload size checked (< 4 KB) and free of personal/financial details.
- [ ] Token cleanup on `UNREGISTERED` and logout implemented and tested.
- [ ] Critical events have an SMS or in-app fallback with deduplication.

## Sources
- FCM message types: https://firebase.google.com/docs/cloud-messaging/customize-messages/set-message-type
- FCM collapsible messages (100-message limit): https://firebase.google.com/docs/cloud-messaging/customize-messages/collapsible-message-types
- FCM message lifespan (TTL): https://firebase.google.com/docs/cloud-messaging/customize-messages/setting-message-lifespan
- FCM Android message priority: https://firebase.google.com/docs/cloud-messaging/android/message-priority
- FCM token management: https://firebase.google.com/docs/cloud-messaging/manage-tokens · error codes: https://firebase.google.com/docs/cloud-messaging/error-codes
- FCM HTTP v1 message reference: https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages
- Android notification runtime permission: https://developer.android.com/develop/ui/views/notifications/notification-permission
- APNs, sending notification requests: https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns
- APNs, pushing background updates: https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app
- Expo push notifications overview: https://docs.expo.dev/push-notifications/overview/
