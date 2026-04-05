-- Neon bootstrap for "SVOI_RETSORAN"
-- Run once in Neon SQL Editor.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_cards (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brand TEXT NOT NULL DEFAULT 'MIR',
    last4 TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    holder TEXT,
    expiry TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, created_at, last4)
);

CREATE TABLE IF NOT EXISTS bookings (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    table_id INTEGER NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, table_id, booking_date, booking_time, created_at)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_type TEXT NOT NULL DEFAULT 'dine_in',
    status TEXT NOT NULL DEFAULT 'preparing',
    effective_status TEXT NOT NULL DEFAULT 'preparing',
    effective_status_updated_at TIMESTAMPTZ,
    is_delivery_overdue BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    items_total INTEGER NOT NULL DEFAULT 0,
    points_applied INTEGER NOT NULL DEFAULT 0,
    payable_total INTEGER NOT NULL DEFAULT 0,
    bonus_earned INTEGER NOT NULL DEFAULT 0,
    comment TEXT NOT NULL DEFAULT '',
    serving_mode TEXT NOT NULL DEFAULT '',
    serving_label TEXT NOT NULL DEFAULT '',
    serving_time TEXT NOT NULL DEFAULT '',
    booking_table_id INTEGER,
    booking_date DATE,
    booking_time TIME,
    booking_status TEXT NOT NULL DEFAULT '',
    payment_card_brand TEXT NOT NULL DEFAULT '',
    payment_card_last4 TEXT NOT NULL DEFAULT '',
    payment_card_expiry TEXT NOT NULL DEFAULT '',
    delivery_name TEXT NOT NULL DEFAULT '',
    delivery_phone TEXT NOT NULL DEFAULT '',
    delivery_street TEXT NOT NULL DEFAULT '',
    delivery_house TEXT NOT NULL DEFAULT '',
    delivery_apartment TEXT NOT NULL DEFAULT '',
    delivery_entrance TEXT NOT NULL DEFAULT '',
    delivery_floor TEXT NOT NULL DEFAULT '',
    delivery_intercom TEXT NOT NULL DEFAULT '',
    delivery_comment TEXT NOT NULL DEFAULT '',
    delivery_address TEXT NOT NULL DEFAULT '',
    delivery_eta_minutes INTEGER NOT NULL DEFAULT 20,
    cancelled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    qty INTEGER NOT NULL DEFAULT 0,
    photo TEXT,
    PRIMARY KEY (order_id, position)
);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_mode TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_label TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_time TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS effective_status TEXT NOT NULL DEFAULT 'preparing';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS effective_status_updated_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_delivery_overdue BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_table_id INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_date DATE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_time TIME;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_status TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_brand TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_last4 TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_expiry TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_user_cards_user_id
    ON user_cards(user_id);

CREATE INDEX IF NOT EXISTS idx_bookings_user_date_time
    ON bookings(user_id, booking_date, booking_time);

CREATE INDEX IF NOT EXISTS idx_orders_user_created
    ON orders(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON orders(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_status_created
    ON orders(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_type_created
    ON orders(order_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_effective_status_created
    ON orders(effective_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_delivery_overdue_created
    ON orders(is_delivery_overdue, created_at DESC)
    WHERE order_type = 'delivery';

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items(order_id);

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    lore TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    photo_path TEXT NOT NULL DEFAULT '',
    portion_label TEXT NOT NULL DEFAULT '',
    popularity INTEGER NOT NULL DEFAULT 0,
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS promotions (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    lore TEXT NOT NULL DEFAULT '',
    class_name TEXT NOT NULL DEFAULT 'akciya',
    text TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100,
    condition TEXT NOT NULL DEFAULT '',
    reward TEXT NOT NULL DEFAULT '',
    dsl_version INTEGER,
    notify TEXT NOT NULL DEFAULT '',
    reward_mode TEXT NOT NULL DEFAULT 'once',
    limit_per_order INTEGER,
    limit_per_user_per_day INTEGER,
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    photo_path TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS promotion_applications (
    id BIGSERIAL PRIMARY KEY,
    promotion_id BIGINT NOT NULL REFERENCES promotions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_count INTEGER NOT NULL DEFAULT 0,
    reward_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE promotions ADD COLUMN IF NOT EXISTS text TEXT NOT NULL DEFAULT '';
ALTER TABLE promotions ADD COLUMN IF NOT EXISTS link TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_menu_items_active_type
    ON menu_items(active, type, id);

CREATE INDEX IF NOT EXISTS idx_menu_items_featured
    ON menu_items(featured, popularity DESC, id ASC);

CREATE INDEX IF NOT EXISTS idx_admin_actions_entity_created
    ON admin_actions(entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_actions_admin_created
    ON admin_actions(admin_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_actions_action_created
    ON admin_actions(action_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_promotions_active_priority
    ON promotions(active, priority DESC, id ASC);

CREATE INDEX IF NOT EXISTS idx_promotions_window
    ON promotions(start_at, end_at);

CREATE INDEX IF NOT EXISTS idx_promotion_applications_promo_user_applied
    ON promotion_applications(promotion_id, user_id, applied_at DESC);

CREATE INDEX IF NOT EXISTS idx_promotion_applications_order_id
    ON promotion_applications(order_id);
