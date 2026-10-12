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
How one story goes from idea to `main`. With **autopilot** on (the default, `eos explain autopilot`) you only do step 1 and, rarely, step 4.
1. **Build** (agent chat): paste the prompt `eos next` gives you. The agent writes the tests first, then the code, and runs `python3 .eos/bin/eos.py verify` until it is green.
2. **Ship** (the agent does it): `python3 .eos/bin/eos.py ship --story <story file>` makes a **branch** (a private copy of the code), a **commit** (a saved snapshot), pushes it, marks the story done and opens a **pull request (PR)**: a GitHub page showing the change before it joins `main`.
3. **Checks** (automatic, on GitHub): **CI** re-runs every check on GitHub's computers, and the **eos review** check decides whether a person must look. All green and nothing sensitive: the PR merges by itself and its branch is deleted.
4. **Only if asked** (GitHub): a PR that touches login, personal data, money, the database, CI or the tests gets the label `needs-human`, and you are mentioned in a comment saying why. Read the *Files changed* tab; if it is fine, add the label `human-approved` (`gh pr edit <PR number> --add-label human-approved`) and it merges itself.
5. **Next story** (terminal): `git switch main && git pull`, then `eos next`.
With autopilot off, you do steps 2 to 4 yourself: `git switch -c feat/<name>`, `git add -A`, `git commit -m "feat: ..."`, `git push -u origin HEAD`, `gh pr create --fill`, `gh pr checks --watch`, then `gh pr merge --squash --delete-branch`.
`gh` is the GitHub command-line tool (https://cli.github.com); run `gh auth login` once.

## autopilot | auto-merge | needs-human | human-approved | eos-review | ship
**Autopilot** lets pull requests merge themselves, so you don't have to click Merge after every story. GitHub does not let you approve your own pull request, so the reviewer is a check instead of a person: the **eos review** job (in `.github/workflows/eos-autopilot.yml`) reads each PR. It sorts the change by risk (the lane) and looks for weakened tests or changed checks. If an `OPENROUTER_API_KEY` secret exists, it also posts an AI review comment, which is advice only.
- **Safe change**: when every check is green, the `eos autopilot merge` job squash-merges it and deletes the branch.
- **Sensitive change** (login, personal data, money, database migrations, CI or check settings, weakened tests): the PR gets the label `needs-human`, you are @-mentioned in a comment explaining why, and the eos review check stays red. You read it and add `human-approved`, and it merges itself. Agents never add that label.
Set it up once per repo: `eos autopilot setup` (needs `gh auth login`). It allows squash merge and auto-merge, deletes branches after merge, creates the labels, and asks GitHub to require the green `eos review` check on `main` (no human approval needed). GitHub Free has no branch protection for private repos; autopilot still works there, the only difference being that GitHub won't stop someone clicking Merge on a red PR.
Turn it off or on: `eos autopilot off` / `eos autopilot on`. Merges by the default token don't start other workflows (a GitHub rule): for a deploy-on-main workflow, add a fine-grained token as the secret `EOS_AUTOPILOT_TOKEN`.

## test-integrity | test-change-approved | label | labels
**Test integrity** is a check that runs on every pull request. It compares the PR with `main` and stops it when the change could make the tests prove less than before: a test skipped or deleted, an `assert` removed, a coverage or score threshold lowered, or a "ignore this error" comment added in risky code. This stops anyone (an AI agent included) from turning checks green by weakening them.
Sometimes the change is honest: a test rewritten because the feature changed, or an old test replaced by a better one. Then a human confirms it by adding the GitHub **label** (a tag on the PR) `test-change-approved`, and the check stops blocking.
Who adds it: the reviewer, never the agent that wrote the change. How: read the changed tests on the PR's *Files changed* tab; if they are fine, either click *Labels* > `test-change-approved` on the PR page, or run `gh pr edit <PR number> --add-label test-change-approved` in the terminal. GitHub re-runs the checks by itself. If `gh` answers that the label is not found, create it once per repo: `gh label create test-change-approved`, then run the `gh pr edit` line again.
If the change is NOT honest (a test was weakened to hide a bug), don't add the label: ask the agent to restore the test and fix the code instead.
Run it on your machine before pushing: `python3 .eos/bin/eos.py test-integrity --base origin/main`.

## handoff | hand-off | end-of-task
At the end of every story or task, an agent following eos ends with a plain-words hand-off: what it did, what it verified (which checks ran and their result), and the one next action, saying where to do it (terminal, agent chat or GitHub) and offering to do the git and pull-request steps itself. Any eos or CI name is explained in a few words. If an agent hands you jargon, reply "explain that in plain words and tell me exactly what to type and where", or run `eos where`.
