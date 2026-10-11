# Change NNNN: <title>

- **Status:** planned | in progress | merged | rolled back
- **Branch (same name in every repo):** `<branch>`
- **Owner:** <name> · **Started:** YYYY-MM-DD

## Why
One paragraph: the outcome and who needs it.

## Repos touched (merge in this order: contracts and providers first, consumers after)
| Order | Repo | What changes | PR | Status |
|---|---|---|---|---|
<rows>

## Contract change (if any)
- Contract file and version: `<repo>/<file>` vX → vY
- Additive only? yes / no. A breaking change needs a new version and a deprecation window; old and new run side by side until every consumer has moved.
- Breaking-change check: `oasdiff breaking` (OpenAPI) / `buf breaking` (protobuf) / consumer contract tests (Pact)

## Rollout and rollback
- Deploy order (same as merge order unless stated):
- Feature flag(s):
- Rollback: revert consumers first, then providers. Data changes: expand → migrate → contract.

## PR links (each PR description says "Part of <workspace> change NNNN" and links the others)
-
