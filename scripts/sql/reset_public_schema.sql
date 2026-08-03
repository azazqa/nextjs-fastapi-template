-- Reset ONLY the public schema (tables/types/functions/views/sequences/etc).
-- Intended for destructive operational reset. Review before running.
--
-- What it does:
-- 1) Drops schema "public" with CASCADE (removes all objects under it, including ENUM types).
-- 2) Recreates schema "public".
-- 3) Restores default privileges commonly expected by tools.
--
-- What it does NOT do:
-- - Drop roles/users/databases
-- - Recreate tables (run Alembic migrations manually after this)

BEGIN;

-- Terminate other connections to reduce "being accessed" issues.
-- (Requires permission; if it fails, you can remove this block.)
DO $$
DECLARE
  dbname text := current_database();
BEGIN
  PERFORM pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = dbname
    AND pid <> pg_backend_pid();
EXCEPTION
  WHEN insufficient_privilege THEN
    -- ignore
    NULL;
END $$;

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

-- Typical defaults
GRANT USAGE ON SCHEMA public TO PUBLIC;
GRANT ALL ON SCHEMA public TO CURRENT_USER;

COMMIT;

