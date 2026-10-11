---
id: release
title: Release & deployment
kind: phase
mode: both
when: preparing a release, versioning, changelog, feature flags or rollout
description: Use when preparing or doing a release: versioning, changelog, feature flags, migration order, rollout, rollback.
globs: ["**/CHANGELOG*", "**/release-please*", "**/.releaserc*", "**/.changeset/**", "**/flags/**", "**/feature-flags*"]
next: [operations]
---
# Release & deployment

## Entry
Merged, reviewed changes with a green main branch. Migrations and contract changes are known. A release owner is named (a human).

## Standards
1. Small and frequent. Trunk-based development with short-lived branches. Incomplete features go behind flags. Deployment and release are separate events: deploy dark, then turn on the flag.
2. Versioning. Use SemVer for libraries and APIs, and date or SemVer for apps. Conventional commits drive the changelog (release-please, semantic-release or changesets). The changelog is written for humans: what changed for users and operators.
3. Build once, promote. The same artefact (image digest) moves through staging and then production. It is signed, has provenance/attestation and an attached SBOM.
4. Order of operations for data:
   - Deploy the expand migration first.
   - Deploy code that works with both old and new schemas.
   - Run the backfill.
   - Switch reads and writes.
   - Contract in a later release.
   Never couple a destructive migration with a code deploy.
5. Progressive rollout. Use canary or percentage rollout (e.g. 5%→25%→100%) with automated guardrails: error rate, latency p95, and business KPIs such as payment success rate. Watch it for a defined time between steps.
6. Rollback is a button. Document and test the rollback (redeploy the previous digest, or turn the flag off). Data changes need a forward fix plan.
7. Release checklist and freeze rules.
   - No Friday-evening or holiday releases for money flows unless agreed.
   - On-call is aware of the release.
   - Status page/comms are prepared for user-visible changes.
8. AI role. The AI drafts release notes, checklists and rollout plans. Only the pipeline or a human deploys to production.

## Deliverables
- Version tag, changelog, release notes (user-facing and ops-facing), rollout plan with guardrail thresholds, rollback steps, migration order. Tags and changelog can come from release-please (`eos scaffold release`).

## Automated checks
- CI on the release commit: full test suite, build, image scan, SBOM and attestation.
- Smoke tests after each rollout step; automated rollback when guardrails are breached (if the platform supports it).

## Deep references
Read one only when doing that work (`.eos/packs/ref/<id>.md`): `ops/deploy-strategies` (canary, blue-green, rollback, approvals, previews) · `ops/feature-flags` (OpenFeature, kill switches, cleanup) · `security/supply-chain` (provenance, SBOM) · `testing/mobile-qa` (release test checklist, bug bash).

## Exit checklist (Definition of Done)
- [ ] The artefact is signed/attested, and the same digest went through staging.
- [ ] Migrations ran in the safe order, and smoke tests passed in production.
- [ ] Guardrail metrics stayed healthy through the full rollout window.
- [ ] Changelog and release notes are published, flags are cleaned up or scheduled for removal.
- [ ] The release owner signed off.

## Handoff → operations
Pass the release record (version, digest, flags, dashboards to watch, rollback steps) to on-call.

## Stop & escalate
Stop the rollout on any guardrail breach, unexpected migration lock or error spike. Roll back first and investigate later.
