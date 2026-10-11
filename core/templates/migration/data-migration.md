# Data migration: <name>

Pattern: expand → migrate → contract. Every step backward compatible until the last.

| Step | What | Reversible? | Verify with | Status |
|---|---|---|---|---|
| 1 Expand | add new tables/columns (nullable, no locks: lock_timeout, concurrent indexes) | yes (drop) | schema diff | planned |
| 2 Backfill | batches of N rows, idempotent, resumable (checkpoint: <where>) | yes | row counts, checksums per partition | planned |
| 3 Dual write / sync | outbox or CDC preferred over app dual writes | yes | mismatch counter = 0 | planned |
| 4 Switch reads | behind flag `<flag>` | yes (flag) | parity report | planned |
| 5 Switch writes | behind flag `<flag>` | yes until old data stops updating | invariants (e.g. sum of balances) | planned |
| 6 Contract | remove old columns/tables in a later release | **no**: backup + restore test first | – | planned |

- **Backup before step 6:** <how, where, restore test date>
- **PII / money:** <retention, reconciliation, human reviewer>
