---
id: infra-devops
title: Infrastructure, DevOps & IaC
kind: phase
mode: files
when: editing Dockerfiles, CI/CD, IaC, Kubernetes or environment config
description: Use when editing infrastructure or delivery - Dockerfiles, compose, CI/CD workflows, Terraform/OpenTofu, Kubernetes/Helm, environments. Immutable, least-privilege, reproducible, plan-before-apply.
globs: ["**/Dockerfile*", "**/*.dockerfile", "**/compose*.yml", "**/compose*.yaml", "**/docker-compose*", "**/*.tf", "**/*.tfvars", "**/*.hcl", ".github/workflows/**", "**/k8s/**", "**/helm/**", "**/charts/**", "infra/**", "deploy/**", "**/.gitlab-ci.yml"]
next: [security, release, operations]
---
# Infrastructure, DevOps & IaC

## Entry
Architecture and ADRs define the environments and hosting. The change is described as a plan.

## Standards
1. Everything as code. Infra, CI and config are in git and reviewed. No click-ops on shared environments; if an emergency forces it, back-port it to code within 24 h.
2. Plan before apply. Run `terraform/tofu plan` (or `helm diff`, `kubectl diff`) on every PR and post the output. The AI never runs apply, deploy or destroy on shared environments. A human or the pipeline does.
3. Containers.
   - Multi-stage builds, minimal or distroless base images pinned by digest, and a non-root user.
   - No secrets in layers.
   - A `.dockerignore` file.
   - A healthcheck.
   - One process per container.
   - Reproducible builds.
4. CI/CD.
   - Pin actions by commit SHA (Renovate keeps them updated).
   - `permissions:` least privilege, set per job.
   - Use OIDC to the cloud instead of long-lived keys.
   - Cache dependencies; separate jobs per stack with path filters.
   - Protected branches with required checks.
5. Environments. dev → staging → prod, all from the same artefact (build once, promote). Config differs only through env vars or secret refs. Production access is just-in-time and audited.
6. Least privilege. Use a separate service account per workload, scoped network policies or security groups, and no wildcard IAM. Store state files remotely with locking and encryption.
7. Supply chain.
   - Lockfiles are committed.
   - Generate an SBOM.
   - Provenance/attestation for release artefacts (SLSA level as decided).
   - Image scanning.
8. Cost and limits. Every workload has resource requests and limits plus autoscaling bounds. Tag resources with owner, env and cost centre. Set budgets and alerts.
9. Disaster recovery. Automate backups, run a restore test at a set cadence, and write RPO/RTO next to the runbook.

## Deliverables
- IaC/CI changes, a plan output in the PR, updated env docs, and a runbook update if operations change. Starters: `eos scaffold compose` (local Postgres/Redis, `.env.example`), `eos scaffold docker-python|docker-node`.

## Automated checks
- IaC fmt/validate/lint (e.g. tflint), policy and security scan (e.g. checkov or trivy config), actionlint for workflows, hadolint for Dockerfiles.
- Container image scan, plus a secrets scan on every commit.

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `ops/iac` (OpenTofu/Terraform, state, plan review, checkov) · `ops/platforms` (PaaS vs Kubernetes, probes, images) · `ops/runtime-config` (config and secrets at runtime) · `ops/dr-chaos` (backups, DR strategies) · `security/supply-chain` (Actions pinning, SBOM, SLSA) · `security/secrets-keys` (OIDC, rotation) · `data/postgres-operations` (PgBouncer, replicas, backups).

## Exit checklist (Definition of Done)
- [ ] The plan or diff was reviewed, and no unexpected destroy or replace appears.
- [ ] Least privilege holds: no wildcards, no long-lived keys, and actions are pinned.
- [ ] Images are non-root and pinned, and the scans are clean (or exceptions are documented with an expiry).
- [ ] Rollback path documented. Backups and restores are covered.
- [ ] Human approval for any production-affecting change.

## Handoff → security / release / operations
Pass the plan output, the changed environments, the rollback steps and the monitoring changes.

## Stop & escalate
Stop before any apply, deploy, destroy, IAM widening, firewall opening, or production data access. Prepare the change and let a human run it.
