# Migration playbook: refactor, re-platform, rewrite ("refonte")

Read on demand by the migration pack. Sources are at the end; they were checked on 2026-10-10.

## 1. Choose the smallest change
| Option | What changes | Risk | Use when |
|---|---|---|---|
| Refactor in place | Internal structure only; behaviour stays the same | Low | Code is hard to change but the platform is fine |
| Upgrade | Framework or runtime version | Low to medium | Supported upgrade path exists; go one major at a time |
| Re-platform | Runtime, hosting, DB engine; same behaviour | Medium | Platform is end-of-life, too costly or too slow |
| Incremental rewrite (strangler fig) | Slices replaced behind a seam | Medium | Design no longer fits; can route per slice |
| Big-bang rewrite | Everything at once | High | Almost never: a stated business reason and human approval |

Rewrites from scratch throw away years of bug fixes hidden in old code. That warning dates from 2000 ([Spolsky]) and still applies. If you rewrite, do it slice by slice.

## 2. Safety net first
- **Characterization tests** record what the code does today, not what it should do ([Characterization test]). Use them before touching untested code.
- **Golden master / approval tests:** capture outputs for a wide set of real inputs and diff against the approved file ([ApprovalTests]). Scrub non-deterministic fields (time, ids) first.
- Pin known bugs as "current behaviour" with a ticket link, and fix them in a separate change, so a refactor never hides a behaviour change.
- Where tests are impossible (no seams), add the smallest seam first: extract a function, inject a dependency, or wrap a global.

## 3. Strangler fig
1. Put a seam in front of the old system: an HTTP proxy or router, an API gateway route, a facade module, or a branch-by-abstraction interface inside the code ([Fowler: strangler fig], [Fowler: branch by abstraction], [Azure pattern], [Shopify]).
2. Move one slice behind the seam, compare (§4), flip the flag, then watch.
3. Repeat. The old system shrinks until it can be deleted.

Slice order: read-only before write; low traffic before high; well-understood before obscure; and money last, or with the longest dual run.

## 4. Parity checks
- **Shadow / dual run:** send the same input to old and new, serve the old result, and log any difference ([GitHub Scientist] does this in-process: `use` old, `try` new, compare, publish mismatches).
- **Define "equal" first:** key ordering, float rounding, time zones, ids, whitespace.
- **Track the mismatch rate per slice.** Exit when it is 0, or when every mismatch is explained in `parity.md`.
- **Money:** reconcile totals (old ledger = new ledger) daily during the dual run.

## 5. Flags and rollout
- A flag per slice, off by default; enable it per cohort, then by percentage, with a kill switch ([Fowler: feature toggles], [OpenFeature] for a vendor-neutral API).
- Each flag has an owner and a removal date. Release toggles are short-lived by design.

## 6. Data migration
- **Expand → migrate → contract** (parallel change, [Fowler: parallel change]):
  1. add new columns or tables (backward compatible);
  2. backfill in idempotent, resumable batches;
  3. verify;
  4. switch reads;
  5. switch writes;
  6. remove the old schema in a later release.
- **Stripe's online-migration pattern:** dual-write, change reads, change writes, remove old data ([Stripe]).
- **Dual writes from application code can diverge.** Prefer an outbox table or change-data-capture ([Debezium]) to keep stores in sync.
- **Verify with:**
  - row counts;
  - checksums per partition;
  - sampled deep comparisons;
  - business invariants (sum of balances).
- **Backups:** take one before each irreversible step and test the restore. Keep the old data read-only until the rollback window closes.
- **Lint migration SQL** (squawk in eos core CI). Use a lock timeout, create indexes concurrently, and backfill outside the transaction.

## 7. Cutover and rollback
- **Cutover runbook:**
  - preconditions (parity, backups, on-call);
  - a timeline with owners;
  - go/no-go criteria and a time limit for the decision;
  - the exact commands;
  - verification queries and dashboards;
  - communication.
- **Rollback runbook:**
  - triggers (error rate, latency, mismatch, a business metric);
  - steps to route back;
  - data reconciliation for writes made on the new path;
  - who decides.
- Rehearse both in staging, and time them.
- Keep the old path warm (deployed, flag-able) for an agreed window.

## 8. Decommission
Remove the old code, routes, jobs, data (after the retention period), flags, dashboards, secrets and DNS. Archive the runbooks and the parity report in `docs/migration/<name>/`.

## 9. With AI agents
- Give the agent one slice per session with the plan file; it must not touch other slices.
- Characterization tests are protected like other tests: agents may add them but never loosen them (`eos test-integrity`).
- Ask the agent for a parity report, not a claim of parity.

## Sources
- [Spolsky]: https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/
- [Characterization test]: https://en.wikipedia.org/wiki/Characterization_test (term from M. Feathers, *Working Effectively with Legacy Code*)
- [ApprovalTests]: https://approvaltests.com/
- [Fowler: strangler fig]: https://martinfowler.com/bliki/StranglerFigApplication.html
- [Fowler: branch by abstraction]: https://martinfowler.com/bliki/BranchByAbstraction.html
- [Fowler: parallel change]: https://martinfowler.com/bliki/ParallelChange.html
- [Fowler: feature toggles]: https://martinfowler.com/articles/feature-toggles.html
- [Azure pattern]: https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig
- [Shopify]: https://shopify.engineering/refactoring-legacy-code-strangler-fig-pattern
- [GitHub Scientist]: https://github.com/github/scientist
- [OpenFeature]: https://openfeature.dev/
- [Stripe]: https://stripe.com/blog/online-migrations
- [Debezium]: https://debezium.io/
- Book: Sam Newman, *Monolith to Microservices*: https://samnewman.io/books/monolith-to-microservices/
