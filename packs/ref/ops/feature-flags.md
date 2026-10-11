---
id: ops/feature-flags
title: Feature flags with OpenFeature (types, registry and expiry, rollout, kill switches, telemetry, cleanup)
area: ops
read_when: adding, reading or removing a feature flag, planning a gradual rollout or an A/B test, adding a kill switch, choosing a flag vendor, reviewing ops/flags.json
verified: 2026-10-10
revisit_days: 180
sources: ["https://martinfowler.com/articles/feature-toggles.html", "https://openfeature.dev/docs/reference/intro", "https://openfeature.dev/docs/reference/concepts/provider", "https://openfeature.dev/docs/reference/concepts/hooks", "https://openfeature.dev/docs/reference/technologies/server/python", "https://openfeature.dev/docs/reference/technologies/server/javascript/", "https://opentelemetry.io/docs/specs/semconv/feature-flags/feature-flags-logs/"]
---
# Feature flags with OpenFeature

A flag changes behaviour without a deploy. Pete Hodgson's advice (martinfowler.com): treat flags as inventory with a carrying cost and keep the inventory low. Every flag doubles the paths to test until it is removed.

## Decision guide

**1. Know which kind of flag you are adding** (Hodgson's categories; `type` in `ops/flags.json`):
| Type | Purpose | Lifetime | Example |
|---|---|---|---|
| release | ship unfinished or risky code dark, roll out gradually | days to weeks, then delete | `new-checkout` |
| experiment | A/B test with a measured outcome | until the result is in | `pricing-page-b` |
| ops | kill switch or degraded mode during incidents | long-lived, reviewed | `payments-kill-switch` |
| permission | entitlement per plan or customer | long-lived, really product config | `beta-exports` |
Release and experiment flags must expire (`eos ops check`: at most 90 days by default, `ops.flag_max_days`).

**2. Use OpenFeature as the API, pick the backend later.** OpenFeature (a CNCF incubating project) is a vendor-neutral evaluation API with SDKs for many languages. Your code calls the client; a **provider** connects it to a backend (env and file, flagd, a SaaS, your own). Switching vendors means changing one provider line. **Hooks** run around each evaluation (logging, telemetry, validation).

**3. Start with the registry provider** (`eos scaffold flags`):
- `ops/flags.json` lists every flag: key, type, description, owner, created, expires, default, optional `rollout_percent`.
- Python `flags.py` and Node `lib/flags.ts` implement an OpenFeature provider that reads the registry, honours `FLAG_<KEY>` env overrides per deployment (`FLAG_PAYMENTS_KILL_SWITCH=true`), and rolls boolean flags out to a stable share of users by hashing flag key + user ID (the same hash in both languages, so web and API agree).
- Call sites: `flag_enabled("new-checkout", user_id=...)` / `await flagEnabled("new-checkout", { userId })`. Unknown flags return the safe default, never an exception.
- Move to a flag service when you need non-developers to flip flags, per-segment targeting, audit logs or instant changes without a restart.

**4. Rules for reading flags.**
- Evaluate on the server; send the browser the result, not the targeting rules.
- Read a flag in one place (one decision point) and pass the result down; do not scatter the same key across files.
- Defaults must be the safe, old behaviour: if the provider fails, users get what worked yesterday.
- Name keys by intent (`new-checkout`, not `flag-17`); lower-case letters, digits, `-`, `_`, `.`.

**5. Rollout recipe for a release flag.** Merge dark (0%) → internal users → 1% → 10% → 50% → 100%, watching the SLO dashboard and business metrics at each step (`ops/deploy-strategies`). Hold at 100% for an agreed time, then delete the flag and the old code path in one PR.

**6. Kill switches for dependencies.** One ops flag per risky dependency (payment provider, mobile-money API, SMS gateway, an LLM API) that switches to a degraded mode: queue requests, hide the feature with a message, or route to a fallback. Document it in the runbook's Mitigation section and practise flipping it.

**7. Telemetry.** The scaffolds' trace hook adds a `feature_flag.evaluation` event to the current span with `feature_flag.key`, `feature_flag.provider.name`, `feature_flag.result.variant` and `feature_flag.result.reason` (OpenTelemetry semantic conventions, still marked Development). During an incident you can see which variant a failing request got.

**8. Cleanup is enforced.** `eos ops check` (and `eos check` in CI) fails when a flag is expired, a release or experiment flag has no expiry or lives too long, an owner is missing, or code reads a flag that is not registered (catches typos such as `payments-kill-swich`). Registered flags nobody reads produce a warning: delete them. Fowler describes "time bombs" that fail a test after expiry; this is that idea, in CI.

## Anti-patterns
- Flags with no owner or end date; a flag config nobody can explain a year later.
- Dead flags left in the code and old keys re-used; Hodgson cites Knight Capital's $460 million mistake as the cautionary tale of unmanaged flags.
- Nested flags and flags that depend on other flags; flag checks in hot loops calling a remote service.
- Targeting rules and secret variants shipped to the browser; flags as a substitute for authorization checks.
- Testing only the "on" path; leaving the old path in place after 100% rollout.

## Checks
- `eos ops check` / `eos check`: registry schema, expiry, max lifetime, unregistered keys read in code (`flag_enabled`, `get_boolean_value`, `getBooleanValue`, `flagEnabled`, ...).
- `eos scaffold flags`: `tests/test_flags.py` checks defaults, env overrides, stable rollout and the unknown-flag default.
- Review: new flag has type, owner, expiry and a removal issue; tests cover both paths.

## Sources
- Pete Hodgson, Feature Toggles (aka Feature Flags), martinfowler.com: https://martinfowler.com/articles/feature-toggles.html
- OpenFeature introduction: https://openfeature.dev/docs/reference/intro · Providers: https://openfeature.dev/docs/reference/concepts/provider · Hooks: https://openfeature.dev/docs/reference/concepts/hooks
- OpenFeature Python SDK: https://openfeature.dev/docs/reference/technologies/server/python · Node.js SDK: https://openfeature.dev/docs/reference/technologies/server/javascript/
- OpenTelemetry semantic conventions, feature flag events: https://opentelemetry.io/docs/specs/semconv/feature-flags/feature-flags-logs/
