# Rollback runbook: <name>

- **Triggers:** error rate > <x> · p95 > <y> · parity mismatch > 0 on money · KPI drop > <z> · decision owner says so
- **Who decides:** <name>  ·  **Target time to roll back:** <minutes> (rehearsed: N minutes on YYYY-MM-DD)

## Steps
1. Route traffic back to the old path: <flag off / route change command>.
2. Stop new-path writers: <command>.
3. Reconcile writes made on the new path since cutover: <script/query>; owner <name>.
4. Verify: <queries, dashboards>; announce in <channel>.

## After
- Incident note + what changes before the next attempt (link).
- Parity report updated; plan status reset for the affected slices.
