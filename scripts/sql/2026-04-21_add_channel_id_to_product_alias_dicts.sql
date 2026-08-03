-- Add channel-aware product alias dictionaries
-- Goal:
-- - product_alias_dicts.channel_id (nullable) to scope aliases by channel
-- - allow same alias across different channels
-- - keep a single "global" alias when channel_id IS NULL
--
-- NOTE:
-- - Run this manually in Postgres.
-- - This repo forbids creating new alembic migration files.

BEGIN;

-- 1) Add column (nullable for backwards compatibility)
ALTER TABLE product_alias_dicts
  ADD COLUMN IF NOT EXISTS channel_id uuid NULL;

-- 2) FK (optional, but recommended)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'product_alias_dicts_channel_id_fkey'
  ) THEN
    ALTER TABLE product_alias_dicts
      ADD CONSTRAINT product_alias_dicts_channel_id_fkey
      FOREIGN KEY (channel_id) REFERENCES channels(id);
  END IF;
END $$;

-- 3) Drop legacy UNIQUE(alias) if it exists
DO $$
DECLARE
  c_name text;
BEGIN
  SELECT conname INTO c_name
  FROM pg_constraint
  WHERE conrelid = 'product_alias_dicts'::regclass
    AND contype = 'u'
    AND pg_get_constraintdef(oid) ILIKE '%(alias)%'
  LIMIT 1;

  IF c_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE product_alias_dicts DROP CONSTRAINT %I', c_name);
  END IF;
END $$;

-- 4) Unique per channel (channel_id NOT NULL)
CREATE UNIQUE INDEX IF NOT EXISTS ux_product_alias_dicts_channel_alias
  ON product_alias_dicts (channel_id, alias)
  WHERE channel_id IS NOT NULL;

-- 5) Unique for "global" aliases (channel_id IS NULL)
CREATE UNIQUE INDEX IF NOT EXISTS ux_product_alias_dicts_global_alias
  ON product_alias_dicts (alias)
  WHERE channel_id IS NULL;

-- 6) Helpful index for matching
CREATE INDEX IF NOT EXISTS ix_product_alias_dicts_alias
  ON product_alias_dicts (alias);

COMMIT;

