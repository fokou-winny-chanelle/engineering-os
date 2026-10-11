---
id: mobile/offline-sync
title: Offline-first data and sync on mobile (local database choice with maintenance status, outbox with idempotency keys, conflict resolution, sync engines, background sync)
area: mobile
read_when: choosing a local database (expo-sqlite, op-sqlite, WatermelonDB, Drift, sqflite, Isar) or a sync engine, designing an outbox, handling edit conflicts, or syncing in the background
verified: 2026-10-10
revisit_days: 120
sources: ["https://docs.expo.dev/versions/latest/sdk/sqlite/", "https://op-engineering.github.io/op-sqlite/", "https://github.com/OP-Engineering/op-sqlite", "https://watermelondb.dev/docs/Sync/Intro", "https://pub.dev/packages/drift", "https://pub.dev/packages/isar", "https://pub.dev/packages/isar_community", "https://docs.powersync.com/", "https://docs.flutter.dev/app-architecture/design-patterns/offline-first", "https://firebase.google.com/docs/cloud-messaging/android/receive-messages", "https://dontkillmyapp.com/tecno"]
---
# Offline-first data and sync

Offline-first means the app reads and writes a local database, and a sync process moves changes to and from the server when the network allows. Users see their data instantly, keep working in a dead zone, and never lose a form because a request timed out. Server-side idempotency and concurrency are in `api/reliability`; consistency vocabulary in `architecture/data-consistency`.

## Decision guide

**1. Decide per feature how offline it must be** (Flutter's offline-first guide names the same options).
| Level | Reads | Writes | Example |
|---|---|---|---|
| Online-only write | cached, shown as stale | blocked offline, clearly | change phone number, move money |
| Offline write, later sync | local | local first, outbox | invoices, field forms, notes |
| Local-only with periodic sync | local | local | catalogue, price lists |
Money movement is never "fire and forget offline": queue the intent, but show it as pending until the server confirms (`security/payments`).

**2. Choose the local database (status checked 2026-10-10).**
| Store | Stack | Status | Use when |
|---|---|---|---|
| `expo-sqlite` | Expo | maintained with every SDK (57.x); live queries, optional SQLCipher via config plugin, Drizzle support, key-value `Storage` | default for Expo apps |
| `op-sqlite` | React Native | 18.x (Sept 2026), MIT, active; binds to C++, backends: SQLite, SQLCipher, libSQL, Turso | heavy data, speed, encryption |
| WatermelonDB | React Native | 0.28 (Apr 2025), repo active but slow releases; lazy-loaded observable models; ships a sync protocol, your backend implements pull/push | large reactive datasets, already using it |
| Drift | Flutter | 2.35 (Oct 2026), active; typed SQL, migrations, reactive streams | default for Flutter |
| `sqflite` | Flutter | 2.4.x, maintained; raw SQL | simple needs |
| Isar | Flutter | upstream `isar` last stable 3.1.0 published about three years ago (4.0 only as dev prerelease); community fork `isar_community` 3.3.x (Mar 2026) | do not start new projects on upstream Isar; the fork only with an ADR |
| PowerSync | RN, Flutter, native | sync engine over SQLite with Postgres, MongoDB, MySQL (beta) sources; cloud or self-hosted | you want sync built, not hand-written |
AsyncStorage/SharedPreferences/`UserDefaults` are for small, non-sensitive settings only. Tokens go to secure storage (`mobile/security-masvs`). Encrypt the database (SQLCipher) when it holds personal or financial data and the device may be shared or lost; keep the key in Keychain/Keystore.

**3. The outbox pattern (client side).** Every local write and its "to send" record are committed in **one transaction**: update the row, set `sync_state = 'pending'`, insert into `outbox(id, op, entity, entity_id, payload, idempotency_key, attempt, next_at, created_at)`. A single sync worker sends entries **in order per entity**, with the `Idempotency-Key` header, so a retry after a timeout cannot create a second invoice or payment. On success, mark the row synced and delete the entry; on a 4xx validation error, stop retrying and show it to the user; on network or 5xx errors, back off with jitter (`mobile/networking-unreliable`). Generate IDs on the device (UUIDv7) so offline-created records have stable IDs before the server sees them.

**4. Pulling changes.** Ask the server for "changes since cursor" (a server-issued, monotonically increasing token, not the device clock), apply them in one transaction, then store the new cursor. Deletions travel as tombstones. If the server says the cursor is too old, do a full resync. When FCM calls `onDeletedMessages` (more than 100 messages were pending for the device, or it had not connected for over a month), the app should also do a full sync.

**5. Conflict resolution: decide per field, write it down.**
| Strategy | How | Fits |
|---|---|---|
| Server wins / reject | optimistic concurrency: send `version` (or `If-Match` ETag); server returns 409/412 on mismatch; app shows "changed elsewhere", lets the user re-apply | money, stock, anything with invariants |
| Last-writer-wins per field | server compares a server-assigned order per field, not device timestamps (device clocks are wrong) | profile fields, settings |
| Domain merge | append-only events (payments received, notes added) merge by union; counters as increments, not absolute values | ledgers, activity logs, quantities |
| CRDTs | merge automatically (e.g. text, lists) | collaborative editing; heavier, rarely needed for business apps |
Never silently drop a user's offline edit: keep the rejected change and show it.

**6. Background sync.** Sync when the app opens, when connectivity returns, and on a schedule. Android: WorkManager with network constraints; iOS: `BGTaskScheduler`, which the OS runs when it chooses. Some Android vendor skins (e.g. Tecno's) freeze background apps aggressively (community reports on dontkillmyapp.com), so foreground sync on app open is the one you can count on. Expo: `expo-background-task`; Flutter: `workmanager`. Respect Data Saver and Low Data Mode (`mobile/networking-unreliable`).

**7. Show sync state.** Per record ("pending", "failed: tap to retry"), and globally ("3 changes waiting", last synced time). Users in low-connectivity areas trust apps that are honest about it.

## Examples
```sql
-- one transaction per user action
BEGIN;
UPDATE invoice SET total_xaf = 15000, sync_state = 'pending' WHERE id = :id;
INSERT INTO outbox(id, op, entity, entity_id, payload, idempotency_key, attempt, next_at, created_at)
VALUES (:uuid7, 'update', 'invoice', :id, :json, :uuid4, 0, :now, :now);
COMMIT;
```

## Anti-patterns
- Calling the API from the screen and writing to the DB only on success ("offline" that loses work).
- Retrying POSTs without an idempotency key; resolving conflicts with device timestamps.
- Starting a new Flutter app on upstream Isar; storing tokens or large data in AsyncStorage.
- A sync worker per screen (parallel workers reorder writes).
- Hiding pending/failed writes from the user.

## Checks
- [ ] Each feature's offline level written down; money flows show pending until confirmed.
- [ ] Outbox entry written in the same transaction as the change; idempotency key on every replayed write.
- [ ] Airplane-mode test: create, edit, delete offline; kill the app; reconnect; server state is correct exactly once.
- [ ] Conflict test: edit the same record on two devices; the documented strategy applies and no edit is lost silently.

## Sources
- expo-sqlite: https://docs.expo.dev/versions/latest/sdk/sqlite/
- op-sqlite docs: https://op-engineering.github.io/op-sqlite/ · repository: https://github.com/OP-Engineering/op-sqlite
- WatermelonDB sync: https://watermelondb.dev/docs/Sync/Intro
- Drift: https://pub.dev/packages/drift
- Isar (upstream): https://pub.dev/packages/isar · community fork: https://pub.dev/packages/isar_community
- PowerSync docs: https://docs.powersync.com/
- Flutter, offline-first pattern: https://docs.flutter.dev/app-architecture/design-patterns/offline-first
- FCM, receiving messages (onDeletedMessages, full sync): https://firebase.google.com/docs/cloud-messaging/android/receive-messages
- Don't kill my app! (community reports on vendor background limits), Tecno: https://dontkillmyapp.com/tecno
