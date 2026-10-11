# Security policy

engineering-os writes guard hooks, CI workflows and MCP configurations into other people's projects and machines, so security reports matter here.

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub: go to the repository's **Security** tab and choose **Report a vulnerability** ([how private reporting works](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

Please include:
- the version (`eos --version`) and your OS;
- what an attacker could do, and the steps to reproduce;
- whether it needs a malicious repository, a malicious MCP server or prompt injection, or local access.

This is a project maintained by one person in their spare time. You can expect an acknowledgement within 7 days and a fix or mitigation plan within 30 days for confirmed issues. Credit is given in the CHANGELOG unless you prefer otherwise.

## In scope

- Guard-hook bypasses: an agent reads secret files, force-pushes or runs a blocked command without a prompt.
- Secrets leaking into generated files, client configs, logs or git.
- The MCP launchers (`eos mcp run`): escaping the Postgres host allow-list or the read-only session, or reaching non-allowed origins with the browser server.
- Generated CI workflows that grant excessive permissions or run untrusted code.
- `eos update` overwriting user-edited files, or vendored content bypassing quarantine.

## Out of scope

- Vulnerabilities in third-party tools that eos installs or configures (report those upstream).
- Behaviour of AI models themselves. The hooks are defence in depth, not a sandbox.

## Supported versions

Only the latest minor release gets security fixes while the project is pre-1.0.
