---
id: ops/iac
title: Infrastructure as code (OpenTofu/Terraform, Pulumi), state, modules, plan review, drift and IaC scanning (checkov, Trivy)
area: ops
read_when: creating or changing cloud resources, writing Terraform/OpenTofu or Pulumi code, setting up remote state, reviewing a plan, adding IaC scanning to CI, someone clicked a change in the console
verified: 2026-10-10
revisit_days: 180
sources: ["https://opentofu.org/faq/", "https://github.com/opentofu/opentofu", "https://developer.hashicorp.com/terraform/language/style", "https://www.pulumi.com/docs/iac/concepts/", "https://github.com/pulumi/pulumi", "https://www.checkov.io/", "https://github.com/aquasecurity/tfsec", "https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23"]
---
# Infrastructure as code

If a resource is not in code, you cannot review it, rebuild it after a disaster (`ops/dr-chaos`) or know who changed it. IaC turns infrastructure changes into pull requests with a plan that a human approves.

## Decision guide

**1. Pick a tool.**
| Tool | Language | Licence note | Fits when |
|---|---|---|---|
| OpenTofu | HCL | open source (MPL-2.0), under the Linux Foundation; a Terraform fork made after HashiCorp moved Terraform to the BUSL | default for new HCL work; drop-in for most Terraform code |
| Terraform | HCL | BUSL (source-available) | you depend on HCP Terraform or features OpenTofu lacks; check the licence fits your use |
| Pulumi | Node.js, Python, Go, .NET, Java, YAML | engine Apache-2.0; the hosted Pulumi Cloud is a separate service | team prefers a general-purpose language, tests infra like code |
| Platform config (vercel.json, fly.toml, render.yaml) | YAML/TOML/JSON | n/a | everything lives on one PaaS; still commit it |
Do not migrate a working Terraform setup just for the sake of it; do make the licence choice explicit in an ADR. Check provider and state compatibility in each tool's docs before switching.

**2. Repository layout.** One root module per environment or stack (`infra/envs/staging`, `infra/envs/production`) calling shared modules; small modules with clear inputs and outputs; pin provider versions; no copy-paste between environments.

**3. State is sensitive and shared.** HashiCorp's style guide: never commit state files (they can contain secrets; version control cannot lock them), the `.terraform` directory, saved plan files, or `.tfvars` files with sensitive values; always commit code, the `.terraform.lock.hcl` dependency lock file and a `.gitignore`. Keep state in a remote backend with encryption, locking, versioning and restricted access (only CI and a break-glass role). Back it up like a database.

**4. Workflow: plan in CI, apply after human review.**
- Every PR: `fmt -check`, `validate`, a scanner, and a `plan` posted for review (plan needs read credentials; use OIDC from CI, not stored keys).
- Apply only from the main branch, after approval, through a protected environment (`ops/deploy-strategies`); never from laptops except break-glass, and record it.
- Read the plan for deletes and replacements (`-/+`), especially databases, buckets and DNS; add `prevent_destroy` (Terraform/OpenTofu) or `protect` (Pulumi) on stateful resources.
- An agent may write IaC and run plan; a human applies. Infra changes are the risky lane in eos.

**5. Drift.** Console changes make code lie. Run a scheduled plan (daily or weekly) that alerts when it is not empty; fix by importing the change into code or reverting it. Make console access read-only by default.

**6. Secrets and tags.** No secrets in variables files or code: read them from a secret manager at apply time or let the platform inject them (`ops/runtime-config`), and mark outputs `sensitive`. Tag every resource (owner, environment, service, cost-centre) for cost reports (`ops/capacity-cost`).

**7. Scanning.** Misconfiguration scanners catch public buckets, open security groups, unencrypted disks and privileged pods before apply.
- checkov scans Terraform, CloudFormation, Kubernetes, Helm, ARM templates and Serverless framework files; suppress one finding in code with a reason (`#checkov:skip=CKV_AWS_20:reason`).
- tfsec is now part of Trivy (`trivy config`).
- Supply-chain caution: in March 2026 the `aquasecurity/trivy-action` tags were hijacked and a malicious Trivy release was published (CVE-2026-33634). Run scanners from checksummed binaries or pinned packages, and pin any action by commit SHA (`security/supply-chain`).

## Anti-patterns
- State in git, on a laptop, or in a bucket without locking and versioning.
- `apply` without a reviewed plan; auto-apply on every merge for stateful resources.
- Long-lived cloud admin keys stored as CI secrets instead of OIDC roles.
- Copy-pasted environment folders that slowly diverge; unpinned providers.
- Suppressing scanner findings without a reason, or scanning nothing because "it is just infra".

## Checks
- `eos scaffold iac`: CI workflow (checksummed OpenTofu: `fmt -check`, `init -backend=false`, `validate` per root module; checkov at a pinned version; never applies), `.checkov.yaml`, and an IaC `.gitignore` (state, plans, tfvars).
- `eos verify --full` runs checkov on changed IaC folders when installed; other lanes leave a note (CI runs it).
- Review: plan attached, deletes/replacements explained, stateful resources protected, licence choice in an ADR.

## Sources
- OpenTofu FAQ (why the fork, Linux Foundation): https://opentofu.org/faq/ · licence: https://github.com/opentofu/opentofu
- HashiCorp, Terraform style guide (fmt/validate, .gitignore, lock file): https://developer.hashicorp.com/terraform/language/style
- Pulumi, IaC concepts (languages): https://www.pulumi.com/docs/iac/concepts/ · engine licence: https://github.com/pulumi/pulumi
- Checkov: https://www.checkov.io/
- tfsec (now part of Trivy): https://github.com/aquasecurity/tfsec
- Trivy advisory GHSA-69fq-xp46-6x23 / CVE-2026-33634: https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23
