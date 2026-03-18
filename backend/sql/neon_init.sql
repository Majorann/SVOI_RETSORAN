-- Neon bootstrap for "SVOI_RETSORAN"
-- Run once in Neon SQL Editor.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_cards (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brand TEXT NOT NULL DEFAULT 'MIR',
    last4 TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    holder TEXT,
    expiry TEXT,
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, created_at, last4)
);

CREATE TABLE IF NOT EXISTS bookings (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    table_id INTEGER NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, table_id, booking_date, booking_time, created_at)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_type TEXT NOT NULL DEFAULT 'dine_in',
    status TEXT NOT NULL DEFAULT 'preparing',
    created_at TEXT NOT NULL DEFAULT '',
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
    cancelled_at TEXT NOT NULL DEFAULT ''
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

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items(order_id);
