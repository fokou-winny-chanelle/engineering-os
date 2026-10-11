---
id: ops/opentelemetry
title: Observability with OpenTelemetry (traces, metrics, logs, semantic conventions, sampling, cardinality, correlation IDs, structured logging)
area: ops
read_when: adding tracing, metrics or logging to a service, wiring OpenTelemetry in FastAPI, Flask or Next.js, choosing a sampling rate, naming metrics or labels, writing a log line, debugging a request across services
verified: 2026-10-10
revisit_days: 120
sources: ["https://opentelemetry.io/docs/concepts/sampling/", "https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/", "https://opentelemetry.io/docs/specs/semconv/http/http-spans/", "https://opentelemetry.io/docs/specs/semconv/http/http-metrics/", "https://opentelemetry.io/docs/concepts/signals/logs/", "https://opentelemetry.io/docs/collector/", "https://www.w3.org/TR/trace-context/", "https://nextjs.org/docs/app/guides/open-telemetry", "https://prometheus.io/docs/practices/naming/"]
---
# Observability with OpenTelemetry

OpenTelemetry (OTel) is the vendor-neutral standard for traces, metrics and logs: one SDK in your code, OTLP on the wire, any backend behind it. Changing vendors becomes a config change.

## Decision guide

**1. Wire it once, configure by environment.** `eos scaffold otel-python` (FastAPI/Flask) and `eos scaffold otel-node` (Next.js) add the set-up; every option is a standard variable:
| Variable | Use |
|---|---|
| `OTEL_SERVICE_NAME` | service name on every signal (becomes the Prometheus `job` label) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | where to send, e.g. `http://collector:4318` (HTTP; 4317 is gRPC). Unset in the templates = no export, logs still carry trace IDs |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment.name=production,service.version=1.4.2` |
| `OTEL_TRACES_SAMPLER` / `_ARG` | default `parentbased_always_on`; `parentbased_traceidratio` + `0.1` keeps 10% of new traces |
| `OTEL_SDK_DISABLED=true` | switch it all off (tests, local) |
Next.js: `instrumentation.ts` calls `register()`; import the Node SDK only when `process.env.NEXT_RUNTIME === 'nodejs'` (it does not run on the edge runtime). `@vercel/otel` is the alternative that also covers edge.

**2. Send to a Collector, not straight to a vendor**, once you have more than one service. The Collector receives, processes (batching, redaction, tail sampling) and exports to one or more backends. A single small service can export directly.

**3. Traces: let instrumentation do the boring part.** Framework instrumentation creates a SERVER span per request named `{method} {route}` (`GET /items/{item_id}`), with `http.request.method`, `http.route`, `http.response.status_code`. Add custom spans only around work that matters (a payment call, a queue publish) and attributes that help debugging (`payment.provider`, an internal order ID). Exclude health probes (the templates do).

**4. Correlation IDs: use the trace ID.** W3C Trace Context carries it between services in `traceparent: 00-<32-hex trace id>-<16-hex span id>-<flags>`; instrumented HTTP clients and servers propagate it automatically. Put `trace_id` and `span_id` in every log line (the templates do) and show the trace ID on error pages so a user or support agent can quote it. Do not invent a second request-ID scheme unless a partner requires one; if so, log both.

**5. Structured logs.** One JSON object per line to stdout: UTC time, level, message, logger, trace_id, span_id, plus fields (`payment_id`, `user_id`). Messages are constant strings ("payment created"); variable data goes in fields, so you can search and count. Never log secrets, tokens, full request bodies or personal data (phone numbers, emails): log IDs. The `eos-log-secret`, `eos-log-personal-data` and `eos-log-request-body` Semgrep rules catch the obvious cases; the formatters redact secret-named fields as a seatbelt.

**6. Metrics: RED per service, USE per resource** (`ops/dashboards-alerting`). Prefer the semantic-convention metric `http.server.request.duration` (a histogram in seconds) over hand-made counters; it gives rate, errors (by status) and latency percentiles at once, and the SLO queries in `ops/slo.json` use it.

**7. Cardinality is the cost driver.** Every distinct label combination is a new time series. Never put user IDs, emails, raw URLs, order IDs or error messages in metric labels; use the route template and status code. High-cardinality detail belongs in traces and logs, which you can sample.

**8. Sampling.**
- Head sampling decides at the start of a trace; consistent probability sampling (`traceidratio`) is the common form, and `parentbased_` makes children follow the parent so traces stay complete.
- Tail sampling decides after seeing all or most spans (in the Collector): keep every error and slow trace, a fraction of the rest. Needed when you must not miss errors.
- Start at 100% while traffic is small; lower the ratio when cost or volume demands it. Metrics are not sampled: compute SLOs from metrics, not from sampled traces.

**9. Semantic conventions keep data portable.** Use the standard attribute names (`http.*`, `db.*`, `messaging.*`, `feature_flag.*`) instead of your own; dashboards and backends understand them. Some groups are still marked Development and may change; pin SDK versions and read release notes.

## Anti-patterns
- `logger.info(f"user {email} paid {amount} with token {token}")`: secret, personal data and an unsearchable message in one line.
- A label per user or per URL; a metric per customer.
- Tracing health checks; 100% tail sampling with no budget; computing availability from sampled traces.
- Vendor SDKs sprinkled through the code instead of OTel + OTLP; observability turned on for the first time during an incident.
- Printing to stdout without levels or JSON; logs with local times and no zone.

## Checks
- `eos scaffold otel-python` ships `tests/test_telemetry.py`: request spans use the route template, health probes are not traced, log lines carry the span's trace ID, secret fields are redacted.
- `eos scaffold ops` adds `.semgrep/eos-ops.yml`; the security workflow runs `semgrep scan --config .semgrep/`.
- Review: new metric labels are bounded; new log fields are not secrets or personal data.

## Sources
- OpenTelemetry, Sampling: https://opentelemetry.io/docs/concepts/sampling/ · SDK environment variables: https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/
- OTel semantic conventions, HTTP spans: https://opentelemetry.io/docs/specs/semconv/http/http-spans/ · HTTP metrics: https://opentelemetry.io/docs/specs/semconv/http/http-metrics/
- OTel Logs: https://opentelemetry.io/docs/concepts/signals/logs/ · Collector: https://opentelemetry.io/docs/collector/
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- Next.js, OpenTelemetry: https://nextjs.org/docs/app/guides/open-telemetry
- Prometheus, Metric and label naming (cardinality): https://prometheus.io/docs/practices/naming/
