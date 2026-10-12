# eos concepts (read by `eos explain <topic>`; never loaded into agent context)

## phases | lifecycle | modes | greenfield
Every project is in one **mode**: *greenfield* (new idea), *brownfield* (existing code you are taking over), *rewrite* (refonte: replacing a system piece by piece) or *maintain* (a live, mature product). Each mode has **phases** in order, and each phase has **exit criteria**: files or results that show it is done (e.g. "a PRD exists"). `eos status` shows the phases; `eos next` names the first unmet criterion and how to meet it. The phases and criteria are in `.eos/lifecycle.json`; edit them if your team works differently.
Change mode: `eos mode set <mode>`. Learn: `eos explain brownfield`, `eos explain rewrite`.

## brownfield | adopt | existing code
Taking over existing code. The order matters: **map** it (what is here, how it builds), **measure** it (baseline), add a **safety net** (characterization tests, ratchet gates), then **improve in small slices**. `eos adopt` does the first two without changing your files: your rules and configs are kept; where eos would have written a file you already have, its version goes to `.eos/suggested/` for you to compare. BMAD users: `bmad-project-context` builds verified agent context for an existing repo, and `bmad-help` suggests BMAD's next step.
Source: https://docs.bmad-method.org/explanation/project-context/

## ratchet | baseline | gates
A **ratchet** is a gate that only turns one way. eos runs your linters once and records today's violations as a **baseline** (`.eos/baseline/`). From then on a check fails only on *new* violations, so you can be strict about new code today without fixing years of old issues first. When the count drops, `eos ratchet update` (or `check --tighten` in CI on main) lowers the baseline, so it can never go back up. When it reaches zero, switch to strict gates: `eos gates strict`.
Same idea as ESLint bulk suppressions (https://eslint.org/docs/latest/use/suppressions), PHPStan's baseline (https://phpstan.org/user-guide/baseline), Betterer (https://phenomnomnominal.github.io/betterer/docs/introduction) and dependency-cruiser `--ignore-known` (https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md).

## characterization-tests | golden-master | approval-tests
A **characterization test** records what the code does *today*, right or wrong, so that a refactor or rewrite can prove it changed nothing by accident. You feed real inputs, save the outputs (the "golden master"), and compare future runs to them. Known bugs are pinned as current behaviour with a ticket, and fixed later in their own change.
Sources: https://en.wikipedia.org/wiki/Characterization_test · https://approvaltests.com/

## strangler-fig | rewrite | refonte | migration
Rewriting everything at once ("big bang") is famously risky (https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/). The **strangler fig** pattern puts a **seam** (a proxy route or a facade) in front of the old system and moves one thin **slice** at a time to the new one, until nothing is left of the old. Each slice is reversible. `eos new migration "<name>"` creates the plan, parity report, data-migration plan and cutover/rollback runbooks.
Sources: https://martinfowler.com/bliki/StranglerFigApplication.html · https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig · https://shopify.engineering/refactoring-legacy-code-strangler-fig-pattern

## parity | dual-run | shadow
**Parity** means the new path gives the same results as the old one. In a **dual run** (shadow) the old path still serves users while the new one runs on the same input and the results are compared; mismatches are logged and explained before the new path takes real traffic. Write down what "equal" means (ordering, rounding, time zones) first.
Sources: https://github.com/github/scientist · https://stripe.com/blog/online-migrations

## feature-flags | flags | toggles | expand-contract
A **feature flag** lets you deploy code switched off and turn it on (for some users, then all) without a new release, and off again in seconds. **Expand / contract** (parallel change) does the same for data and APIs: add the new shape alongside the old, move readers and writers over, then remove the old one. Remove flags after the rollout; stale flags become legacy.
Sources: https://martinfowler.com/articles/feature-toggles.html · https://martinfowler.com/bliki/ParallelChange.html · https://openfeature.dev/

## rollback | cutover | runbook
**Cutover** is the moment the old path is switched off. Do it only with parity evidence, a tested backup and a **rollback** you have rehearsed (you know the steps and how long they take). A **runbook** is the written step-by-step list, so nobody improvises under pressure.
Source: https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig

## modular-monolith | modules | boundaries | fitness-functions
One deployable app split into **modules** with clear boundaries: each module exposes a small public API and hides the rest. Boundaries are checked by a tool on every commit (a **fitness function**: import-linter for Python, dependency-cruiser for JS/TS, ArchUnit for Java), so they don't erode. It is the recommended default: you get most benefits of services without the network and operations cost. `eos scaffold boundaries` writes the config; `eos new module <name>` adds a module.
Sources: https://www.thoughtworks.com/radar/techniques/architectural-fitness-function · https://import-linter.readthedocs.io/en/stable/contract_types/ · https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md

## microservices | services | contracts | service-catalog
Independently deployable **services**, each owning its data. They talk through **contracts** (OpenAPI, AsyncAPI, protobuf) that are versioned and checked for breaking changes in CI. A **service catalog** (`docs/architecture/services.md`, Backstage `catalog-info.yaml`) says who owns what. Worth it when teams or scaling needs really differ; otherwise a modular monolith is cheaper. `eos new service <name>` scaffolds one.
Sources: https://microservices.io/patterns/data/database-per-service.html · https://github.com/oasdiff/oasdiff · https://backstage.io/docs/features/software-catalog/descriptor-format

## repo-shape | topology | shape
How the code is laid out: one app in one repo (`single`), one repo with several apps such as apps/web, apps/admin, apps/api (`monorepo`), one app split into modules (`modular-monolith`), many small services (`microservices`), or separate repos in one parent folder (a workspace). For a new project it stays "not decided yet" until the architecture step, because it's hard to change later; `eos next` then lists the commands for each choice. For one person, one repo with several apps is usually simplest (one clone, one set of checks, one commit for a change that spans frontend and backend). Separate repos pay off when different people or teams own and release the parts on their own. Set it with `eos topology set <shape>`, then `eos update`.

## monorepo
Several apps or packages in one repository with shared tooling (pnpm/uv workspaces, Turborepo, Nx). Changes across apps land in one PR. eos wires checks and CI per app dir, each with its own path filter, so a change to one app doesn't run every pipeline.
Sources: https://pnpm.io/workspaces · https://docs.astral.sh/uv/concepts/projects/workspaces/ · https://turborepo.com/docs

## workspace | multi-repo
Several separate repositories in one parent folder. `eos workspace init` adds a workspace `AGENTS.md` (how the repos relate, contracts, owners), an editor workspace file and a change log for cross-repo changes, while each repo keeps its own rules. Open the parent folder in your editor so agents see both levels. A cross-repo change is planned once (`eos workspace change "<title>"`) and shipped as linked PRs, contract first.
Sources: https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces · https://docs.cline.bot/features/multiroot-workspace · https://code.claude.com/docs/en/memory

## adr | decisions
An **Architecture Decision Record** is a one-page note: context, the decision ("We will…"), and its consequences. Kept in the repo (`docs/adr/`), it lets people and agents see *why* things are the way they are, and change them deliberately instead of by accident. `eos new adr "<decision>"`.
Source: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions

## definition-of-done | done | acceptance-criteria
"Done" means verified, not "the code is written": the acceptance criteria have tests, the full check is green, and risky areas (money, auth, personal data, migrations) are listed for human review. Each story's acceptance criteria are written *before* the code, as Given/When/Then.

## slo | operations | runbooks
A **Service Level Objective** is a target for what users feel (e.g. "99.5% of checkouts succeed over 30 days"). The gap to 100% is the **error budget**: while you have budget, ship; when it runs out, fix reliability first. Alerts fire on budget burn, and each alert links to a runbook.
Sources: https://sre.google/workbook/implementing-slos/ · https://sre.google/workbook/alerting-on-slos/

## teaching | teaching-mode
Teaching mode is on by default for new projects. Agents explain each decision in one or two plain sentences (the principle and why it applies) and end a task with the next step; `eos next` adds plain meanings after jargon and shows the exact sentence to paste into your agent. `eos teach off` makes everything terse (`eos teach on` brings it back). It costs about 45 always-on tokens.

## packs | tokens | context
Agents read instructions on every request, and that costs tokens and attention. eos keeps the always-on part small (AGENTS.md core rules) and loads **packs** only when needed: by file path (e.g. migration docs) or as skills chosen by their one-line description. Budgets are checked by `eos check`; `eos budget` shows the numbers.

## pr-flow | story-loop | pull-request | pr | branch | merge
How one story goes from idea to `main`. Every step says where to type it: the **terminal**, your **agent chat** (Cline or Cursor), or the **GitHub** website. Your agent can run the terminal steps for you: just ask it.
1. **Branch** (terminal): `git switch main && git pull`, then `git switch -c feat/<short-name>`. A branch is a private copy of the code where you can work without touching `main`.
2. **Build** (agent chat): paste the prompt `eos next` gives you. The agent writes the tests first, then the code.
3. **Check** (terminal): `python3 .eos/bin/eos.py verify` runs the checks this change needs. Fix anything red before going on.
4. **Commit** (terminal): `git add -A` then `git commit -m "feat: <what changed>"`. A commit is a saved snapshot with a message.
5. **Pull request** (terminal): `git push -u origin HEAD` then `gh pr create --fill`. A **pull request (PR)** is a page on GitHub that shows the change so it can be reviewed before it joins `main`.
6. **CI** (GitHub, the PR's *Checks* tab, or `gh pr checks` in the terminal): **CI** means GitHub re-runs the checks on its own computers. Wait until they are green (about 2 to 10 minutes).
7. **Approval label, only when the test-integrity check is red** (GitHub or terminal): a reviewer reads the test changes, and if they are honest adds the `test-change-approved` label with `gh pr edit <PR number> --add-label test-change-approved`. See `eos explain test-integrity`.
8. **Merge** (GitHub's *Merge* button, or `gh pr merge --squash --delete-branch`): the change joins `main`. Then `git switch main && git pull`.
9. **Next story**: set the story's `**Status:**` line to `done` and run `eos next`.
`gh` is the GitHub command-line tool (https://cli.github.com); run `gh auth login` once. Without it, do steps 5 to 8 on the GitHub website.

## test-integrity | test-change-approved | label | labels
**Test integrity** is a check that runs on every pull request. It compares the PR with `main` and stops it when the change could make the tests prove less than before: a test skipped or deleted, an `assert` removed, a coverage or score threshold lowered, or a "ignore this error" comment added in risky code. This stops anyone (an AI agent included) from turning checks green by weakening them.
Sometimes the change is honest: a test rewritten because the feature changed, or an old test replaced by a better one. Then a human confirms it by adding the GitHub **label** (a tag on the PR) `test-change-approved`, and the check stops blocking.
Who adds it: the reviewer, never the agent that wrote the change. How: read the changed tests on the PR's *Files changed* tab; if they are fine, either click *Labels* > `test-change-approved` on the PR page, or run `gh pr edit <PR number> --add-label test-change-approved` in the terminal. GitHub re-runs the checks by itself. If `gh` answers that the label is not found, create it once per repo: `gh label create test-change-approved`, then run the `gh pr edit` line again.
If the change is NOT honest (a test was weakened to hide a bug), don't add the label: ask the agent to restore the test and fix the code instead.
Run it on your machine before pushing: `python3 .eos/bin/eos.py test-integrity --base origin/main`.

## handoff | hand-off | end-of-task
At the end of every story or task, an agent following eos ends with a plain-words hand-off: what it did, what it verified (which checks ran and their result), and the one next action, saying where to do it (terminal, agent chat or GitHub) and offering to do the git and pull-request steps itself. Any eos or CI name is explained in a few words. If an agent hands you jargon, reply "explain that in plain words and tell me exactly what to type and where", or run `eos where`.
