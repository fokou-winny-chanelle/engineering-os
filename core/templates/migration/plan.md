# Migration plan: <name>

- **Kind:** refactor | upgrade | re-platform | incremental rewrite (strangler fig)
- **Why (link the ADR):** docs/adr/NNNN-...
- **Owner:** <name>  ·  **Started:** YYYY-MM-DD  ·  **Target date:** <date or "none">
- **Seam:** <proxy route / facade module / interface where old and new are switched>
- **Rollback window:** <how long the old path stays deployable after cutover>

## Safety net (before any change)
- [ ] Characterization / golden-master tests for the behaviour being moved: `<path>`
- [ ] Known bugs pinned as "current behaviour" with tickets
- [ ] Baseline metrics captured (error rate, latency p95, business KPI)

## Slices (thin, reversible, ordered by risk: read-only and low traffic first, money last)
| # | Slice | Parity criteria ("equal" means…) | Flag | Data touched | Rollback step | Status |
|---|---|---|---|---|---|---|
| 1 | <e.g. GET /invoices> | same JSON ignoring key order; amounts exact | `mig_invoices_read` | none | flag off | planned |

Status values: planned → shadow (dual run) → canary (x%) → live → old removed.

## Progress log (one line per step; newest last)
- YYYY-MM-DD: plan written
