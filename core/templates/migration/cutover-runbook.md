# Cutover runbook: <name>

- **When:** <date, time, time zone>  ·  **Decision owner (go/no-go):** <name>  ·  **Time box for the decision:** <minutes>
- **People:** <on-call, DB, product, support>  ·  **Channel:** <where updates go>

## Preconditions (all true or no go)
- [ ] Parity report green for every slice in scope
- [ ] Backup taken and restore tested on YYYY-MM-DD
- [ ] Rollback runbook rehearsed in staging on YYYY-MM-DD (took N minutes)
- [ ] Dashboards and alerts for the new path are live
- [ ] Users/support informed

## Steps (exact commands; owner per step)
| # | Time | Step | Command / action | Owner | Check |
|---|---|---|---|---|---|
| 1 | T-0 | freeze writes / enable maintenance mode (if needed) | | | |
| 2 | | flip flag to new path | | | |
| 3 | | verify | <queries, dashboard links> | | |

## Go / no-go criteria (after step 3)
- Error rate ≤ <x>, p95 latency ≤ <y>, mismatch = 0, business KPI within <z> of baseline.
- Not met within the time box → run the rollback runbook. No heroics.
