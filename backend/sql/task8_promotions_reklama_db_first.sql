-- Run after task5/task6 if they are still pending.
-- This migration prepares the promotions table for DB-first promo content,
-- including reklama items stored in the same table via class_name.

BEGIN;

ALTER TABLE promotions
    ADD COLUMN IF NOT EXISTS text TEXT NOT NULL DEFAULT '';

ALTER TABLE promotions
    ADD COLUMN IF NOT EXISTS link TEXT NOT NULL DEFAULT '';

COMMIT;
