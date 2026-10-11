---
id: python-fastapi
title: FastAPI services
kind: stack
mode: files
when: editing a FastAPI app (routers, dependencies, schemas)
description: FastAPI conventions - routers, dependencies, Pydantic v2 schemas, async DB, OpenAPI export, error handlers, testing with httpx.
globs: ["**/routers/**", "**/api/**/*.py", "**/main.py", "**/deps.py", "**/dependencies.py", "**/schemas/**"]
markers: ["pyproject.toml", "requirements.txt", "uv.lock"]
contains: ["fastapi"]
requires: ["python"]
fast_check: ""
full_check: ""
ci: ""
---
# Stack: FastAPI (adds to Python pack)

## Structure
- `app/main.py` holds `create_app()` (a factory) with a lifespan context for startup and shutdown (DB pool, HTTP clients). Don't use `@app.on_event`.
- One `APIRouter` per bounded context with a `prefix`, `tags`, and dependencies for auth.
- Schemas (Pydantic v2) live in `schemas/` and are separate from ORM models. Request models use `extra="forbid"`; response models are explicit via `response_model` or the return type.

## Rules
1. Thin route handlers. Parse with the schema, call a service, map the result. Business logic never lives in the route.
2. Use dependencies (`Depends`) for:
   - the DB session (unit of work, commit/rollback in the dependency);
   - the current user/principal;
   - permissions;
   - settings.
   Use `Annotated[T, Depends(...)]` aliases.
3. Async all the way. Use `async def` routes with an async driver (asyncpg / psycopg 3 async) and `AsyncSession`. If a library is sync-only, use a plain `def` route (FastAPI runs it in a threadpool). Never call sync I/O inside `async def`.
4. Errors. Register exception handlers that map domain errors to RFC 9457 problem+json in one place. Never raise `HTTPException` from services.
5. Contract.
   - OpenAPI is exported to `contracts/openapi.json` by a script; CI fails if it is stale.
   - Run oasdiff breaking-change checks on PRs.
   - Set a stable `operation_id` (e.g. generate it from the route name) so generated clients have stable names.
6. Security.
   - Use OAuth2/OIDC via a proven library and verify JWTs with audience, issuer and expiry checks.
   - Set a CORS allow-list (not `*` with credentials).
   - Apply rate limits at the gateway or middleware.
   - Limit request body size at the proxy.
7. Background work. `BackgroundTasks` is only for best-effort jobs. Anything that must not be lost goes to a queue with an outbox.
8. Observability. Add OpenTelemetry FastAPI instrumentation, a request-ID middleware, and `/healthz` (liveness) plus `/readyz` (checks the DB).

## Testing
- Use `httpx.AsyncClient(transport=ASGITransport(app=app))` with `app.dependency_overrides` for auth/clock. Use a real DB through testcontainers, with a transaction rolled back per test.
- Contract: `schemathesis run contracts/openapi.json --url …` (or `from_asgi`) in CI on the API job.

## Pitfalls
- Creating the DB engine per request; forgetting `await`; returning ORM objects without a response model (data leaks).
- Mixing sync SQLAlchemy sessions into async routes.
- Using `from_attributes` without an explicit response model, which exposes internal fields.
