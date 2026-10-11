// Fixtures for core/scaffold/analytics/semgrep-analytics.yml (semgrep --test). Not executed.
import posthog from "posthog-js";
import mixpanel from "mixpanel-browser";
import { getAnalytics, logEvent } from "firebase/analytics";

declare function gtag(...args: unknown[]): void;
declare const analytics: { track: (...a: unknown[]) => void; identify: (...a: unknown[]) => void };

export function onSignup(user: { id: string; email: string; phoneNumber: string }, plan: string) {
  // ruleid: eos-js-analytics-pii-property, eos-js-analytics-pii-value
  posthog.capture("Account Created", { email: user.email, plan });
  // ruleid: eos-js-analytics-pii-property
  analytics.track("Order Completed", { phoneNumber: "redacted", total: 1 });
  // ruleid: eos-js-analytics-pii-property
  mixpanel.people.set({ $email: "x", plan });
  // ruleid: eos-js-analytics-pii-property
  gtag("event", "sign_up", { first_name: "x" });
  // ruleid: eos-js-analytics-pii-property
  logEvent(getAnalytics(), "purchase", { national_id: "x" });
  // ruleid: eos-js-analytics-pii-value
  posthog.identify(user.email);
  // ruleid: eos-js-analytics-pii-value
  analytics.identify(user.id, { contact: user.phoneNumber });
  // ok: eos-js-analytics-pii-property
  posthog.capture("Account Created", { plan, country: "CM" });
  // ok: eos-js-analytics-pii-value
  posthog.identify(user.id);
  // ok: eos-js-analytics-pii-property
  const form = { email: user.email };
  return form;
}
