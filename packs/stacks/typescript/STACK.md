---
id: typescript
title: TypeScript / Node (any framework)
kind: stack
mode: files
when: editing TypeScript/JavaScript code, package.json or tsconfig
description: TypeScript/Node conventions - package manager, strict tsconfig, lint/format, Vitest, runtime validation at boundaries, module and error rules. Base for Next.js, NestJS, etc.
globs: ["**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts", "**/*.js", "**/*.mjs", "**/package.json", "**/tsconfig*.json"]
markers: ["package.json", "tsconfig.json"]
contains: []
requires: []
fast_check: "{pm} run lint"
full_check: "{pm} run lint && {pm} run typecheck && {pm} test && {pm} run --if-present build"
ci: node
---
# Stack: TypeScript / Node

## Toolchain (pins in `versions.toml`, `packageManager` field and lockfile)
| Job | Default | Script contract (package.json) |
|---|---|---|
| Package manager | pnpm (lockfile committed; `packageManager` set; Corepack or pnpm/action-setup) | `pnpm install --frozen-lockfile` in CI |
| Lint + format | ESLint (flat config) + Prettier, or Biome (one per repo, ADR) | `lint`, `format` |
| Types | `tsc --noEmit` (strict) | `typecheck` |
| Unit/component tests | Vitest (+ Testing Library) | `test` |
| E2E | Playwright (+ @axe-core/playwright) | `test:e2e` |
| Boundaries | dependency-cruiser or ESLint boundaries plugin | `lint:arch` |
| Audit | `pnpm audit --prod` + Renovate | — |

Every package exposes `lint`, `typecheck`, `test` (and `build` if it builds). eos and CI call only these scripts, so the tools behind them can change freely.

## tsconfig baseline
`"strict": true, "noUncheckedIndexedAccess": true, "exactOptionalPropertyTypes": true, "noImplicitOverride": true, "verbatimModuleSyntax": true, "isolatedModules": true`. Use the `"module"`/`"moduleResolution"` the runtime or bundler requires.

## Rules
1. No `any`. Use `unknown` and narrow it. No non-null `!` without a comment. `// @ts-expect-error` only with a reason; never `@ts-ignore`.
2. Validate at runtime at every boundary (HTTP input, env, external API responses, storage) with a schema library (zod, valibot or similar) and infer types from the schema. Types alone don't protect you at runtime.
3. Generated API client from the OpenAPI spec (e.g. orval or openapi-typescript). Never hand-write response types.
4. Errors.
   - Use typed error classes or Result types at the domain level.
   - Never `catch (e) {}`.
   - Handle every promise: no floating promises (enable the lint rule).
5. Money: use integer minor units or a decimal library. Never use `number` arithmetic on decimal amounts. Format with `Intl.NumberFormat(locale, {style: "currency", currency})`.
6. Env: parse `process.env` once into a typed, validated config module. Fail fast. Only explicitly public variables reach client bundles.
7. Modules: ESM by default. No default exports in shared libraries (named exports refactor better). No barrel files that create import cycles.
8. Node services:
   - Graceful shutdown on SIGTERM.
   - Timeouts on fetch (`AbortSignal.timeout`).
   - A structured logger (pino).
   - OpenTelemetry instrumentation.
9. Tests: Vitest with fake timers for the clock, MSW for HTTP mocks at the network boundary, and Testcontainers for a real DB.

## Pitfalls the AI often makes
- Mixing CommonJS and ESM; importing server-only modules into client code.
- `JSON.parse` without validation; `as` casts to silence errors.
- Adding a dependency for a one-liner. Inventing npm packages: check that it exists, its weekly downloads and maintenance before adding it.
- Editing the lockfile by hand or switching package manager.
