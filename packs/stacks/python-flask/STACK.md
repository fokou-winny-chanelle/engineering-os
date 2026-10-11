---
id: python-flask
title: Flask services
kind: stack
mode: files
when: editing a Flask app (blueprints, views, extensions)
description: Flask conventions - app factory, blueprints, request validation (APIFlask or flask-smorest), SQLAlchemy 2 sessions, error handlers, OpenAPI, testing with the test client.
globs: ["**/blueprints/**", "**/views/**", "**/app/__init__.py", "**/wsgi.py", "**/extensions.py"]
markers: ["pyproject.toml", "requirements.txt", "uv.lock"]
contains: ["flask"]
requires: ["python"]
fast_check: ""
full_check: ""
ci: ""
---
# Stack: Flask (adds to Python pack)

## Structure
- App factory: `create_app(config=None)` in `app/__init__.py`. Extensions are created in `extensions.py` and initialised with `init_app`. No global app object imported by other modules.
- One Blueprint per bounded context. Views are thin; services and domain follow the backend pack layering.
- Config: a typed settings object loaded from env (pydantic-settings), mapped into `app.config`. Never hard-code secrets or the `SECRET_KEY`.

## Rules
1. Validate at the edge. Use APIFlask or flask-smorest (choose one in an ADR) with schemas for input and output, which also gives you OpenAPI. Don't use `request.json[...]` without validation.
2. Errors. Use `@app.errorhandler(DomainError)` to map domain errors to problem+json in one place. Turn off debug mode outside local development (the Werkzeug debugger allows remote code execution).
3. DB.
   - Use SQLAlchemy 2.x (Flask-SQLAlchemy 3.x or plain SQLAlchemy with a scoped session) and Alembic/Flask-Migrate.
   - Commit or roll back per request in a teardown handler or service unit of work.
   - Never leave a session open across requests.
4. Sync by default. Flask's async views still run in a worker thread per request. For heavy concurrency or websockets, don't fight Flask; document the choice. Run with gunicorn (sync or gthread workers), with the worker count sized and set in config.
5. Security.
   - Flask-Login or OIDC via a proven library.
   - CSRF protection for cookie-session forms (Flask-WTF).
   - Secure cookie flags (`SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE`).
   - CORS allow-list.
   - Security headers (e.g. Flask-Talisman or the proxy).
6. Contract. Export the OpenAPI spec to `contracts/openapi.json` via a CLI command (`flask spec` in APIFlask; flask-smorest has `flask openapi write`). CI checks it is fresh and runs oasdiff.
7. Observability. Add OpenTelemetry Flask instrumentation, a request-ID in `g`, JSON logs, and `/healthz` plus `/readyz`.

## Testing
- Use pytest fixtures `app` (factory with test config) → `client = app.test_client()`. Use a real DB via testcontainers, with a transaction per test. `app.test_request_context()` covers helpers.

## Pitfalls
- Circular imports from a global `app`; using `flask run` in production; leaking `debug=True`; storing per-user state in module globals; forgetting `app.app_context()` in CLI and tests.
