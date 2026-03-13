-- Neon bootstrap for "SVOI_RETSORAN"
-- Run once in Neon SQL Editor.

-- Example table from your friend (can be used for analytics/reporting)
CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    guests INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Main app storage (compatible with current backend code)
CREATE TABLE IF NOT EXISTS app_state (
    state_key TEXT PRIMARY KEY,
    state_value JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO app_state(state_key, state_value)
VALUES
    ('users', '[]'::jsonb),
    ('bookings', '[]'::jsonb),
    ('orders', '[]'::jsonb)
ON CONFLICT (state_key) DO NOTHING;
