# Sources (checked 2026-10-09; v0.4 additions checked 2026-10-10)
Facts in packs and configs were checked against these primary sources. Re-check them when you bump `versions.toml`.

## Agent tools
- Cursor rules: https://cursor.com/docs/context/rules · Cursor hooks: https://cursor.com/docs/agent/hooks · Cursor MCP: https://cursor.com/docs/context/mcp · Cursor skills: https://cursor.com/docs/context/skills
- Cline rules: https://docs.cline.bot/features/cline-rules · Cline hooks: https://docs.cline.bot/features/hooks · Cline MCP config: https://docs.cline.bot/mcp/configuring-mcp-servers · Cline skills: https://docs.cline.bot/features/skills
- Claude Code memory/CLAUDE.md: https://code.claude.com/docs/en/memory · hooks: https://code.claude.com/docs/en/hooks · MCP: https://code.claude.com/docs/en/mcp · skills: https://code.claude.com/docs/en/skills
- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md · Codex config/MCP: https://developers.openai.com/codex/mcp
- AGENTS.md standard: https://agents.md · Agent Skills spec: https://agentskills.io
- Anthropic, "Effective context engineering for AI agents": https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

## Workflow
- BMAD Method: https://github.com/bmad-code-org/BMAD-METHOD (releases: https://github.com/bmad-code-org/BMAD-METHOD/releases) · docs: https://docs.bmad-method.org
- EARS requirements (as used by Kiro specs): https://kiro.dev/docs/specs/ · GitHub Spec Kit: https://github.com/github/spec-kit
- Diataxis: https://diataxis.fr · DORA metrics: https://dora.dev/guides/dora-metrics/

## MCP servers
- GitHub MCP (remote, toolsets, read-only): https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md
- Context7: https://github.com/upstash/context7 · Postman remote MCP: https://learning.postman.com/docs/developer/postman-api/postman-mcp-server/postman-mcp-remote-server/
- Figma MCP: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ · Playwright MCP: https://github.com/microsoft/playwright-mcp
- MCP security best practices: https://modelcontextprotocol.io/specification/draft/basic/security_best_practices · OWASP GenAI/LLM Top 10: https://genai.owasp.org

## Quality gates
- pre-commit: https://pre-commit.com · pre-commit-hooks: https://github.com/pre-commit/pre-commit-hooks · gitleaks: https://github.com/gitleaks/gitleaks
- ruff-pre-commit: https://github.com/astral-sh/ruff-pre-commit · conventional-pre-commit: https://github.com/compilerla/conventional-pre-commit
- Renovate presets: https://docs.renovatebot.com/presets-helpers/ · actionlint: https://github.com/rhysd/actionlint · shellcheck: https://www.shellcheck.net
- GitHub Actions security hardening: https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- OWASP Top 10: https://owasp.org/Top10/ · OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/ · RFC 9457: https://www.rfc-editor.org/rfc/rfc9457 · WCAG 2.2: https://www.w3.org/TR/WCAG22/

## Stacks
- uv: https://docs.astral.sh/uv/ · ruff: https://docs.astral.sh/ruff/ · mypy: https://mypy.readthedocs.io · pytest: https://docs.pytest.org
- FastAPI: https://fastapi.tiangolo.com · Flask: https://flask.palletsprojects.com · APIFlask: https://apiflask.com · flask-smorest: https://flask-smorest.readthedocs.io
- Pydantic: https://docs.pydantic.dev · SQLAlchemy 2: https://docs.sqlalchemy.org/en/20/ · Alembic: https://alembic.sqlalchemy.org
- Next.js: https://nextjs.org/docs (v16 upgrade notes: https://nextjs.org/docs/app/guides/upgrading/version-16) · TypeScript: https://www.typescriptlang.org/docs/ · pnpm: https://pnpm.io · Vitest: https://vitest.dev · Playwright: https://playwright.dev

## Context and token audit (v0.2.0)
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/gpt-5/gpt-5_prompting_guide.ipynb
- https://cursor.com/docs/context/rules
- https://cursor.com/blog/dynamic-context-discovery
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/mcp
- https://docs.cline.bot/customization/cline-rules
- https://github.com/cline/cline/issues/9398
- https://developers.openai.com/codex/guides/agents-md
- https://github.com/openai/codex/pull/29486
- https://github.com/github/github-mcp-server/releases

## Research-driven upgrades (v0.4.0; full report: docs/research/RESEARCH.md)
- Harness and agent practice: https://openai.com/index/harness-engineering/ · https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2 · https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents · https://cursor.com/blog/agent-best-practices
- Evidence: https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ · https://dora.dev/research/2025/dora-report · https://arxiv.org/abs/2510.20270 (ImpossibleBench) · https://research.trychroma.com/context-rot · https://arxiv.org/abs/2410.02736 (LLM-judge bias) · https://www.gitclear.com/ai_assistant_code_quality_2025_research
- Decisions: https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF (Type 1/2) · https://mcfunley.com/choose-boring-technology · https://www.thoughtworks.com/radar/techniques/architectural-fitness-function
- Design: https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md · https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ · https://www.designtokens.org/TR/2025.10/format/
- Mobile: https://expo.dev/changelog/sdk-57 · https://docs.expo.dev/guides/new-architecture · https://docs.flutter.dev/release/release-notes (stable from storage.googleapis.com/flutter_infra_release/releases/releases_linux.json) · https://github.com/subosito/flutter-action · https://docs.maestro.dev/maestro-flows · https://wix.github.io/Detox/ · https://mas.owasp.org/MASVS/
- Security: https://owasp.org/Top10/2025/ · https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release · https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ · https://simonwillison.net/2025/jun/16/the-lethal-trifecta/ · https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks · https://linddun.org/threat-types/ · https://slsa.dev/spec/v1.1/levels · https://arxiv.org/abs/2406.10279 (package hallucination) · https://prc.cm/en/multimedia/documents/10271-law-n-2024-017-of-23-12-2024-web (Cameroon Law 2024/017)
- Scale: https://sre.google/workbook/implementing-slos/ · https://sre.google/workbook/alerting-on-slos/ · https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/ · https://discord.com/blog/how-discord-stores-trillions-of-messages · https://shopify.engineering/bfcm-readiness-2025
- Reproducibility: https://mise.jdx.dev/dev-tools/mise-lock · https://github.com/jdx/mise-action · https://containers.dev/ · https://github.com/devcontainers/features

## Any project state, self-guiding, topologies (v0.5.0; details: docs/research/v0.5-notes.md)
- Ratchet / baselines: https://eslint.org/docs/latest/use/suppressions · https://phpstan.org/user-guide/baseline · https://phenomnomnominal.github.io/betterer/docs/introduction · https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md
- Legacy and rewrites: https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/ · https://en.wikipedia.org/wiki/Characterization_test · https://approvaltests.com/ · https://martinfowler.com/bliki/StranglerFigApplication.html · https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig · https://shopify.engineering/refactoring-legacy-code-strangler-fig-pattern · https://martinfowler.com/bliki/BranchByAbstraction.html · https://martinfowler.com/bliki/ParallelChange.html · https://martinfowler.com/articles/feature-toggles.html · https://openfeature.dev/ · https://github.com/github/scientist · https://stripe.com/blog/online-migrations · https://debezium.io/ · https://samnewman.io/books/monolith-to-microservices/
- Decisions: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- Topologies: https://www.thoughtworks.com/radar/techniques/architectural-fitness-function · https://import-linter.readthedocs.io/en/stable/contract_types/ · https://github.com/gauge-sh/tach · https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md · https://nx.dev/docs/features/enforce-module-boundaries · https://www.archunit.org/ · https://spring.io/projects/spring-modulith · https://github.com/Shopify/packwerk · https://microservices.io/patterns/data/database-per-service.html · https://github.com/oasdiff/oasdiff · https://buf.build/docs/breaking/ · https://www.asyncapi.com/ · https://docs.pact.io/ · https://backstage.io/docs/features/software-catalog/descriptor-format · https://docs.docker.com/compose/how-tos/profiles/ · https://pnpm.io/workspaces · https://turborepo.com/docs · https://docs.astral.sh/uv/concepts/projects/workspaces/
- Multi-repo workspaces and agents: https://cursor.com/docs/rules · https://forum.cursor.com/t/agents-md-leaks-into-other-repositories-in-multi-repo-workspace/155477 · https://code.claude.com/docs/en/large-codebases · https://code.claude.com/docs/en/memory · https://docs.cline.bot/features/multiroot-workspace · https://docs.cline.bot/customization/cline-rules · https://developers.openai.com/codex/guides/agents-md · https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces · https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
- BMAD brownfield (pinned v6.12.1): https://docs.bmad-method.org/explanation/project-context/ · https://docs.bmad-method.org/reference/skills-and-agents/ · https://docs.bmad-method.org/reference/core-tools/

## Velocity audit (v0.6.0; details: docs/research/v0.6-velocity-audit.md)
- Approval fatigue: https://www.anthropic.com/engineering/claude-code-sandboxing (sandboxing cut permission prompts by 84% internally)
- Fast feedback: https://dora.dev/capabilities/continuous-integration/ (automated tests should give feedback within minutes; about 10 minutes as an upper bound) · https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html (about 1.5% of test runs flaky)
- Related tests and fast reruns: https://vitest.dev/guide/cli.html (`vitest related`) · https://jestjs.io/docs/cli (`--findRelatedTests`) · https://docs.pytest.org/en/stable/how-to/cache.html (`--ff` failed-first)
- Tool config scoping: https://docs.astral.sh/ruff/configuration/ (closest config file wins) · https://pre-commit.com/ (`default_install_hook_types`, `files`, `SKIP`)
