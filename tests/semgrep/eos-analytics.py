# Fixtures for core/scaffold/analytics/semgrep-analytics.yml (semgrep --test). Not executed.
import posthog
from mixpanel import Mixpanel
from segment import analytics

mp = Mixpanel("token")


def signup(user, plan_name: str) -> None:
    # ruleid: eos-analytics-pii-property
    posthog.capture(user.id, "Account Created", {"email": user.contact, "plan": plan_name})
    # ruleid: eos-analytics-pii-property
    analytics.track(user.id, "Order Completed", properties={"phone_number": user.msisdn_masked})
    # ruleid: eos-analytics-pii-property
    analytics.identify(user.id, {"date_of_birth": user.birthday})
    # ruleid: eos-analytics-pii-value
    analytics.identify(user.email, {"plan": plan_name})
    # ruleid: eos-analytics-pii-value
    posthog.capture(distinct_id=user.phone, event="Login Succeeded")
    # ruleid: eos-analytics-pii-value
    posthog.capture(user.id, "Profile Updated", {"contact": user.email})
    # ok: eos-analytics-pii-property
    posthog.capture(user.id, "Account Created", {"plan": plan_name, "country": "CM"})
    # ok: eos-analytics-pii-value
    analytics.identify(user.id, {"plan": plan_name, "signup_channel": "ussd"})
    # ok: eos-analytics-pii-property
    record = {"email": user.email}
    # ok: eos-analytics-pii-value
    mp.track(user.id, "Plan Changed", {"from": "free", "to": plan_name})
    print(record)
