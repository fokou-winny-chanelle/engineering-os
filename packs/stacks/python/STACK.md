---
id: python
title: Python (any framework)
kind: stack
mode: files
when: editing Python code, tests or pyproject
description: Python stack conventions - uv, ruff, type checking, pytest, packaging, async and typing rules. Applies to any Python service, library or script.
globs: ["**/*.py", "**/*.pyi", "**/pyproject.toml", "**/uv.lock", "**/requirements*.txt"]
markers: ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile", "uv.lock"]
contains: []
requires: []
fast_check: "uv run ruff check --fix . && uv run ruff format ."
full_check: "uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q"
ci: python
---
# Stack: Python

## Toolchain (pins live in `versions.toml` / lockfile)
| Job | Tool | Command |
|---|---|---|
| Env + deps | uv (lockfile `uv.lock` committed) | `uv sync`, `uv add pkg`, `uv run …` |
| Lint + format | ruff | `uv run ruff check --fix .`, `uv run ruff format .` |
| Types | mypy --strict (or pyright; pick one per repo, ADR) | `uv run mypy .` |
| Tests | pytest (+ pytest-cov, hypothesis, testcontainers) | `uv run pytest -q` |
| Boundaries | import-linter (`[tool.importlinter]`) | `uv run lint-imports` |
| Deps audit | pip-audit | `uv export --no-hashes -o /tmp/req.txt && uvx pip-audit -r /tmp/req.txt` |

Never call bare `pip install` or `python` outside `uv run`. Don't edit `uv.lock` by hand.

## Layout
`src/<package>/` with `api/` (transport), `services/` (use-cases), `domain/` (pure), `adapters/` (DB, HTTP, queue) and `settings.py`, per the backend pack layering. Tests mirror it: `tests/unit`, `tests/integration`, `tests/contract`.

## Rules
1. Types everywhere. Public functions are fully annotated. Never use `Any` in signatures. Use `TypedDict`, `Protocol` and `dataclass(frozen=True, slots=True)` or pydantic models at the edges. No `# type: ignore` without an error code and a reason.
2. Ruff config. Start from `select = ["E","F","W","I","B","UP","S","ASYNC","RUF","PT","SIM","N","DTZ","T20"]`. Banned in prod code: `print` (T20) and naive datetimes (DTZ). Don't add `# noqa` without a code and a reason.
3. Money: use `decimal.Decimal` with an explicit `quantize(..., rounding=ROUND_HALF_EVEN)` (or the rule from the spec), or `int` minor units. Never `float`.
4. Time: `datetime.now(tz=UTC)` only. Use `zoneinfo` for display.
5. Errors. Define a domain exception hierarchy in `domain/errors.py`. Never write `except Exception: pass`. Use `raise … from e`.
6. Async.
   - No blocking I/O (`requests`, `time.sleep`, sync DB drivers) inside `async def`.
   - Use `httpx.AsyncClient` with timeouts.
   - Use `asyncio.TaskGroup` for fan-out.
   - Run CPU-bound work via `anyio.to_thread` or a worker queue.
7. Settings: use `pydantic-settings` (one `Settings` class). Fail at startup when a required env var is missing.
8. DB:
   - SQLAlchemy 2.x typed ORM (`Mapped[...]`) or Core.
   - Alembic migrations, with `alembic check` in CI to detect drift.
   - Sessions are scoped per request or unit of work.
9. Logging: `structlog` or stdlib `logging` with a JSON formatter. Include the request ID, no PII, and use `logger.exception` in handlers.
10. Tests:
    - Use pytest fixtures (function scope by default), factories, and `freezegun`/`time-machine` for the clock.
    - Run integration tests against real Postgres via testcontainers.
    - Use `pytest -x --lf` while iterating.

## Pitfalls the AI often makes
- Writes Pydantic v1 syntax (`class Config`, `.dict()`, `validator`) instead of v2 (`model_config`, `.model_dump()`, `field_validator`).
- Uses SQLAlchemy 1.x `Query` API instead of `select()`.
- Mutable default args. Catching broad exceptions in tests. Patching the wrong import path in mocks (patch where the name is used).
- Invents packages. Verify on PyPI before `uv add`.
