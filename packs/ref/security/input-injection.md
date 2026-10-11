---
id: security/input-injection
title: Input handling and injection (SQL, XSS, SSRF, uploads, deserialization, commands)
area: security
read_when: building queries, rendering user content, fetching user-supplied URLs, accepting file uploads, parsing XML/YAML/pickle, or shelling out
verified: 2026-10-10
revisit_days: 365
sources: ["https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html", "https://web.dev/articles/strict-csp", "https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API", "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html", "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html", "https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html", "https://docs.astral.sh/ruff/rules/#flake8-bandit-s"]
---
# Input handling and injection

Injection is A05 in the OWASP Top 10:2025. The fix is almost always the same idea: **keep data and code in separate channels** (parameters, not string building), and validate input against an allow-list at the boundary. Validation alone is not a defence against injection; correct encoding for the destination is.

## Decision guide

**By sink:**

| Sink | Do | Never | Automated check |
|---|---|---|---|
| SQL | parameterized queries / ORM query builders; allow-list identifiers (sort column, table) from a fixed map | f-strings, `+`, template literals into SQL; `raw()` with user input | ruff `S608`; semgrep `eos-js-sql-template-literal` |
| HTML (XSS) | framework auto-escaping (React, Jinja2 autoescape, Django templates); sanitize rich text with a maintained sanitizer (DOMPurify, nh3/bleach) | `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, `|safe`, `mark_safe` on user data | semgrep `eos-react-dangerously-set-inner-html` (review each hit) |
| Browser defence in depth | **strict CSP**: `script-src 'nonce-{random}' 'strict-dynamic'; object-src 'none'; base-uri 'none'` (web.dev); Trusted Types for DOM sinks where supported | `unsafe-inline` + host allow-lists as the only CSP | CSP header test; report-only first |
| Outbound HTTP to user-supplied URL (SSRF, API7) | allow-list of hosts/schemes; resolve DNS and reject private, loopback, link-local (169.254.0.0/16, fd00::/8…) after resolution; disable or re-check redirects; separate egress proxy | fetch any URL from a webhook config, image URL, PDF renderer, or LLM tool without checks | test with `http://169.254.169.254/`, `http://localhost`, DNS-rebinding hostnames |
| Cloud metadata | AWS: require IMDSv2 (session-token, "session-oriented") and disable IMDSv1; similar hardening on other clouds | leaving v1 enabled on instances that fetch URLs | IaC policy (infra pack) |
| OS commands | library calls instead of shelling out; `subprocess.run([...], shell=False)` with a fixed binary | `shell=True`, `os.system`, `child_process.exec` with user input | ruff `S602`/`S605`; semgrep |
| Deserialization | JSON with schema validation; `yaml.safe_load`; signed data if it must round-trip | `pickle`/`marshal`/`yaml.load`/Java native serialization on untrusted data | ruff `S301`, `S506` |
| XML | `defusedxml` (Python), disable DTDs/external entities | default parsers on untrusted XML (XXE) | ruff `S314`–`S320` |
| File paths | map ids to server-chosen paths; `resolve()` and check it stays under the base dir | joining user filenames into paths (`../`) | test with `../../etc/passwd` |
| Templates | render user data as variables | building a template string from user input (SSTI) | review |

**File uploads (OWASP File Upload cheat sheet):** allow-list extensions **and** verify content (magic bytes / re-encode images); never trust `Content-Type`; enforce size limits at the proxy and app; generate a new random filename; store outside the web root (object storage, private bucket) and serve via signed short-lived URLs with `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`; scan for malware where users share files; strip image metadata (EXIF GPS) for privacy.

**Validation at the boundary:** parse into typed schemas (Pydantic, Zod, Bean Validation) with length, range and format limits; reject unknown fields on write endpoints (also prevents mass assignment, `security/authorization`); canonicalize before validating (Unicode normalization, URL decoding once).

**LLM output is untrusted input** to whatever consumes it (OWASP LLM05 Improper Output Handling): treat model output going into SQL, HTML, shell or URLs exactly like user input. See `security/llm-agent-security`.

## Anti-patterns
- "We escape quotes" or blocklists of `<script>` instead of parameterization/encoding.
- Sanitizing on input and then concatenating into a different context (HTML-escaped data put into SQL or a URL).
- SSRF check on the hostname string but fetching after a new DNS lookup (rebinding) or following redirects to internal hosts.
- Accepting uploads into `public/` with the original filename.
- Disabling ruff `S` rules file-wide to silence one finding (use a targeted `# noqa: S608` with a reason).

## Checks
- [ ] ruff with `S` selected passes (the Python stack pack enables it; it is the maintained re-implementation of bandit's checks).
- [ ] `semgrep --config .semgrep/eos-security.yml` passes or each hit is triaged (`eos scaffold security`).
- [ ] Tests per injection-prone endpoint: SQL metacharacters, `<script>`/event-handler payloads rendered escaped, SSRF to metadata/localhost rejected, path traversal rejected, oversize and wrong-type uploads rejected.
- [ ] CSP header present (strict/nonce-based) and verified in an integration test or ZAP baseline.
- [ ] IMDSv2 required on cloud instances (IaC check).

## Sources
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- https://web.dev/articles/strict-csp (nonce/hash-based strict CSP)
- https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API
- https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html (IMDSv2 session-oriented)
- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html
- https://docs.astral.sh/ruff/rules/#flake8-bandit-s (ruff `S` rules derived from bandit)
