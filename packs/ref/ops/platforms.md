---
id: ops/platforms
title: Where to run it (PaaS vs containers on VMs vs Kubernetes vs serverless), health checks and probes, container image hygiene
area: ops
read_when: choosing a hosting platform, someone proposes Kubernetes, writing a Dockerfile or health check, configuring liveness/readiness/startup probes, moving off a PaaS
verified: 2026-10-10
revisit_days: 180
sources: ["https://kubernetes.io/docs/concepts/overview/", "https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/", "https://github.com/hadolint/hadolint", "https://docs.docker.com/build/building/secrets/", "https://sre.google/workbook/canarying-releases/"]
---
# Where to run it: platforms, health checks and images

Pick the least platform that meets your needs. Every layer you run yourself (cluster, ingress, certificates, node upgrades) is on-call work that does not ship features. Cost estimating is in `architecture/cost`; growth stages in `architecture/scaling-stages`.

## Decision guide

**1. Default ladder for a solo developer or small team.**
| Option | Fits when | You still own |
|---|---|---|
| PaaS (Vercel, Render, Fly.io, Railway, Heroku-style, Cloud Run, App Runner) | web apps and APIs, previews per PR, small team, no platform engineer | app, data, config, alerts, cost limits |
| Managed serverless functions | spiky or low traffic, event handlers, cron | cold starts, time limits, vendor APIs |
| Containers on one or a few VMs (Docker Compose, Kamal-style tools) | steady load, predictable bills, data residency needs a specific provider or region, PaaS limits hit | OS patches, TLS, backups, deploy tooling, monitoring the box |
| Managed Kubernetes (EKS, GKE, AKS, others) | many services, a team that can run it, needs a PaaS cannot meet (custom networking, operators, GPU scheduling, multi-tenant) | cluster upgrades, add-ons, RBAC, networking, cost control |
Use a managed database whatever you pick for compute, unless you have a tested restore and someone to run it (`data/postgres-operations`).

**2. Kubernetes is a toolkit, not a product.** In its own docs: "not a traditional, all-inclusive PaaS"; it does not build or deploy source code, and does not provide middleware, databases, caches or storage as built-in services; logging, monitoring and alerting are pluggable choices. You assemble CI/CD, ingress, certificates, secrets handling (Secrets are unencrypted in etcd by default, `ops/runtime-config`), observability and upgrades yourself. Choose it for a concrete need, not for scale you expect later; moving from a container on a PaaS to Kubernetes is easier when the app is already twelve-factor and containerised.

**3. Keep the app portable whatever the platform.** Config from the environment, logs to stdout as JSON, stateless processes with state in managed services, graceful shutdown on SIGTERM (finish in-flight requests, flush telemetry), one artefact promoted through environments. That keeps the exit door open when prices, limits or residency rules change.

**4. Health endpoints: liveness vs readiness vs startup** (Kubernetes semantics; most PaaS health checks behave like readiness).
- **Liveness** (`/healthz`): "is this process stuck?" Cheap, no dependency calls. The kubelet restarts the container when it fails; Kubernetes warns that wrong liveness probes can cause cascading failures (restarts under high load, more load on the remaining pods).
- **Readiness** (`/readyz`): "can I take traffic now?" Checks what the instance needs (database reachable, migrations applied), each with a short timeout; failing removes the instance from load balancing without restarting it.
- **Startup**: for slow starters; it holds off the other probes until the app has started.
- Do not put a third-party API (payment provider, mobile money) in readiness: its outage would take your whole fleet out of rotation. Degrade that feature instead (`architecture/resilience`).
- `eos scaffold docker-python` ships `health.py` with both endpoints (2-second check timeout) and tests.

**5. Container images.**
- Pin base images by version (and digest where your update bot can refresh it); slim or distroless bases; multi-stage builds so compilers stay out of runtime images.
- Run as a non-root user (`USER 10001` in the eos template); read-only filesystem where possible.
- Build-time secrets via secret mounts, never `ARG` or `ENV` (Docker's docs: they persist in the image).
- Lint with hadolint (`eos scaffold docker-lint`: checksummed binary, no third-party action, fails on warnings); scan images for CVEs in CI (`security/supply-chain`).
- Rebuild regularly to pick up base-image patches even when your code has not changed.

**6. Deploys on any platform** follow `ops/deploy-strategies`: health-gated rollout, keep the previous release to roll back to, and migrations that work with both versions (`data/migrations`).

## Anti-patterns
- Kubernetes for one app and one developer "because we will scale"; a self-run cluster nobody upgrades.
- Liveness probes that call the database or a payment API; no readiness check at all.
- Images running as root, `latest` tags, secrets in `ENV`, build tools in the runtime image.
- Platform-specific code paths scattered through the app, making a move expensive.

## Checks
- `eos scaffold docker-python`: Dockerfile (non-root), `health.py`, `test_health.py` (liveness never touches dependencies; readiness times out and returns 503).
- `eos scaffold docker-lint`: hadolint config + container workflow (lint rendered Dockerfile, build without push). Lanes: hadolint runs in risky and `--full` checks when installed.
- Review: platform choice recorded in an ADR with the reason and the exit plan.

## Sources
- Kubernetes, Overview (what Kubernetes is not): https://kubernetes.io/docs/concepts/overview/
- Kubernetes, Liveness, Readiness, and Startup Probes: https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/
- hadolint: https://github.com/hadolint/hadolint
- Docker, Build secrets: https://docs.docker.com/build/building/secrets/
- Google SRE Workbook, Canarying Releases: https://sre.google/workbook/canarying-releases/
