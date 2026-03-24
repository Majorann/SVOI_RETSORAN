CREATE TABLE IF NOT EXISTS promotions (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    lore TEXT NOT NULL DEFAULT '',
    class_name TEXT NOT NULL DEFAULT 'akciya',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100,
    condition TEXT NOT NULL DEFAULT '',
    reward TEXT NOT NULL DEFAULT '',
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

CREATE INDEX IF NOT EXISTS idx_promotions_active_priority
    ON promotions(active, priority DESC, id ASC);

CREATE INDEX IF NOT EXISTS idx_promotions_window
    ON promotions(start_at, end_at);

CREATE INDEX IF NOT EXISTS idx_promotion_applications_promo_user_applied
    ON promotion_applications(promotion_id, user_id, applied_at DESC);

CREATE INDEX IF NOT EXISTS idx_promotion_applications_order_id
    ON promotion_applications(order_id);
