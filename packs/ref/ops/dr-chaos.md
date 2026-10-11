---
id: ops/dr-chaos
title: Backups and disaster recovery (RPO/RTO, 3-2-1, restore drills, DR strategies) and chaos engineering (when it pays)
area: ops
read_when: setting up backups, choosing RPO/RTO, planning disaster recovery or a second region, scheduling a restore drill or game day, someone proposes chaos experiments
verified: 2026-10-10
revisit_days: 180
sources: ["https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/business-continuity-plan-bcp.html", "https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html", "https://www.cisa.gov/sites/default/files/publications/data_backup_options.pdf", "https://principlesofchaos.org/", "https://docs.aws.amazon.com/fis/latest/userguide/what-is.html"]
---
# Backups, disaster recovery and chaos engineering

A backup you have never restored is a hope. Disaster recovery is the plan, the people and the practice that turn backups into a running service within an agreed time.

## Decision guide

**1. Set RPO and RTO per system first; they decide everything else** (AWS DR whitepaper definitions):
- **RPO** (recovery point objective): the most data, measured in time since the last recovery point, you accept losing. Payments ledger: minutes or zero. Analytics: a day.
- **RTO** (recovery time objective): the longest acceptable delay between the interruption and restored service.
- Write both in the runbook with the owner's sign-off. Smaller numbers cost more (standby capacity, replication, people on call).

**2. Back up by the 3-2-1 rule** (CISA): three copies of important data (one primary, two backups), on two different media or storage types, one copy offsite. In cloud terms:
- Primary database + provider snapshots + an independent copy in another account and region (or another provider), so one compromised account or one deleted project cannot erase everything.
- Make backups immutable or versioned with retention locks where offered (protects against ransomware and mistakes).
- Encrypt backups; keep the keys where a disaster that takes the primary cannot take them too, and test that you can still decrypt.
- PostgreSQL specifics (continuous archiving, PITR, pgBackRest, `pg_dump` limits): `data/postgres-operations`.

**3. Back up more than the database.** Object storage (uploads, invoices), secrets and key material (escrowed safely, `security/secrets-keys`), infrastructure code and state (`ops/iac`), DNS zone, CI/CD config, third-party settings (payment provider webhooks and callback URLs), and the runbooks themselves (not only on the system that failed).

**4. Restore drills: scheduled, timed, written down.**
- Monthly or quarterly: restore the latest backup into an isolated environment, run integrity checks (row counts, latest transaction time, application smoke test), record how long it took, compare with RTO and RPO.
- Rotate who does it, so the knowledge is not in one head. Update the runbook with every surprise.
- Alert when a backup job fails or the newest backup is older than the RPO; monitoring "backup job succeeded" is not enough, check the artefact.

**5. Choose a DR strategy by RTO/RPO and budget** (AWS's four, from cheapest to fastest):
| Strategy | What runs in the recovery site | Typical fit |
|---|---|---|
| Backup and restore | nothing; restore data and rebuild with IaC | most small products; hours of RTO |
| Pilot light | data replicated, core services off or minimal | lower RTO without paying for full capacity |
| Warm standby | a scaled-down but working copy | faster failover, real ongoing cost |
| Multi-site active/active | full capacity in two or more sites | very low RTO; hardest (data consistency, cost) |
Start with backup-and-restore plus IaC that can rebuild everything; move up only when an RTO demands it and you can afford to test it. A failover you have never exercised is unlikely to work.

**6. Chaos engineering: only after the basics.** The Principles of Chaos Engineering: define steady state as a measurable output (your SLIs), hypothesise it holds, introduce real-world events (instance crash, dependency latency, network loss), try to disprove the hypothesis, automate, and minimise blast radius.
- It pays when you have SLOs and dashboards, automated recovery to test (retries, failover, autoscaling, kill switches), and enough traffic that a weakness would bite.
- It does not pay yet when there is one instance, no monitoring, or known unfixed weaknesses: fix those first.
- Small-team version: a quarterly game day in staging. Kill the app process, block the payment provider, fill the disk, expire a certificate; check alerts fire, runbooks work, users see a friendly degraded mode. Managed tools exist (AWS Fault Injection Service runs fault experiments against AWS resources); a script and a timer are enough to start.
- Never run experiments in production without an agreed window, a stop button, and an SLO budget you can afford to spend.

## Anti-patterns
- Backups in the same account and region as production, with the same admin credentials.
- "Backups succeed" alerts and no restore ever tested; restore steps only in one person's head.
- RPO/RTO promised to customers that nobody measured.
- Multi-region active/active for a product with one developer and no tested restore.
- Chaos experiments without monitoring, a hypothesis or a way to stop.

## Checks
- Restore drill log (manual): date, backup used, time to restore, data loss window, issues found; compared with RPO/RTO.
- Alerts: backup age > RPO, backup job failed, replication lag (`data/postgres-operations`).
- `eos scaffold iac`: infrastructure rebuildable from code (validate in CI).

## Sources
- AWS, Disaster Recovery of Workloads on AWS, recovery objectives: https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/business-continuity-plan-bcp.html · DR options: https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html
- CISA, Data Backup Options (3-2-1 rule): https://www.cisa.gov/sites/default/files/publications/data_backup_options.pdf
- Principles of Chaos Engineering: https://principlesofchaos.org/
- AWS Fault Injection Service: https://docs.aws.amazon.com/fis/latest/userguide/what-is.html
