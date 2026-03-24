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

CREATE INDEX IF NOT EXISTS idx_menu_items_active_type
    ON menu_items(active, type, id);

CREATE INDEX IF NOT EXISTS idx_menu_items_featured
    ON menu_items(featured, popularity DESC, id ASC);
