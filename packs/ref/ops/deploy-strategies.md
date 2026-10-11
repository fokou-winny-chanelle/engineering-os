---
id: ops/deploy-strategies
title: Deployment strategies (rolling, blue-green, canary, progressive delivery), rollback, release safety, change management and preview environments
area: ops
read_when: choosing how to deploy, setting up a production deploy workflow or approvals, planning a risky release or a rollback, adding preview environments, deciding who may change production
verified: 2026-10-10
revisit_days: 180
sources: ["https://martinfowler.com/bliki/BlueGreenDeployment.html", "https://martinfowler.com/bliki/CanaryRelease.html", "https://sre.google/workbook/canarying-releases/", "https://argo-rollouts.readthedocs.io/en/stable/", "https://docs.flagger.app/", "https://dora.dev/guides/dora-metrics-four-keys/", "https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments", "https://vercel.com/docs/deployments/environments"]
---
# Deployment strategies and release safety

In Google's experience most incidents are triggered by changes: binary or configuration pushes (SRE Workbook). Safe delivery is not fewer changes; it is small changes, exposed gradually, with a fast way back.

## Decision guide

**1. Separate deploy from release.** Deploy = new code is running. Release = users get the behaviour. Feature flags (`ops/feature-flags`) let you deploy dark, release to 1% then 100%, and turn a feature off without a deploy. Config and flag changes are changes too: review and roll them out like code.

**2. Pick the simplest strategy that gives you a fast rollback.**
| Strategy | How | Rollback | Cost / caveat | Fits |
|---|---|---|---|---|
| Rolling (platform default) | replace instances a few at a time behind readiness checks | redeploy previous image | old and new run side by side briefly | most PaaS and Kubernetes apps |
| Blue-green | two identical production environments; switch the router to the new one | switch the router back | double the resources during the switch; handle transactions made on the new side | releases needing instant rollback, simple stacks |
| Canary | send a small share of traffic or users to the new version, compare with the rest, then widen | send all traffic back | needs per-version metrics; metric intervals no longer than the canary | services with enough traffic to compare |
| Progressive delivery | automate the canary: shift traffic in steps while analysing metrics, roll back automatically on failure | automatic | Argo Rollouts / Flagger on Kubernetes, or the platform's built-in traffic splitting | teams on Kubernetes with good metrics |
| Flag rollout | deploy everywhere, release by flag percentage | flag off | flag debt; only covers flagged code | small teams without traffic-splitting infrastructure |
For a solo developer on a PaaS: rolling deploys with readiness checks + flags for risky features + one-command rollback covers most needs.

**3. Canary evaluation, simply.** Compare canary vs control on the SLO signals (error ratio, p95 latency) and business signals (payments succeeding). Break metrics down by version label; a canary at 5% with a 20% error rate shows up as only 1% overall (Workbook example). Watch at least as long as one unit of work (a batch job, a payment callback round trip).

**4. Rollback must be boring.**
- Keep the previous artefact (immutable image tags or digests, never `latest`) and a documented one-command rollback in the runbook.
- Database changes are the usual blocker: expand → migrate → contract (`data/migrations`), so the previous version still works against the new schema. A release that needs a destructive migration is a one-way door: plan it separately.
- Roll back first when a deploy lines up with a symptom; debug afterwards.

**5. Release safety checklist for risky changes** (money, auth, data model, infra):
- Small diff, reviewed, tests and `eos verify` lane passed; a flag or canary step; dashboards open during rollout.
- Deploy in working hours when someone can watch; avoid Friday evening and the day before a holiday unless the change is a fix.
- Know the abort signal (which metric, which threshold) before you start.
- Announce in the team channel; tag the deploy on dashboards.

**6. Change management for small teams: guardrails, not a board.**
- Production deploys only from CI on the main branch; nobody deploys from a laptop.
- GitHub environments: deployment branch rules, required reviewers (up to 6; one approval is enough; "prevent self-review" blocks approving your own run), optional wait timer, environment-scoped secrets. Note GitHub's plan limits: protection rules on private repositories need a paid plan.
- Infrastructure: plan in CI, a human approves and applies (`ops/iac`). Emergency changes are allowed, then written up within a day.
- Track DORA's delivery metrics to see whether safety work helps: deployment frequency, lead time for changes, change fail rate, failed deployment recovery time, deployment rework rate.

**7. Preview environments.** A short-lived environment per pull request (Vercel does this per pushed branch; many PaaS and Kubernetes setups can too) lets reviewers click through changes.
- Use separate, seeded test data and sandbox credentials for payment and mobile-money providers; never production databases or secrets.
- Protect previews (auth or unguessable URLs + `noindex`), tear them down on merge, cap how many run (cost).
- Environment variables per environment; production secrets are never available to preview builds or to workflows triggered from forks.

## Anti-patterns
- Big-bang releases bundling weeks of changes; deploying and releasing in the same step with no flag.
- `latest` image tags; rollbacks that need a rebuild; migrations that break the previous version.
- Manual production deploys from laptops; shared admin credentials in CI.
- Canary judged by eye on a global error graph; previews wired to production data.

## Checks
- `eos verify` lanes: risky paths get extra checks before merge; CI runs the full suite.
- `eos scaffold docker-python` / `docker-node`: `container.yml` builds the image in PRs; `eos scaffold iac`: plan-only workflow.
- Review: deploy workflow uses a protected environment; rollback command is in the runbook; migrations follow expand/contract.

## Sources
- Martin Fowler, BlueGreenDeployment: https://martinfowler.com/bliki/BlueGreenDeployment.html · Danilo Sato, CanaryRelease: https://martinfowler.com/bliki/CanaryRelease.html
- Google SRE Workbook, Canarying Releases: https://sre.google/workbook/canarying-releases/
- Argo Rollouts: https://argo-rollouts.readthedocs.io/en/stable/ · Flagger: https://docs.flagger.app/
- DORA software delivery metrics: https://dora.dev/guides/dora-metrics-four-keys/
- GitHub, Managing environments for deployment: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- Vercel, Environments (preview deployments): https://vercel.com/docs/deployments/environments
