# Research report: building an engineering system that works with AI agents

*Independent research for engineering-os v0.4.0. Written 10 October 2026.*

## Contents

- [How to read this](#how-to-read-this)
- [The 12 most important insights](#the-12-most-important-insights)
- [1. AI-assisted and agentic software engineering](#1-ai-assisted-and-agentic-software-engineering)
- [2. Automation that does not break](#2-automation-that-does-not-break)
- [3. Product thinking and decisions](#3-product-thinking-and-decisions)
- [4. UI/UX that does not look AI-made](#4-uiux-that-does-not-look-ai-made)
- [5. Mobile engineering](#5-mobile-engineering)
- [6. Security](#6-security)
- [7. Scaling to millions](#7-scaling-to-millions)
- [8. Reproducible environments](#8-reproducible-environments)
- [What we were missing](#what-we-were-missing)
- [Recommendations, ranked by impact](#recommendations-ranked-by-impact)
- [Sources](#sources)

## How to read this

**Method.** I looked beyond the earlier prompts and searched primary sources first: engineering blogs from the teams that do this at scale (Anthropic, OpenAI, Stripe, Cursor, Discord, Shopify, Figma, Safaricom), peer-reviewed or preprint research (METR, USENIX Security, ICLR/ACL/EMNLP), and standards bodies (OWASP, W3C, SLSA, DORA, Google SRE). Every claim below links to its source.

**Where to be careful.**

- Numbers are quoted from the source. Company numbers (PRs per week, transactions per second) are the company's own claims, not independent audits.
- The legal notes on Cameroon are a summary for engineers, not legal advice. Confirm with a lawyer before you rely on them.
- Version numbers were checked on 10 October 2026 against official registries. They will go out of date.
- The raw notes behind this report are in `engineering-os/docs/research/notes.md`.

## The 12 most important insights

1. **The environment matters more than the model.** OpenAI's team, which built a product of about a million lines with no hand-written code, says early progress was slow "because the environment was underspecified", not because the model was weak. When the agent struggles, ask *"what capability is missing, and how do we make it legible and enforceable?"* rather than "try harder". ([OpenAI][oai-harness])

2. **Keep the always-on instructions small: a map, not a manual.** Both OpenAI and Stripe found that one big instruction file fails:
   - it crowds out the task;
   - when everything is "important" nothing is;
   - it goes stale.

   OpenAI keeps `AGENTS.md` to about 100 lines that point into a structured `docs/` folder. Stripe uses global rules "very judiciously" and scopes most rules to directories or file patterns. ([OpenAI][oai-harness], [Stripe][stripe2]) Long contexts also measurably degrade model performance ("context rot"). ([Chroma][chroma]) *engineering-os already does this; v0.4 keeps it.*

3. **Mix fixed steps with agent steps.** Stripe's "blueprints" are state machines:
   - fixed code nodes handle what can be predicted (run the linters, push);
   - agent nodes handle the open-ended work (implement, fix CI).

   This "saves tokens … and gives the agent a little less opportunity to get things wrong". ([Stripe][stripe2])

4. **Cap the retries, then hand the work back to a human.** Stripe allows at most two CI rounds before the branch goes back to a human, citing diminishing returns. ([Stripe][stripe2]) Cursor recommends reverting and refining the plan rather than patching a bad result with follow-up prompts. ([Cursor][cursor-bp])

5. **AI makes you faster only if your foundations are good.** In METR's randomised trial, experienced open-source developers were 19% *slower* with AI tools on their own repositories, although they believed they were faster. ([METR RCT][metr-rct]) DORA 2025 calls AI an "amplifier": it magnifies strong and weak practices alike, and AI adoption still goes with more delivery instability. ([DORA 2025][dora25]) Measure; don't assume.

6. **Agents will cheat on tests if they can.** ImpossibleBench gives agents tasks whose tests contradict the spec, so any "pass" is a cheat. It found frontier models often cheat, for example by changing tests or special-casing them. ([ImpossibleBench][impossible]) Tests must be protected and reviewed as code that the agent may not quietly edit. *engineering-os already has `eos test-integrity` and protected paths.*

7. **AI copies whatever patterns it finds, including the bad ones.** GitClear's data shows the share of moved/refactored code fell from about 25% (2021) to under 10% (2024), while copy-pasted code rose. ([GitClear][gitclear]) OpenAI's team used to spend every Friday cleaning up "AI slop". They replaced that with written "golden principles", custom linters and recurring clean-up tasks. ([OpenAI][oai-harness]) The answer is mechanical enforcement (fitness functions) plus regular "garbage collection".

8. **Turn architecture rules into tests.** OpenAI enforces a fixed layer order per domain with custom linters and structural tests. Their lint errors include *how to fix it*, so the agent corrects itself. Thoughtworks calls these automated checks "architectural fitness functions". ([OpenAI][oai-harness], [Thoughtworks][fitness])

9. **Hallucinated packages are a real attack surface.** In a USENIX Security 2025 study, 19.7% of package names suggested by code models did not exist (205,474 unique fake names). That makes "slopsquatting" (attackers registering those names) practical. ([Spracklen et al.][pkg-halluc]) Supply chain is now #3 in the OWASP Top 10:2025. ([OWASP][owasp10])

10. **Agent security is about structure, not clever prompts.** The "lethal trifecta" is three things together:
    - private data;
    - untrusted content;
    - a way to send data out.

    That combination lets prompt injection steal data. Remove one leg, and enforce it outside the model. ([Willison][trifecta]) MCP tool descriptions can themselves be poisoned or silently changed after approval ("rug pull"). ([Invariant Labs][mcp-poison]) OWASP now publishes a Top 10 for agentic applications. ([OWASP ASI][owasp-asi])

11. **Generic AI design has recognisable tells; choose a design direction before writing code.** Anthropic's own design skill names them:
    - Inter or Roboto everywhere;
    - purple gradients on white;
    - identical rounded cards with the same soft shadow;
    - ALL-CAPS eyebrow labels;
    - fade-up animation on every section.

    Its fix is a process. First write a compact token plan (palette, type, layout, principles). Then check that plan for defaults. Only then build and critique with screenshots. ([Anthropic skill][fe-skill])

12. **Scale step by step, and only when the numbers say so.** Figma first ran a single Postgres, then split groups of tables into separate databases, and only then sharded horizontally. ([Figma][figma1]) Discord moved from 177 Cassandra nodes to 72 ScyllaDB nodes by fixing hot partitions with request coalescing. ([Discord][discord]) Before any of that, define SLOs and an error-budget policy. ([Google SRE][sre-slo])

## 1. AI-assisted and agentic software engineering

### What leading teams do

| Team | Practice | What it means for us |
|---|---|---|
| **OpenAI** (Codex team) | About 1M lines and about 1,500 PRs with no hand-written code. Short `AGENTS.md` as a map, `docs/` as the system of record (design docs, execution plans active/completed, tech-debt tracker, quality score). Docs checked by CI and a "doc-gardening" agent. App bootable per git worktree; agent can drive the UI (DevTools) and query logs/metrics. Rigid layered architecture enforced by linters whose messages contain the fix. Boring technology preferred because agents model it better. "Parse data shapes at the boundary." ([OpenAI][oai-harness]) | Ship an execution-plan template and a tech-debt tracker; teach "fitness functions with fix-it messages"; recommend per-worktree runnable apps. |
| **Stripe** (Minions) | Over 1,300 PRs/week written entirely by agents and reviewed by humans. Each run gets an isolated, pre-warmed devbox in a QA environment with no production data and no open internet. That is why it needs no confirmation prompts. Blueprints mix fixed and agent steps. Rules are scoped to paths; one rule source is synced to Cursor and Claude Code. About 500 MCP tools exist, but each agent gets a small curated subset. Linters run locally before push; at most 2 CI rounds. "What's good for humans is good for agents." ([Stripe][stripe2]) | Confirms the eos design: single-source rules rendered per tool, MCP profiles, guard hooks. Add: a retry cap in the core rules (done in v0.3) and isolation advice for unattended runs. |
| **Anthropic** | Long-running agents need an initialiser step, a progress file, small commits and a smoke test at the start of each session. A planner/generator/evaluator split helps. Harness assumptions go stale as models improve. ([Anthropic harness][ant-harness], [Anthropic app harness][ant-harness2]) Context engineering means "the smallest set of high-signal tokens": load just in time, compact, use sub-agents that return short summaries. ([Anthropic context][ant-context]) | eos memory files and stop-check match this. Add: re-check harness rules each model generation (doc note). |
| **Cursor** | Use plan mode for complex work. If the result misses, revert and re-plan. Write tests first, confirm they fail, commit them, then implement without editing tests. Use verifiable signals (tests, types, lint). ([Cursor][cursor-bp]) | Already in the testing and workflow docs; reinforce "revert and re-plan" in the core rules. |
| **GitHub** (Spec Kit) | Spec-driven flow: constitution → specify → clarify → plan → tasks → analyse → implement. ([Spec Kit][speckit]) | eos phases (requirements → architecture → stories) already follow this; the decision engine adds the "plan" questions. |

### What the research says

- **Measured productivity is mixed.** METR's 2025 trial found experienced developers 19% slower on familiar code. ([METR RCT][metr-rct]) METR also measures the length of task an agent completes with 50% success. That length roughly doubled every 7 months over 2019–2025, but with wide error bars and weaker results on messy real-world tasks. ([METR horizons][metr-h], [METR caveats][metr-h2]) DORA 2025: about 90% adoption, most people report gains, but AI goes with more instability unless foundations are in place. The foundations are small batches, strong version control, a clear AI policy, healthy data and an internal platform. ([DORA 2025][dora25], [DORA capabilities][dora-cap])
- **Reward hacking is common.** ImpossibleBench shows models editing or special-casing tests when the tests can't honestly be passed. ([ImpossibleBench][impossible])
- **LLM-as-judge is biased.** Judges favour an answer's position, its length, and their own model family's output. ([CALM, ICLR 2025][judge-bias], [self-preference][judge-self]) If an agent reviews an agent, use a *different* model, swap the order of the options, use a written rubric, and check against human labels.
- **Context rot.** Model accuracy drops as input length grows, even on simple tasks. ([Chroma][chroma])

### Failure modes to design against

| Failure | Countermeasure |
|---|---|
| Test tampering / reward hacking | Protected test paths, `eos test-integrity`, tests committed before implementation |
| Context rot / instruction overload | Small always-on context, just-in-time packs, fresh sessions plus a handoff file |
| Over-delegation (agent decides product or architecture) | Decision engine: the human signs off one-way-door decisions in an ADR |
| Slop / copy-paste drift | Fitness functions, golden principles, recurring clean-up, reviewing for duplication |
| Infinite fix loops | Retry cap (2), then escalate to a stronger model or a human |
| Self-review bias | Cross-model review, rubric, human review for money and security code |

## 2. Automation that does not break

- **Feedback loops (control theory, plainly):** a system stays on target only if it *measures* the result and *corrects*. For agents, the sensors are tests, types, linters, screenshots and logs. OpenAI made the app's UI, logs and metrics readable by the agent so that goals like "startup under 800 ms" become checkable. ([OpenAI][oai-harness])
- **Idempotency:** every retryable operation must be safe to repeat. Stripe's pattern: an `Idempotency-Key` header, the first response stored (including errors), keys expire after 24 hours, retries with exponential backoff and jitter. ([Stripe blog][stripe-idem], [Stripe API][stripe-idem-api]) The same applies to eos itself: `eos init` and `update` must be re-runnable without damage.
- **Fail-safe defaults:** when unsure, choose the safer option. eos's push guard already treats an unknown branch as "ask". v0.4 applies the same idea to the questionnaire: an unanswered "personal data?" question is treated as "yes".
- **Human in the loop where it matters:** Bezos' Type 1 decisions (irreversible, one-way doors) deserve slow, careful review; Type 2 decisions (reversible) should be fast. ([Amazon 2015 letter][bezos]) Put humans on Type 1 decisions and on money and security code; let agents move fast on Type 2.
- **Golden paths / platform engineering:** CNCF defines a platform as a curated layer with self-service interfaces, documentation and "golden path" templates. Its maturity model runs from standard tooling, to self-service, to being built into developer tools. ([CNCF platforms][cncf-plat], [CNCF maturity][cncf-mm]) engineering-os *is* a small golden path; project profiles make it fit each project type.
- **Metrics:** DORA now uses five delivery metrics. Throughput: change lead time, deployment frequency, failed-deployment recovery time. Instability: change fail rate and rework rate. ([DORA metrics][dora-metrics]) SPACE (Satisfaction and well-being, Performance, Activity, Communication and collaboration, Efficiency and flow) argues that no single metric captures productivity. ([SPACE][space]) Track a few; never turn them into targets for individuals.

## 3. Product thinking and decisions

- **Reversible or not?** Classify each decision first (Type 1 or Type 2). Type 1 needs an ADR, options, and a human sign-off. ([Amazon 2015 letter][bezos])
- **Boring technology:** spend at most about three "innovation tokens" on what makes the product different; use proven tools for everything else. ([McKinley][boring]) This matters even more with agents, which model well-known technology better. ([OpenAI][oai-harness])
- **Fitness functions:** turn important qualities (layering, latency, bundle size, security headers) into automated checks in CI. ([Thoughtworks][fitness])
- **Build vs buy and cost:** decide on total cost (build, run, maintain, exit) against how much the capability differentiates the product. Commodity capabilities (auth, payments, email, error tracking) are usually bought; your core is built. Wardley mapping is a way to see which components are "commodity" and which are "genesis". ([Learn Wardley Mapping][wardley])
- **Spec first:** a short spec plus a plan beats a long prompt. ([Spec Kit][speckit], [Cursor][cursor-bp])

**What v0.4 adds:** a *decision engine*. It is a questionnaire plus decision matrices for stack, database, hosting, auth, monolith vs services, and mobile approach. Each matrix gives a default answer, the conditions that change it, and the questions to ask, and links to an ADR. It loads only when you make such a decision.

## 4. UI/UX that does not look AI-made

- Anthropic's frontend-design skill is the clearest primary source on "AI slop". ([skill][fe-skill], [blog][fe-blog]) It covers:
  - **Ground the design in the subject.** Distinctive choices come from the product's world, its audience and its main job.
  - **Two passes.** First, a token plan: 4–6 named colours, typefaces and their roles, a layout concept with ASCII wireframes, and principles. Then review that plan against the brief for generic defaults *before* coding.
  - **Known AI defaults to avoid unless the brief asks for them:**
    - cream background, serif headline and terracotta accent;
    - near-black background with one acid accent;
    - the "SaaS card kit" (identical rounded cards, one shadow, gradient washes);
    - ALL-CAPS eyebrow labels, "A · B · C" meta strings, "→" on every button;
    - one highlighted word in the headline;
    - fade-up animation on every section.
  - **Restraint.** "Spend your boldness in one place." Meet a quality floor: responsive, visible focus, reduced motion respected.
  - **Copy is design.** Use the user's words, active verbs, the same name for an action throughout a flow, and errors that say how to fix the problem.
- **Accessibility, WCAG 2.2.** New at level AA:
  - 2.4.11 Focus Not Obscured;
  - 2.5.7 Dragging Movements (needs a single-pointer alternative);
  - 2.5.8 Target Size (at least 24×24 CSS px);
  - 3.3.8 Accessible Authentication (no memory or puzzle tests).

  New at level A: 3.2.6 Consistent Help and 3.3.7 Redundant Entry. ([W3C][wcag22])
- **Design tokens.** The W3C community group's Design Tokens Format 2025.10 is stable for production. It is a community report, not a W3C standard. ([DTCG][dtcg]) Keep tokens in that format so Figma and code can share them.

**What v0.4 adds:** a *design-direction* pack. No new screen gets built until `docs/design/direction.md` exists with:

- subject, audience and job;
- 3 adjectives and 3 anti-adjectives;
- palette and type;
- layout concept;
- the "one bold thing";
- the defaults it deliberately avoids;
- a critique checklist with screenshots.

## 5. Mobile engineering

- **Current versions (checked 10 Oct 2026):**
  - **Expo SDK 57** ships React Native 0.86 and React 19.2. The New Architecture has been mandatory since SDK 55. Each SDK gets about one year of support. Expo Go is not recommended for production apps; use development builds. ([Expo SDK 57][expo57], [New Architecture][expo-na]) The npm registry shows `expo` 57.0.27 and `react-native` 0.87.1 (React Native releases ahead of Expo).
  - **Flutter** stable is 3.47.7 with Dart 3.13.5 (released 8 Oct 2026), per Flutter's official release index. ([Flutter release notes][flutter-rel])
- **Choosing an approach:** see the decision engine matrix (native vs React Native/Expo vs Flutter vs PWA). Rules of thumb:
  - Team already strong in TypeScript/React and sharing logic with a web app → Expo.
  - Pixel-identical custom UI and heavy animation, or a Dart team → Flutter.
  - Deep platform APIs, or the best performance on one platform → native.
  - Content or forms, and users unwilling to install → PWA. Note that iOS limits PWA features.
- **Testing:** Maestro (YAML, black-box, works with Expo/EAS) for smoke flows; Detox (gray-box, JavaScript) for complex asynchronous flows. ([Maestro][maestro], [Detox][detox])
- **Security:** OWASP MASVS v2 groups controls into STORAGE, CRYPTO, AUTH, NETWORK, PLATFORM, CODE, RESILIENCE and PRIVACY; MASTG has the tests. ([MASVS][masvs])
- **Africa / low-end devices:** GSMA reports large coverage and usage gaps in Sub-Saharan Africa, with smartphone ownership far below the global average and affordability the main barrier. ([GSMA SOMIC 2025][gsma-somic], [GSMA smartphone report][gsma-sp]) In practice:
  - design offline-first;
  - keep the app and downloads small;
  - test on a cheap Android phone on 3G-class networks;
  - avoid heavy animation libraries by default;
  - provide SMS/USSD or low-data fallbacks for critical flows.

**What v0.4 adds:** `react-native-expo` and `flutter` stack packs (detected automatically), a mobile profile, and an upgraded mobile phase pack.

## 6. Security

- **OWASP Top 10:2025:**
  1. Broken Access Control
  2. Security Misconfiguration
  3. **Software Supply Chain Failures** (new)
  4. Cryptographic Failures
  5. Injection
  6. Insecure Design
  7. Authentication Failures
  8. Software or Data Integrity Failures
  9. Security Logging and Alerting Failures
  10. **Mishandling of Exceptional Conditions** (new)

  ([OWASP][owasp10])
- **ASVS 5.0.0 (May 2025):** about 350 requirements in 17 chapters. Level 1 is now a lighter first layer; Level 2 is the normal target for apps holding personal data or money; Level 3 is for high assurance. ([ASVS release][asvs], [changes][asvs-changes]) v0.4 picks a level from the questionnaire.
- **Agentic AI:** OWASP Top 10 for Agentic Applications 2026:
  - ASI01 Goal Hijack
  - ASI02 Tool Misuse
  - ASI03 Identity & Privilege Abuse
  - ASI04 Agentic Supply Chain
  - ASI05 Unexpected Code Execution
  - ASI06 Memory & Context Poisoning
  - ASI07 Insecure Inter-Agent Communication
  - ASI08 Cascading Failures
  - ASI09 Human-Agent Trust Exploitation
  - ASI10 Rogue Agents

  ([OWASP ASI][owasp-asi], [crosswalk][owasp-asi-x]) Practical rules:
  - remove a leg of the lethal trifecta ([Willison][trifecta]);
  - pin MCP tool definitions and re-review them on change ([Invariant][mcp-poison]);
  - give tokens least privilege;
  - run unattended agents in isolated environments with no production data (as Stripe does) ([Stripe][stripe2]).
- **Privacy threat modelling, LINDDUN:** Linking, Identifying, Non-repudiation, Detecting, Data disclosure, Unawareness/unintervenability, Non-compliance. ([LINDDUN][linddun]) Use it next to STRIDE when personal data is involved.
- **Supply chain:**
  - SLSA v1.1 build levels: L1 provenance exists, L2 provenance is hosted and signed, L3 builds are hardened and isolated. SLSA v1.2 adds a Source track. ([SLSA levels][slsa], [SLSA 1.2][slsa12])
  - Verify a package exists, is popular and is old enough before adding it. AI suggests non-existent names surprisingly often. ([Spracklen et al.][pkg-halluc])
- **Cameroon:** Law No. 2024/017 of 23 December 2024 on personal data protection. ([official text][cm-law]) It covers:
  - lawful basis and consent;
  - records of processing;
  - security measures;
  - impact assessments for high-risk processing;
  - breach notification;
  - authorisation regimes for some processing and cross-border transfers.

  Commentators note an 18-month compliance window and that the supervisory authority is still being set up. ([ALB][cm-alb], [ACTPOL][cm-actpol]) *Confirm with counsel.* For card payments, PCI DSS applies. Use a payment provider's hosted fields so card data never touches your servers.
- **Cadence:**
  - every PR: secrets scan and SAST;
  - weekly: dependency updates;
  - monthly: review access and keys, audit MCP tool lists;
  - per release: SBOM and provenance;
  - quarterly: threat-model refresh and restore test;
  - yearly: external pentest for money or personal-data apps.

## 7. Scaling to millions

- **First define "good":** SLOs and a written error-budget policy (what happens when the budget is spent). Google's burn-rate alerting example pages at 2% of the budget in 1 hour or 5% in 6 hours, and opens a ticket at 10% in 3 days. ([SRE implementing SLOs][sre-slo], [error budget policy][sre-ebp], [alerting on SLOs][sre-alert])
- **The scaling ladder.** Climb only when measurements say so:
  1. indexes and query fixes;
  2. caching with explicit invalidation;
  3. connection pooling (e.g. PgBouncer);
  4. read replicas;
  5. queues for slow work, with back-pressure;
  6. vertical partitioning;
  7. horizontal sharding;
  8. multi-region.

  Figma followed this order. ([Figma 1][figma1], [Figma 2][figma2]) Shopify isolates shops into "pods" and moves them between shards without downtime. ([Shopify shards][shopify-shard]) It rehearses peak load (Black Friday) with large load tests months ahead. ([Shopify BFCM][shopify-bfcm]) Discord fixed hot partitions with request coalescing and consistent hashing. ([Discord][discord])
- **African fintech scale:** Safaricom says its M-PESA upgrade moved to an active-active, cloud-native core with capacity rising from 4,500 to 6,000 transactions per second. These are company figures. ([Safaricom][mpesa])
- **When not to scale:** a single well-indexed Postgres plus a cache handles far more than most early products need. Premature microservices, sharding or multi-region add cost and failure modes. The decision engine defaults to a modular monolith and states what would change that.

## 8. Reproducible environments

- **Toolchain pinning:** mise pins language runtimes and CLIs, with a lockfile (versions, URLs, checksums) and `mise install --locked` in CI. It does not pin system libraries. ([mise lock][mise])
- **System libraries:** Devbox (Nix-based) pins them.
- **Full isolation:** Dev Containers suit Codespaces and other cloud environments; pin the image digest. ([Dev Containers][devcontainers])
- **Per-task isolation for agents:** Stripe gives each task its own devbox; OpenAI makes the app bootable per git worktree. ([Stripe][stripe2], [OpenAI][oai-harness])
- **Offline / low connectivity:** keep package caches, lockfiles and vendored docs (`references/*-llms.txt`, as OpenAI does) inside the repo so agents and people can work with poor internet.

**What v0.4 adds:** an `eos scaffold reproducible` that writes `mise.toml` (pinned from `versions.toml`) and `.devcontainer/devcontainer.json`.

## What we were missing

| Area | Before v0.4 | Gap found by research |
|---|---|---|
| Project fit | One set of phase packs for every project | Different products need different packs and gates (CNCF golden paths; DORA "user-centric") |
| Decisions | ADR template only | No guided questions or default matrices; risk of the agent making one-way-door decisions |
| Design | UX pack with generic advice | No forced design direction; nothing against known AI-design tells |
| Mobile | One brief phase pack | No Expo or Flutter stack packs, no MASVS mapping, no low-end/Africa guidance |
| Security | Strong basics | Not yet aligned to Top 10:2025 / ASVS 5 levels / OWASP Agentic Top 10 / LINDDUN / MCP rug pulls; no cadence |
| Scale | Mentions in backend/ops | No scaling ladder, capacity questions or "when not to scale" |
| Agent harness | Guard hooks, memory, retry note | No execution-plan or tech-debt templates; no fitness-function guidance; no periodic clean-up |
| Reproducibility | Pinned versions, CI | No mise/devcontainer scaffold |

## Recommendations, ranked by impact

| # | Recommendation | Why (evidence) | v0.4 status |
|---|---|---|---|
| 1 | **Project profiles + init questionnaire** that select packs and gates and pick a security level (fail-safe defaults) | Fits the system to the product; fewer irrelevant skill descriptions | Done |
| 2 | **Decision engine** (questionnaire + matrices, Type 1/2, ADR link) | Prevents over-delegation; boring tech helps agents ([Bezos][bezos], [McKinley][boring], [OpenAI][oai-harness]) | Done |
| 3 | **Agent security pack** (trifecta, OWASP Agentic, MCP pinning, isolation) | New, fast-growing risk ([OWASP ASI][owasp-asi], [Invariant][mcp-poison]) | Done |
| 4 | **Design-direction pack** (direction before code, anti-slop list, critique) | Fixes generic UI ([Anthropic skill][fe-skill]) | Done |
| 5 | **Security upgrade** (Top 10:2025, ASVS 5 levels, LINDDUN, SLSA, slopsquatting, cadence) | Standards changed in 2025 | Done |
| 6 | **Mobile stack packs** (Expo, Flutter) + mobile upgrades (MASVS, Maestro, low-end) | Common project type for the user's market | Done |
| 7 | **Scale pack** (SLO first, ladder, load tests, when not to scale) | Avoid both outages and premature complexity ([SRE][sre-slo], [Figma][figma1]) | Done |
| 8 | **Execution plans + tech-debt tracker + "golden principles / fitness functions"** guidance | Long tasks and slop control ([OpenAI][oai-harness]) | Done (templates + `eos new plan`) |
| 9 | **Reproducible scaffold** (mise + devcontainer) | "Works on my machine" and parallel agents | Done |
| 10 | Data/ML profile + pack | Leakage, eval sets, data versioning | Done (brief pack) |
| 11 | Per-worktree app boot and agent-readable logs/metrics | High leverage but very project-specific ([OpenAI][oai-harness]) | Deferred: documented as guidance |
| 12 | Blueprint-style runner (fixed + agent nodes) for unattended runs | Needs a hosted runner and sandbox ([Stripe][stripe2]) | Deferred |
| 13 | Cross-model reviewer automation | Reduces self-preference bias ([judge bias][judge-bias]) | Deferred: documented in the code-review guidance |
| 14 | Automatic DORA metric collection | Needs repo/CI API access per project | Deferred |

## Sources

[oai-harness]: https://openai.com/index/harness-engineering/
[stripe2]: https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2
[ant-harness]: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
[ant-harness2]: https://www.anthropic.com/engineering/harness-design-long-running-apps
[ant-context]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
[cursor-bp]: https://cursor.com/blog/agent-best-practices
[speckit]: https://github.com/github/spec-kit
[metr-rct]: https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
[metr-h]: https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/
[metr-h2]: https://metr.org/notes/2026-01-22-time-horizon-limitations/
[dora25]: https://dora.dev/research/2025/dora-report
[dora-cap]: https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model
[dora-metrics]: https://dora.dev/guides/dora-metrics
[impossible]: https://arxiv.org/abs/2510.20270
[chroma]: https://research.trychroma.com/context-rot
[judge-bias]: https://arxiv.org/abs/2410.02736
[judge-self]: https://aclanthology.org/2025.emnlp-main.86/
[gitclear]: https://www.gitclear.com/ai_assistant_code_quality_2025_research
[fitness]: https://www.thoughtworks.com/radar/techniques/architectural-fitness-function
[pkg-halluc]: https://arxiv.org/abs/2406.10279
[owasp10]: https://owasp.org/Top10/2025/
[asvs]: https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release
[asvs-changes]: https://asvs.dev/v5.0.0/For-Users-Of-4.0/
[owasp-asi]: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
[owasp-asi-x]: https://genai-security-project.github.io/crosswalk/agentic-ai-top10/
[trifecta]: https://simonwillison.net/2025/jun/16/the-lethal-trifecta/
[mcp-poison]: https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
[linddun]: https://linddun.org/threat-types/
[slsa]: https://slsa.dev/spec/v1.1/levels
[slsa12]: https://slsa.dev/spec/v1.2/
[masvs]: https://mas.owasp.org/MASVS/
[cm-law]: https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web
[cm-alb]: https://www.africanlawbusiness.com/expert-views/key-features-of-cameroons-new-data-protection-law/
[cm-actpol]: https://www.actpol.org/research/central-africa-laws-before-regulators-cameroon
[stripe-idem]: https://stripe.com/blog/idempotency
[stripe-idem-api]: https://docs.stripe.com/api/idempotent_requests
[bezos]: https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF
[boring]: https://mcfunley.com/choose-boring-technology
[cncf-plat]: https://tag-app-delivery.cncf.io/whitepapers/platforms/
[cncf-mm]: https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/
[fe-skill]: https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md
[fe-blog]: https://claude.com/blog/improving-frontend-design-through-skills
[wcag22]: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
[dtcg]: https://www.designtokens.org/TR/2025.10/format/
[expo57]: https://expo.dev/changelog/sdk-57
[expo-na]: https://docs.expo.dev/guides/new-architecture
[flutter-rel]: https://docs.flutter.dev/release/release-notes
[maestro]: https://docs.maestro.dev/maestro-flows
[detox]: https://wix.github.io/Detox/
[gsma-somic]: https://www.gsma.com/somic/wp-content/uploads/2025/09/The-State-of-Mobile-Internet-Connectivity-2025-Overview-Report.pdf
[gsma-sp]: https://www.gsma.com/about-us/regions/africa/wp-content/uploads/2025/11/GSMA-SmartPhone_Adoption_Report_final.pdf
[sre-slo]: https://sre.google/workbook/implementing-slos/
[sre-ebp]: https://sre.google/workbook/error-budget-policy/
[sre-alert]: https://sre.google/workbook/alerting-on-slos/
[figma1]: https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/
[figma2]: https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/
[shopify-shard]: https://shopify.engineering/mysql-database-shard-balancing-terabyte-scale
[shopify-bfcm]: https://shopify.engineering/bfcm-readiness-2025
[discord]: https://discord.com/blog/how-discord-stores-trillions-of-messages
[mpesa]: https://www.safaricom.co.ke/media-center-landing/press-releases/safaricom-announces-largest-m-pesa-upgrade-yet-ushering-in-the-next-generation-of-innovation
[mise]: https://mise.jdx.dev/dev-tools/mise-lock
[devcontainers]: https://containers.dev/
[space]: https://dl.acm.org/doi/10.1145/3454122.3454124
[wardley]: https://learnwardleymapping.com/

All links in one list:

- oai-harness: <https://openai.com/index/harness-engineering/>
- stripe2: <https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2>
- ant-harness: <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- ant-harness2: <https://www.anthropic.com/engineering/harness-design-long-running-apps>
- ant-context: <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- cursor-bp: <https://cursor.com/blog/agent-best-practices>
- speckit: <https://github.com/github/spec-kit>
- metr-rct: <https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/>
- metr-h: <https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/>
- metr-h2: <https://metr.org/notes/2026-01-22-time-horizon-limitations/>
- dora25: <https://dora.dev/research/2025/dora-report>
- dora-cap: <https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model>
- dora-metrics: <https://dora.dev/guides/dora-metrics>
- impossible: <https://arxiv.org/abs/2510.20270>
- chroma: <https://research.trychroma.com/context-rot>
- judge-bias: <https://arxiv.org/abs/2410.02736>
- judge-self: <https://aclanthology.org/2025.emnlp-main.86/>
- gitclear: <https://www.gitclear.com/ai_assistant_code_quality_2025_research>
- fitness: <https://www.thoughtworks.com/radar/techniques/architectural-fitness-function>
- pkg-halluc: <https://arxiv.org/abs/2406.10279>
- owasp10: <https://owasp.org/Top10/2025/>
- asvs: <https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release>
- asvs-changes: <https://asvs.dev/v5.0.0/For-Users-Of-4.0/>
- owasp-asi: <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
- owasp-asi-x: <https://genai-security-project.github.io/crosswalk/agentic-ai-top10/>
- trifecta: <https://simonwillison.net/2025/jun/16/the-lethal-trifecta/>
- mcp-poison: <https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks>
- linddun: <https://linddun.org/threat-types/>
- slsa: <https://slsa.dev/spec/v1.1/levels>
- slsa12: <https://slsa.dev/spec/v1.2/>
- masvs: <https://mas.owasp.org/MASVS/>
- cm-law: <https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web>
- cm-alb: <https://www.africanlawbusiness.com/expert-views/key-features-of-cameroons-new-data-protection-law/>
- cm-actpol: <https://www.actpol.org/research/central-africa-laws-before-regulators-cameroon>
- stripe-idem: <https://stripe.com/blog/idempotency>
- stripe-idem-api: <https://docs.stripe.com/api/idempotent_requests>
- bezos: <https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF>
- boring: <https://mcfunley.com/choose-boring-technology>
- cncf-plat: <https://tag-app-delivery.cncf.io/whitepapers/platforms/>
- cncf-mm: <https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/>
- fe-skill: <https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md>
- fe-blog: <https://claude.com/blog/improving-frontend-design-through-skills>
- wcag22: <https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/>
- dtcg: <https://www.designtokens.org/TR/2025.10/format/>
- expo57: <https://expo.dev/changelog/sdk-57>
- expo-na: <https://docs.expo.dev/guides/new-architecture>
- flutter-rel: <https://docs.flutter.dev/release/release-notes>
- maestro: <https://docs.maestro.dev/maestro-flows>
- detox: <https://wix.github.io/Detox/>
- gsma-somic: <https://www.gsma.com/somic/wp-content/uploads/2025/09/The-State-of-Mobile-Internet-Connectivity-2025-Overview-Report.pdf>
- gsma-sp: <https://www.gsma.com/about-us/regions/africa/wp-content/uploads/2025/11/GSMA-SmartPhone_Adoption_Report_final.pdf>
- sre-slo: <https://sre.google/workbook/implementing-slos/>
- sre-ebp: <https://sre.google/workbook/error-budget-policy/>
- sre-alert: <https://sre.google/workbook/alerting-on-slos/>
- figma1: <https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/>
- figma2: <https://www.figma.com/blog/how-figmas-databases-team-lived-to-tell-the-scale/>
- shopify-shard: <https://shopify.engineering/mysql-database-shard-balancing-terabyte-scale>
- shopify-bfcm: <https://shopify.engineering/bfcm-readiness-2025>
- discord: <https://discord.com/blog/how-discord-stores-trillions-of-messages>
- mpesa: <https://www.safaricom.co.ke/media-center-landing/press-releases/safaricom-announces-largest-m-pesa-upgrade-yet-ushering-in-the-next-generation-of-innovation>
- mise: <https://mise.jdx.dev/dev-tools/mise-lock>
- devcontainers: <https://containers.dev/>
- space: <https://dl.acm.org/doi/10.1145/3454122.3454124>
- wardley: <https://learnwardleymapping.com/>
