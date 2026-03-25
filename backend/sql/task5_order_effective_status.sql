-- Run this before task6_normalize_time_fields.sql if both migrations are pending.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS effective_status TEXT NOT NULL DEFAULT 'preparing';

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS effective_status_updated_at TEXT NOT NULL DEFAULT '';

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS is_delivery_overdue BOOLEAN NOT NULL DEFAULT FALSE;

WITH normalized AS (
    SELECT
        id,
        LOWER(COALESCE(order_type, 'dine_in')) AS normalized_order_type,
        LOWER(COALESCE(NULLIF(status, ''), 'preparing')) AS normalized_status,
        COALESCE(created_at, '') AS normalized_created_at,
        COALESCE(delivery_eta_minutes, 20) AS normalized_eta_minutes,
        COALESCE(effective_status_updated_at, '') AS previous_effective_status_updated_at
    FROM orders
    WHERE COALESCE(created_at, '') = ''
       OR created_at ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T'
),
computed AS (
    SELECT
        id,
        CASE
            WHEN normalized_status = 'cancelled' THEN 'cancelled'
            WHEN normalized_order_type = 'delivery'
                AND normalized_created_at <> ''
                AND normalized_created_at::timestamp + make_interval(mins => normalized_eta_minutes) <= NOW() THEN 'served'
            WHEN normalized_order_type = 'delivery'
                AND normalized_status IN ('ready', 'delivering') THEN 'delivering'
            WHEN normalized_order_type = 'delivery'
                AND normalized_status IN ('preparing', 'cooking') THEN 'cooking'
            WHEN normalized_order_type <> 'delivery'
                AND normalized_created_at <> ''
                AND normalized_created_at::timestamp + INTERVAL '90 minutes' <= NOW() THEN 'served'
            WHEN normalized_order_type <> 'delivery'
                AND normalized_created_at <> ''
                AND normalized_created_at::timestamp + INTERVAL '45 minutes' <= NOW() THEN 'delivering'
            WHEN normalized_order_type <> 'delivery'
                AND normalized_created_at <> ''
                AND normalized_created_at::timestamp + INTERVAL '30 minutes' <= NOW() THEN 'ready'
            WHEN normalized_order_type <> 'delivery'
                AND normalized_created_at <> ''
                AND normalized_created_at::timestamp + INTERVAL '15 minutes' <= NOW() THEN 'cooking'
            ELSE normalized_status
        END AS new_effective_status,
        CASE
            WHEN previous_effective_status_updated_at <> '' THEN previous_effective_status_updated_at
            ELSE NOW()::timestamp(0)::text
        END AS new_effective_status_updated_at,
        CASE
            WHEN normalized_order_type <> 'delivery' THEN FALSE
            WHEN normalized_created_at = '' THEN FALSE
            WHEN (
                CASE
                    WHEN normalized_status = 'cancelled' THEN 'cancelled'
                    WHEN normalized_created_at::timestamp + make_interval(mins => normalized_eta_minutes) <= NOW() THEN 'served'
                    WHEN normalized_status IN ('ready', 'delivering') THEN 'delivering'
                    WHEN normalized_status IN ('preparing', 'cooking') THEN 'cooking'
                    ELSE normalized_status
                END
            ) IN ('served', 'cancelled') THEN FALSE
            ELSE normalized_created_at::timestamp + make_interval(mins => normalized_eta_minutes) < NOW()
        END AS new_is_delivery_overdue
    FROM normalized
)
UPDATE orders AS target
SET
    effective_status = computed.new_effective_status,
    effective_status_updated_at = computed.new_effective_status_updated_at,
    is_delivery_overdue = computed.new_is_delivery_overdue
FROM computed
WHERE computed.id = target.id;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_effective_status_created
    ON orders(effective_status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_delivery_overdue_created
    ON orders(is_delivery_overdue, created_at DESC)
    WHERE order_type = 'delivery';
