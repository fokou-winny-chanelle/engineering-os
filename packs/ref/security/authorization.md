---
id: security/authorization
title: Authorization (RBAC/ABAC/ReBAC, IDOR/BOLA, mass assignment)
area: security
read_when: adding roles/permissions, multi-tenancy, sharing, admin tools, any endpoint taking an object id, or reviewing for IDOR/BOLA
verified: 2026-10-10
revisit_days: 365
sources: ["https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html", "https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html", "https://api-security.owasp.org/editions/2023/en/0x11-t10/", "https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/", "https://openfga.dev/docs/fga", "https://cedarpolicy.com/", "https://www.openpolicyagent.org/docs", "https://www.postgresql.org/docs/current/ddl-rowsecurity.html", "https://csrc.nist.gov/pubs/sp/800/162/upd2/final"]
---
# Authorization (RBAC/ABAC/ReBAC, IDOR/BOLA, mass assignment)

Broken access control is A01 in the OWASP Top 10:2025, and three of the OWASP API Security Top 10 2023 are authorization bugs: **API1 Broken Object Level Authorization (BOLA, a.k.a. IDOR)**, **API3 Broken Object Property Level Authorization (BOPLA: mass assignment and excessive data exposure)** and **API5 Broken Function Level Authorization (BFLA: user reaches admin functions)**. Scanners find few of these; tests and design do.

## Decision guide

**Principles (OWASP Authorization cheat sheet):** least privilege; **deny by default**; validate permissions **on every request**, server-side, at the resource; exit safely (fail closed) on errors; log denials; unit and integration tests for the authorization logic.

**Choose the model:**

| Model | Rule shape | Fits | Tools |
|---|---|---|---|
| RBAC | user → role → permission | small fixed set of roles (admin, staff, customer) | framework permissions, a `permissions` table |
| ABAC (NIST SP 800-162) | policy over attributes of subject, resource, action, environment | rules like "teller may approve < limit, in own branch, in business hours" | Cedar, OPA/Rego, in-code policy functions |
| ReBAC (Zanzibar-style) | relationships: user is `editor` of doc, doc in folder, folder owned by org | sharing, nested orgs/teams, Google-Docs-like permissions | OpenFGA, SpiceDB, Cedar entities |

OWASP recommends preferring ABAC/ReBAC over plain RBAC once rules depend on ownership or context; most products end up as RBAC for functions plus ownership/tenant checks for objects. Start with **one policy module** (`authz.can(actor, action, resource)`) called from every handler; adopt an engine only when rules outgrow code.

**Multi-tenancy:** every row carries `tenant_id`; every query is scoped by the tenant from the **authenticated session**, never from the request body or URL. Defence in depth: PostgreSQL row-level security (`ENABLE ROW LEVEL SECURITY` + policies on `current_setting('app.tenant_id')`). Note: superusers and roles with `BYPASSRLS` always bypass RLS, and table owners bypass it unless you use `FORCE ROW LEVEL SECURITY`, so the app must connect as a non-owner role.

**Object-level (BOLA/IDOR):**
- Load objects through the actor's scope: `Invoice.objects.filter(account=request.user.account).get(id=pk)` or `WHERE id = $1 AND owner_id = $2`, not `get(id=pk)` and check later (or never).
- Random UUIDs make guessing harder but are **not** authorization (OWASP IDOR sheet). Check access even for unguessable ids.
- Return 404 for objects the actor may not see (avoids confirming existence), 403 for visible-but-forbidden actions; be consistent.
- Cover every path to the object: list, search, export, file download URLs (static resources need checks too: signed, short-lived URLs), GraphQL nested resolvers, websockets, background job callbacks.

**Property-level (BOPLA / mass assignment):**
- Bind requests to explicit input DTOs/schemas with an allow-list of writable fields; never `Model(**request.json)` or `update(req.body)`.
- Fields like `role`, `is_admin`, `balance`, `tenant_id`, `price`, `status`, `verified` are never client-writable.
- Serialize responses through explicit output schemas so internal fields (password hash, KYC data, other users' emails) never leak.

**Function-level (BFLA):** admin and support endpoints live behind a separate router/middleware with its own role check and MFA; do not rely on hiding buttons in the UI or on unguessable URLs.

## Examples

Authorization matrix test (template: `eos scaffold security-tests` → `tests/security/test_authz_matrix.py`): one parametrized test enumerates (actor, action, resource) → expected status.

| Actor | GET own invoice | GET other user's invoice | GET other tenant's invoice | PATCH `role` on self | POST /admin/refund |
|---|---|---|---|---|---|
| anonymous | 401 | 401 | 401 | 401 | 401 |
| customer A | 200 | 404 | 404 | 400/403 (field ignored or rejected) | 403 |
| support (tenant 1) | 200 | 200 | 404 | 403 | 403 |
| admin (tenant 1, MFA) | 200 | 200 | 404 | 200 (audited) | 200 (audited) |

## Anti-patterns
- Authorization only in the frontend, or only on the list endpoint but not on detail/update/delete.
- Trusting `user_id`, `tenant_id` or `role` from the request body, query, header or JWT claim that the client can influence.
- `if user.role == "admin"` strings scattered across handlers instead of one policy function.
- Caching an authorization decision across users (shared cache keys without actor/tenant).
- RLS enabled but the app connects as the table owner or a `BYPASSRLS` role.
- New endpoint added without adding its rows to the authorization matrix test.

## Checks
- [ ] Authorization matrix test covers every endpoint × role, including cross-user and cross-tenant cases; CI fails if a route has no matrix row (list routes from the app's router).
- [ ] Every data-access query for tenant data is scoped by session tenant (grep/semgrep for unscoped `get(id=` in handlers; RLS as backstop).
- [ ] Input and output schemas are explicit; a test sends `role`, `is_admin`, `tenant_id` in a PATCH and asserts they are unchanged.
- [ ] Admin routes require admin role + MFA in middleware; a test calls them as a normal user (403).
- [ ] Authorization denials are logged with actor, action, resource id and outcome.

## Sources
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html (least privilege, deny by default, every request, prefer ABAC/ReBAC, tests)
- https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html
- https://api-security.owasp.org/editions/2023/en/0x11-t10/ (API1 BOLA, API3 BOPLA, API5 BFLA)
- https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/
- https://openfga.dev/docs/fga
- https://cedarpolicy.com/
- https://www.openpolicyagent.org/docs
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html (RLS, `BYPASSRLS`, `FORCE ROW LEVEL SECURITY`)
- https://csrc.nist.gov/pubs/sp/800/162/upd2/final (ABAC)
