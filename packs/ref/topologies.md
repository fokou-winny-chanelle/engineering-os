# Topologies: modular monolith, microservices, monorepo, multi-repo workspace

Read on demand by the topology and decisions packs. Sources are at the end; they were checked on 2026-10-10.

## 1. Choosing (summary; full matrix in `decision-matrices.md` §5)
- **Default: a modular monolith.** It is one deployable, has one database with a schema per module, and lets you move fast with few moving parts.
- **Microservices** only for a named reason: independent scaling, separate teams with separate release cycles, or a fault or compliance boundary. You pay in network failures, data consistency, observability and on-call.
- **Monorepo vs multi-repo** is about *code storage and change coordination*, not runtime. A monorepo makes atomic cross-app changes easy. Multi-repo gives isolation and separate permissions, but cross-repo changes need coordination (§5).

## 2. Modular monolith
- **Layout:** `src/modules/<name>/` (or `app/modules/`, `domains/`). Each module has:
  - a public API (`api.py` / package `__init__` / `index.ts`);
  - internal code;
  - its own tables (schema or table prefix);
  - an owner.
- **Rules:**
  - no imports of another module's internals;
  - no joins across module tables;
  - side effects across modules go through domain events or an in-process bus;
  - no cycles.
- **Enforce the rules with a fitness function in CI** ([ThoughtWorks: fitness functions]):
  - Python: import-linter contracts (`independence`, `layers`, `forbidden`, `protected`; wildcards like `app.modules.*`, and `broken_contract_guidance` to print the fix) ([import-linter]). Tach is an alternative ([Tach]).
  - JS/TS: dependency-cruiser rules with group matching (`$1`) to allow only a module's own files and others' `index.ts`. `depcruise-baseline` writes the known violations and `--ignore-known` hides them, so only new ones fail ([dependency-cruiser]). dependency-cruiser 18 declares Node ^22, ^24 or ≥26 in its `engines` field (checked 2026-10-10); on Node 20 use v16. Nx `enforce-module-boundaries` with tags in Nx workspaces ([Nx]).
  - JVM: ArchUnit tests ([ArchUnit]); Spring Modulith verifies module structure in Spring Boot ([Spring Modulith]).
  - Ruby: Packwerk packages with dependency and privacy checks ([Packwerk]).
- **Ownership:** a modules catalog (`docs/architecture/modules.md`) plus CODEOWNERS lines per module.
- **Path to services:** a module with a clean API and its own tables can be extracted later behind the same contract.

## 3. Microservices
- **Data:** each service owns its data, and other services never read its database ([microservices.io: database per service]).
- **Contracts:**
  - HTTP: OpenAPI, with a breaking-change check by oasdiff ([oasdiff]);
  - gRPC: protobuf, with `buf breaking` ([buf]);
  - events: AsyncAPI ([AsyncAPI]);
  - between teams: consumer-driven contract tests with Pact ([Pact]).
- **Versioning:** additive first. A breaking change ships as a new version (path `/v2`, a new proto package, a new event type), and the old one stays until no consumer uses it.
- **Calls:** timeouts, retries with backoff and jitter, idempotency keys, circuit breakers. Use an outbox for "write + publish".
- **Service catalog:** one `catalog-info.yaml` per service (Backstage descriptor: `kind: Component`, `spec.owner`, `providesApis`, `consumesApis`) ([Backstage]), plus a human table in `docs/architecture/services.md`.
- **Service template** (`eos new service`): README with purpose, owner, SLO, runbook link; contract stub; catalog file; nested AGENTS.md. Copy the code skeleton from the best existing service.
- **Shared libraries:** technical only (logging, tracing, auth client, HTTP client), versioned and owned. Never share domain models or databases. Duplication beats coupling.
- **Local orchestration:** a root `compose.yaml` with every service plus its dependencies, health checks, `depends_on: condition: service_healthy`, profiles for optional parts ([Compose profiles]), `include` to compose per-service files ([Compose include]) and `develop.watch` for live reload ([Compose watch]).
- **Observability:** trace ids propagated across services (OpenTelemetry), one dashboard per service, SLOs per user journey (performance-scale pack).

## 4. Monorepo
- **Tools:**
  - pnpm workspaces ([pnpm]);
  - Turborepo ([Turborepo]) or Nx ([Nx]) for task graphs and "affected" runs;
  - uv workspaces for Python ([uv workspaces]);
  - Go `go.work`, Cargo workspaces.
- **eos (v0.5)** wires every app or service directory per stack: a row per stack in AGENTS.md, path rules per directory, pre-commit hooks scoped to each directory, and one CI workflow per (stack, directory) with path filters.
- **Rules:**
  - apps never import apps; shared code lives in packages with an owner;
  - one lockfile per ecosystem at the root;
  - CI runs only what changed;
  - a required CI check must not be path-filtered: use one always-running aggregator job instead.

## 5. Multi-repo workspace
- **Layout:** a parent folder (ideally its own small "workspace" git repo) holds the repos side by side. It contains:
  - `eos-workspace.json` (repos, roles, remotes, owners, provides/consumes);
  - a workspace `AGENTS.md` (map, contracts, cross-repo rules);
  - `<name>.code-workspace`;
  - `docs/changes/` (cross-repo change plans).
- **Per repo:** it keeps its own eos install, rules and checks. `eos workspace sync` adds a short workspace block to each repo's AGENTS.md (who its siblings are, and where the map is).
- **How tools see it:**
  - **Cursor** applies nested `AGENTS.md` files to their subtree, and treats the root one as global ([Cursor rules]). In a multi-root `.code-workspace`, each folder's root AGENTS.md currently applies workspace-wide, a known issue ([Cursor forum]). Opening the parent folder keeps repo rules scoped.
  - **Claude Code** loads `CLAUDE.md` and nested `.claude/rules/` in subdirectories on demand. `--add-dir` grants access to sibling repos; their CLAUDE.md loads only with `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`. The `additionalDirectories` setting grants file access only ([Claude Code large codebases], [Claude Code memory]).
  - **Cline** supports multi-root workspaces, but `.clinerules` and skills load only from the first (primary) folder, and checkpoints are off ([Cline multi-root]). So the workspace folder goes first in the `.code-workspace` file, and `eos workspace sync` copies each repo's path rules into the workspace `.clinerules/` with the repo prefix.
  - **Codex** reads AGENTS.md from the git root down to the current directory ([Codex AGENTS.md]). Start it inside the repo you change; the repo's workspace block points to `../AGENTS.md`.
  - **VS Code:** `.code-workspace` folders use relative paths so the file can be shared ([VS Code multi-root]).
- **Cross-repo change protocol:**
  1. `eos workspace change "<title>"` writes a plan: repos touched, contract version change, merge order, the same branch name everywhere.
  2. The provider repo merges an additive contract change first, then the consumers, then the cleanup.
  3. Each PR links the others: "Part of <workspace>#<plan>; depends on org/repo#123". GitHub has no native cross-repo PR dependency, so the plan file is the source of truth ([GitHub linking]).
  4. `eos workspace status` shows each repo's branch, dirty state and ahead/behind; `--prs` asks the GitHub CLI for open PRs on the plan's branch.
- **Contract versioning across repos:** contracts live in the provider repo (or a `contracts` repo) and are versioned with semver. Consumers pin a version, and a breaking change means a major bump plus a deprecation window.

## Sources
- [ThoughtWorks: fitness functions]: https://www.thoughtworks.com/radar/techniques/architectural-fitness-function
- [import-linter]: https://import-linter.readthedocs.io/en/stable/contract_types/
- [Tach]: https://github.com/gauge-sh/tach
- [dependency-cruiser]: https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md (baseline: doc/cli.md `--baseline`, `--ignore-known`)
- [Nx]: https://nx.dev/docs/features/enforce-module-boundaries
- [ArchUnit]: https://www.archunit.org/
- [Spring Modulith]: https://spring.io/projects/spring-modulith
- [Packwerk]: https://github.com/Shopify/packwerk
- [microservices.io: database per service]: https://microservices.io/patterns/data/database-per-service.html
- [oasdiff]: https://github.com/oasdiff/oasdiff
- [buf]: https://buf.build/docs/breaking/
- [AsyncAPI]: https://www.asyncapi.com/
- [Pact]: https://docs.pact.io/
- [Backstage]: https://backstage.io/docs/features/software-catalog/descriptor-format
- [Compose profiles]: https://docs.docker.com/compose/how-tos/profiles/
- [Compose include]: https://docs.docker.com/compose/how-tos/multiple-compose-files/include/
- [Compose watch]: https://docs.docker.com/compose/how-tos/file-watch/
- [pnpm]: https://pnpm.io/workspaces
- [Turborepo]: https://turborepo.com/docs
- [uv workspaces]: https://docs.astral.sh/uv/concepts/projects/workspaces/
- [Cursor rules]: https://cursor.com/docs/rules
- [Cursor forum]: https://forum.cursor.com/t/agents-md-leaks-into-other-repositories-in-multi-repo-workspace/155477
- [Claude Code large codebases]: https://code.claude.com/docs/en/large-codebases
- [Claude Code memory]: https://code.claude.com/docs/en/memory
- [Cline multi-root]: https://docs.cline.bot/features/multiroot-workspace
- [Codex AGENTS.md]: https://developers.openai.com/codex/guides/agents-md
- [VS Code multi-root]: https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces
- [GitHub linking]: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
