---
id: ops/runtime-config
title: Configuration and secrets at runtime (twelve-factor config, validation at startup, env vs files vs secret managers, Kubernetes ConfigMaps and Secrets, rotation)
area: ops
read_when: adding a setting or environment variable, wiring secrets into a container or platform, a config change broke production, setting up per-environment config, rotating a credential without downtime
verified: 2026-10-10
revisit_days: 180
sources: ["https://12factor.net/config", "https://kubernetes.io/docs/concepts/configuration/configmap/", "https://kubernetes.io/docs/concepts/configuration/secret/", "https://sre.google/workbook/canarying-releases/", "https://vercel.com/docs/deployments/environments", "https://docs.docker.com/build/building/secrets/"]
---
# Configuration and secrets at runtime

Config is everything that changes between deploys of the same code: URLs, credentials, feature defaults, limits. Code stays the same from preview to production; config does not. How to store, scan for and rotate secrets is in `security/secrets-keys`; this ref is about getting config into a running process safely.

## Decision guide

**1. Strict separation of config from code** (twelve-factor). The litmus test: could you open-source the repository right now without leaking a credential? Per-deploy values (hostnames, credentials, provider modes like sandbox vs live) come from the environment, not from constants or a committed `settings.prod.py`.

**2. One typed settings object, validated at startup.**
- Load every setting once into a typed object (pydantic-settings in Python, a zod schema in TypeScript); fail fast with a clear message naming the missing or invalid key. A process that starts with a wrong config is worse than one that refuses to start.
- Defaults only for safe, non-secret values (log level, page size). No default for credentials or for "live" payment modes.
- Never print the settings object or the environment; log which keys are set, not their values (`eos-log-secret` rule).
- Commit `.env.example` with every key and a fake value (`eos scaffold compose`); keep real `.env` files out of git (eos's gitignore and gitleaks hooks).

**3. Where secrets live, by platform.**
| Platform | Non-secret config | Secrets |
|---|---|---|
| PaaS (Vercel, Render, Fly, Railway, Heroku-style) | environment variables per environment | the platform's encrypted env vars or secret store, scoped per environment |
| Containers on a VM | env file outside the image, root-only | secret manager fetched at start, or env injected by the orchestrator |
| Kubernetes | ConfigMap | Secret, with encryption at rest enabled and RBAC limiting reads, or an external secret store |
| CI/CD | workflow variables | environment secrets on protected environments; OIDC to the cloud instead of long-lived keys |
Kubernetes facts to remember: a ConfigMap provides no secrecy or encryption and holds at most 1 MiB; Secrets are stored unencrypted in etcd by default, anyone with API access can read them, and anyone who can create a pod in the namespace can mount them. The Kubernetes docs list the minimum: encryption at rest, least-privilege RBAC, per-container access, consider external stores.

**4. Never bake config into artefacts.** No secrets in Docker images (Docker's docs: build arguments and environment variables persist in the final image; use secret mounts for build-time secrets), in client bundles (`NEXT_PUBLIC_*` and Expo public vars are public by design), or in mobile apps. Build once, configure per environment, so the artefact you tested is the one you ship.

**5. Config changes are deploys.** The SRE Workbook counts configuration pushes among the most common incident triggers. Treat them like code: reviewed in a PR or an audited change, rolled out gradually where possible (flags, `ops/feature-flags`), and with a known way back (previous value recorded). Mark config and flag changes on dashboards.

**6. Rotation without downtime.**
- Support two valid credentials at once: add the new one, deploy or reload, switch traffic, then revoke the old one. Webhook signing secrets and API keys of payment providers usually allow this overlap; check each provider.
- Prefer short-lived credentials (cloud IAM roles, OIDC, database IAM auth) over static passwords where the platform offers them.
- Processes read secrets at start; rotating means a rolling restart, or a reload signal if your app supports it. Know which one your runbook needs.

**7. Per-environment hygiene.** Separate credentials per environment (preview, staging, production) and per service; sandbox keys for payment and mobile-money providers outside production. A preview build must never see production secrets.

## Anti-patterns
- `if ENV == "production":` branches scattered through the code instead of config values.
- Secrets in images, in `NEXT_PUBLIC_` variables, in committed `.env` files or in CI logs.
- Settings read lazily deep in the code, so a missing key fails on the first payment instead of at startup.
- One shared admin credential for all environments and services; rotation that needs a maintenance window.
- Treating Kubernetes Secrets as encrypted because the values are base64.

## Checks
- eos pre-commit: gitleaks on staged changes; `.env*` ignored except `.env.example`.
- `.semgrep/eos-ops.yml` (`eos scaffold ops`): secrets and personal data in log calls.
- `eos scaffold iac`: `.gitignore` keeps state and `*.tfvars` (often secret) out of git; checkov reviews Kubernetes manifests.
- Review: new setting is typed, validated at startup, documented in `.env.example`, and scoped per environment.

## Sources
- The Twelve-Factor App, III. Config: https://12factor.net/config
- Kubernetes, ConfigMaps: https://kubernetes.io/docs/concepts/configuration/configmap/ · Secrets: https://kubernetes.io/docs/concepts/configuration/secret/
- Google SRE Workbook, Canarying Releases (changes as incident triggers): https://sre.google/workbook/canarying-releases/
- Vercel, Environments (per-environment variables): https://vercel.com/docs/deployments/environments
- Docker, Build secrets: https://docs.docker.com/build/building/secrets/
