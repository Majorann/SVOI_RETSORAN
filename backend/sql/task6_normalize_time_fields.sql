-- Task 6: normalize legacy TEXT timestamps to typed Postgres columns.
-- Assumption:
-- - legacy naive datetime strings are stored in UTC
-- - blank strings mean "missing value"
--
-- Run this after task5_order_effective_status.sql if task 5 has not been applied yet.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM users
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid users.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM user_cards
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid user_cards.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM bookings
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid bookings.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM orders
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid orders.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM orders
        WHERE BTRIM(COALESCE(cancelled_at, '')) <> ''
          AND BTRIM(COALESCE(cancelled_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid orders.cancelled_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM orders
        WHERE BTRIM(COALESCE(effective_status_updated_at, '')) <> ''
          AND BTRIM(COALESCE(effective_status_updated_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid orders.effective_status_updated_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM admin_users
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid admin_users.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM admin_actions
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid admin_actions.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM menu_items
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid menu_items.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM menu_items
        WHERE BTRIM(COALESCE(updated_at, '')) <> ''
          AND BTRIM(COALESCE(updated_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid menu_items.updated_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promotions
        WHERE BTRIM(COALESCE(start_at, '')) <> ''
          AND BTRIM(COALESCE(start_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid promotions.start_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promotions
        WHERE BTRIM(COALESCE(end_at, '')) <> ''
          AND BTRIM(COALESCE(end_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid promotions.end_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promotions
        WHERE BTRIM(COALESCE(created_at, '')) <> ''
          AND BTRIM(COALESCE(created_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid promotions.created_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promotions
        WHERE BTRIM(COALESCE(updated_at, '')) <> ''
          AND BTRIM(COALESCE(updated_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid promotions.updated_at values detected';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promotion_applications
        WHERE BTRIM(COALESCE(applied_at, '')) <> ''
          AND BTRIM(COALESCE(applied_at, '')) !~ '^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?(?:[+-][0-9]{2}:[0-9]{2}|Z)?$'
    ) THEN
        RAISE EXCEPTION 'Invalid promotion_applications.applied_at values detected';
    END IF;
END $$;

UPDATE users
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE user_cards
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE bookings
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE orders
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE admin_users
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE admin_actions
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE menu_items
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE menu_items
SET updated_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(updated_at, '')) = '';

UPDATE promotions
SET created_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(created_at, '')) = '';

UPDATE promotions
SET updated_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(updated_at, '')) = '';

UPDATE promotion_applications
SET applied_at = NOW()::timestamp(0)::text
WHERE BTRIM(COALESCE(applied_at, '')) = '';

ALTER TABLE orders
    ALTER COLUMN cancelled_at DROP NOT NULL,
    ALTER COLUMN cancelled_at DROP DEFAULT,
    ALTER COLUMN effective_status_updated_at DROP NOT NULL,
    ALTER COLUMN effective_status_updated_at DROP DEFAULT;

ALTER TABLE promotions
    ALTER COLUMN start_at DROP NOT NULL,
    ALTER COLUMN start_at DROP DEFAULT,
    ALTER COLUMN end_at DROP NOT NULL,
    ALTER COLUMN end_at DROP DEFAULT;

ALTER TABLE users
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE user_cards
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE bookings
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE orders
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN cancelled_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN BTRIM(COALESCE(cancelled_at, '')) = '' THEN NULL
        WHEN cancelled_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN cancelled_at::timestamptz
        ELSE (cancelled_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN effective_status_updated_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN BTRIM(COALESCE(effective_status_updated_at, '')) = '' THEN NULL
        WHEN effective_status_updated_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN effective_status_updated_at::timestamptz
        ELSE (effective_status_updated_at::timestamp AT TIME ZONE 'UTC')
    END;

ALTER TABLE admin_users
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE admin_actions
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE menu_items
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN updated_at DROP DEFAULT,
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN updated_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN updated_at::timestamptz
        ELSE (updated_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE promotions
    ALTER COLUMN start_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN BTRIM(COALESCE(start_at, '')) = '' THEN NULL
        WHEN start_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN start_at::timestamptz
        ELSE (start_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN end_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN BTRIM(COALESCE(end_at, '')) = '' THEN NULL
        WHEN end_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN end_at::timestamptz
        ELSE (end_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at DROP DEFAULT,
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN created_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN created_at::timestamptz
        ELSE (created_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN updated_at DROP DEFAULT,
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN updated_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN updated_at::timestamptz
        ELSE (updated_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE promotion_applications
    ALTER COLUMN applied_at DROP DEFAULT,
    ALTER COLUMN applied_at TYPE TIMESTAMPTZ
    USING CASE
        WHEN applied_at ~ '([+-][0-9]{2}:[0-9]{2}|Z)$' THEN applied_at::timestamptz
        ELSE (applied_at::timestamp AT TIME ZONE 'UTC')
    END,
    ALTER COLUMN applied_at SET DEFAULT NOW(),
    ALTER COLUMN applied_at SET NOT NULL;

COMMIT;
