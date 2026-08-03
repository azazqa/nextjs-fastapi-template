-- Add commission column to product_alias_dicts
-- NOTE: Run manually in Postgres. This repo forbids creating new alembic migration files.

BEGIN;

ALTER TABLE product_alias_dicts
  ADD COLUMN IF NOT EXISTS commission integer NULL DEFAULT 0;

-- Ensure existing NULLs become 0 for consistent behavior
UPDATE product_alias_dicts
SET commission = 0
WHERE commission IS NULL;

COMMIT;

