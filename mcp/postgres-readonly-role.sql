-- Read-only role for the Postgres MCP server (engineering-os). DEV / LOCAL DATABASES ONLY.
-- Run as the database owner or a superuser, e.g.:
--   psql "postgresql://postgres@localhost:5432/myapp_dev" -v ON_ERROR_STOP=1 \
--        -v dbname=myapp_dev -v pw="'choose-a-local-password'" -f mcp/postgres-readonly-role.sql
-- Then in ~/.config/engineering-os/secrets.env (never in git):
--   POSTGRES_MCP_URL=postgresql://eos_mcp_ro:choose-a-local-password@localhost:5432/myapp_dev
-- Re-run after adding new schemas (the GRANT ... ON ALL TABLES lines cover existing tables only;
-- ALTER DEFAULT PRIVILEGES covers tables created later by the role that runs this script).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eos_mcp_ro') THEN
    CREATE ROLE eos_mcp_ro LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
      CONNECTION LIMIT 5;
  END IF;
END
$$;
ALTER ROLE eos_mcp_ro PASSWORD :pw;

-- Layer 1: every session and transaction of this role is read-only, and long queries are cancelled.
ALTER ROLE eos_mcp_ro SET default_transaction_read_only = on;
ALTER ROLE eos_mcp_ro SET statement_timeout = '30s';
ALTER ROLE eos_mcp_ro SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE eos_mcp_ro SET lock_timeout = '2s';

-- Layer 2: privileges. Read data, nothing else.
GRANT CONNECT ON DATABASE :"dbname" TO eos_mcp_ro;
REVOKE CREATE ON SCHEMA public FROM eos_mcp_ro;
GRANT USAGE ON SCHEMA public TO eos_mcp_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO eos_mcp_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO eos_mcp_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO eos_mcp_ro;
-- More schemas: repeat the USAGE / SELECT / DEFAULT PRIVILEGES lines with the schema name.

-- Health checks and top queries read statistics views (pg_stat_statements, pg_stat_activity
-- of other sessions). pg_read_all_stats is read-only; skip it if you do not want that.
GRANT pg_read_all_stats TO eos_mcp_ro;

-- Check (should print: on | 30s and fail with "read-only transaction"):
--   SET ROLE eos_mcp_ro; SHOW default_transaction_read_only; SHOW statement_timeout;
--   CREATE TABLE eos_should_fail(x int);  RESET ROLE;
