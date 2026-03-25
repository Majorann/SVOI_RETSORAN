import json
import os
import threading
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path

import psycopg
from config import MENU_ITEMS_PATH, MENU_PHOTO_NAMES, PROMO_ITEMS_PATH
from services.business_logic import current_time_value
from services.order_status import apply_persisted_status_fields_value


_SCHEMA_READY = False
_SCHEMA_LOCK = threading.Lock()
_LOCAL = threading.local()
_IS_HF_SPACE = bool(os.getenv("SPACE_ID") or os.getenv("HF_SPACE_ID"))


def _env_int(name, default):
    value = (os.getenv(name) or "").strip()
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


DB_OPERATION_RETRIES = max(1, _env_int("DB_OPERATION_RETRIES", 3))
DB_RETRY_DELAY_SECONDS = max(1, _env_int("DB_RETRY_DELAY_SECONDS", 2))
PG_CONNECT_TIMEOUT_SECONDS = max(
    1,
    _env_int("PG_CONNECT_TIMEOUT_SECONDS", 5 if _IS_HF_SPACE else 10),
)


def _database_url():
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _connect():
    return psycopg.connect(
        _database_url(),
        autocommit=True,
        connect_timeout=PG_CONNECT_TIMEOUT_SECONDS,
    )


def _get_conn():
    conn = getattr(_LOCAL, "conn", None)
    try:
        if conn is not None and not conn.closed:
            return conn
    except Exception:
        pass
    conn = _connect()
    _LOCAL.conn = conn
    return conn


def _reset_conn():
    conn = getattr(_LOCAL, "conn", None)
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass
    _LOCAL.conn = None


def _execute_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            note TEXT NOT NULL DEFAULT ''
        );
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS promotion_applications (
            id BIGSERIAL PRIMARY KEY,
            promotion_id BIGINT NOT NULL REFERENCES promotions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_count INTEGER NOT NULL DEFAULT 0,
            reward_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        """
    )
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_mode TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_label TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_time TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS service_fee INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS effective_status TEXT NOT NULL DEFAULT 'preparing'")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS effective_status_updated_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_delivery_overdue BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_table_id INTEGER")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_date DATE")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_time TIME")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_status TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_brand TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_last4 TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_expiry TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ALTER COLUMN cancelled_at DROP NOT NULL")
    cur.execute("ALTER TABLE promotions ADD COLUMN IF NOT EXISTS text TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE promotions ADD COLUMN IF NOT EXISTS link TEXT NOT NULL DEFAULT ''")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_cards_user_id ON user_cards(user_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_user_date_time ON bookings(user_id, booking_date, booking_time);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_type_created ON orders(order_type, created_at DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_effective_status_created ON orders(effective_status, created_at DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_delivery_overdue_created ON orders(is_delivery_overdue, created_at DESC) WHERE order_type = 'delivery';"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_booking_slot ON orders(booking_table_id, booking_date, booking_time);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_date_time ON bookings(booking_date, booking_time);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_menu_items_active_type ON menu_items(active, type, id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_menu_items_featured ON menu_items(featured, popularity DESC, id ASC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_users_created_by ON admin_users(created_by);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_actions_admin_user_id ON admin_actions(admin_user_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_actions_created_at ON admin_actions(created_at);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_actions_entity ON admin_actions(entity_type, entity_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotions_active_priority ON promotions(active, priority DESC, id ASC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotions_window ON promotions(start_at, end_at);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotion_applications_promo_user_applied ON promotion_applications(promotion_id, user_id, applied_at DESC);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotion_applications_order_id ON promotion_applications(order_id);"
    )
    cur.execute(
        """
        CREATE OR REPLACE FUNCTION prune_admin_actions_30d()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            DELETE FROM admin_actions
            WHERE created_at < NOW() - INTERVAL '30 days';
            RETURN NEW;
        END;
        $$;
        """
    )
    cur.execute("DROP TRIGGER IF EXISTS trg_prune_admin_actions_30d ON admin_actions;")
    cur.execute(
        """
        CREATE TRIGGER trg_prune_admin_actions_30d
        AFTER INSERT ON admin_actions
        FOR EACH STATEMENT
        EXECUTE FUNCTION prune_admin_actions_30d();
        """
    )


def _count_rows(cur, table_name):
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _table_exists(cur, table_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    row = cur.fetchone()
    return bool(row[0]) if row else False


def _column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
        )
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    return bool(row[0]) if row else False


def _column_type_info(cur, table_name, column_name):
    cur.execute(
        """
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    if row is None:
        return "", ""
    return _coerce_text(row[0]), _coerce_text(row[1])


def _normalize_timestamptz_column(cur, table_name, column_name, *, nullable: bool, default_sql: str | None):
    if not _table_exists(cur, table_name):
        return
    if not _column_exists(cur, table_name, column_name):
        return

    _, udt_name = _column_type_info(cur, table_name, column_name)
    if udt_name == "timestamptz":
        if default_sql:
            cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {default_sql}")
        else:
            cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT")
        if nullable:
            cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL")
        else:
            cur.execute(f"UPDATE {table_name} SET {column_name} = NOW() WHERE {column_name} IS NULL")
            cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL")
        return

    cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT")

    if udt_name == "timestamp":
        cur.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN {column_name} TYPE TIMESTAMPTZ
            USING {column_name} AT TIME ZONE 'UTC'
            """
        )
    else:
        fallback_sql = "NULL" if nullable else "NOW()"
        cur.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN {column_name} TYPE TIMESTAMPTZ
            USING (
                CASE
                    WHEN NULLIF(BTRIM({column_name}::text), '') IS NULL THEN {fallback_sql}
                    WHEN BTRIM({column_name}::text) ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}(?:[ T][0-9]{{2}}:[0-9]{{2}}(?::[0-9]{{2}}(?:\\.[0-9]+)?)?)?(?:Z|[+-][0-9]{{2}}:[0-9]{{2}})?$'
                        THEN CASE
                            WHEN BTRIM({column_name}::text) ~ '(?:Z|[+-][0-9]{{2}}:[0-9]{{2}})$'
                                THEN BTRIM({column_name}::text)::TIMESTAMPTZ
                            ELSE BTRIM({column_name}::text)::TIMESTAMP AT TIME ZONE 'UTC'
                        END
                    ELSE {fallback_sql}
                END
            )
            """
        )

    if default_sql:
        cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {default_sql}")
    if nullable:
        cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL")
    else:
        cur.execute(f"UPDATE {table_name} SET {column_name} = NOW() WHERE {column_name} IS NULL")
        cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL")


def _normalize_legacy_temporal_columns(cur):
    columns = (
        ("users", "created_at", False, "NOW()"),
        ("user_cards", "created_at", False, "NOW()"),
        ("bookings", "created_at", False, "NOW()"),
        ("orders", "created_at", False, "NOW()"),
        ("orders", "cancelled_at", True, None),
        ("orders", "effective_status_updated_at", True, None),
        ("admin_users", "created_at", False, "NOW()"),
        ("admin_actions", "created_at", False, "NOW()"),
        ("menu_items", "created_at", False, "NOW()"),
        ("menu_items", "updated_at", False, "NOW()"),
        ("promotions", "start_at", True, None),
        ("promotions", "end_at", True, None),
        ("promotions", "created_at", False, "NOW()"),
        ("promotions", "updated_at", False, "NOW()"),
        ("promotion_applications", "applied_at", False, "NOW()"),
    )
    for table_name, column_name, nullable, default_sql in columns:
        _normalize_timestamptz_column(
            cur,
            table_name,
            column_name,
            nullable=nullable,
            default_sql=default_sql,
        )


def _coerce_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_text(value, default=""):
    if value is None:
        return default
    return str(value)


def _coerce_dict(value):
    return value if isinstance(value, dict) else {}


def _coerce_list(value):
    return value if isinstance(value, list) else []


def _coerce_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(_coerce_text(value))


def _parse_optional_date(value):
    text = _coerce_text(value).strip()
    if not text:
        return None
    return _parse_date(text)


def _parse_time(value):
    if isinstance(value, dt_time):
        return value.replace(second=0, microsecond=0)
    parsed = dt_time.fromisoformat(_coerce_text(value))
    return parsed.replace(second=0, microsecond=0)


def _parse_optional_time(value):
    text = _coerce_text(value).strip()
    if not text:
        return None
    return _parse_time(text)


def _parse_optional_datetime(value):
    text = _coerce_text(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def _parse_optional_datetime_utc(value):
    parsed = _parse_optional_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc)
    return parsed.replace(tzinfo=timezone.utc)


def _serialize_datetime_utc(value):
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc) if value.tzinfo is not None else value
        return normalized.replace(tzinfo=None).isoformat(timespec="seconds")
    return _coerce_text(value)


def _serialize_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return _coerce_text(value)


def _serialize_time(value):
    if isinstance(value, dt_time):
        return value.replace(microsecond=0).isoformat()
    return _coerce_text(value)


def _time_hhmm(value):
    if isinstance(value, dt_time):
        return value.strftime("%H:%M")
    try:
        return _parse_time(value).strftime("%H:%M")
    except (TypeError, ValueError):
        return _coerce_text(value)


def _replace_users_in_tx(cur, users):
    user_rows = []
    user_ids = []
    card_rows = []

    for user in _coerce_list(users):
        if not isinstance(user, dict):
            continue
        user_id = _coerce_int(user.get("id"), 0)
        if user_id <= 0:
            continue
        user_ids.append(user_id)
        user_rows.append(
            (
                user_id,
                _coerce_text(user.get("name")),
                _coerce_text(user.get("phone")),
                _coerce_text(user.get("password_hash")),
                _coerce_int(user.get("balance"), 0),
                _parse_optional_datetime_utc(user.get("created_at")) or datetime.now(timezone.utc),
            )
        )
        for card in _coerce_list(user.get("cards")):
            if not isinstance(card, dict):
                continue
            card_rows.append(
                (
                    user_id,
                    _coerce_text(card.get("brand"), "MIR"),
                    _coerce_text(card.get("last4")),
                    bool(card.get("active")),
                    _coerce_text(card.get("holder")) or None,
                    _coerce_text(card.get("expiry")) or None,
                    _parse_optional_datetime_utc(card.get("created_at")) or datetime.now(timezone.utc),
                )
            )

    if user_rows:
        cur.executemany(
            """
            INSERT INTO users (id, name, phone, password_hash, balance, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET
                name = EXCLUDED.name,
                phone = EXCLUDED.phone,
                password_hash = EXCLUDED.password_hash,
                balance = EXCLUDED.balance,
                created_at = EXCLUDED.created_at
            """,
            user_rows,
        )

    if user_ids:
        cur.execute("DELETE FROM user_cards WHERE user_id = ANY(%s)", (user_ids,))
        if card_rows:
            cur.executemany(
                """
                INSERT INTO user_cards (
                    user_id, brand, last4, active, holder, expiry, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                card_rows,
            )


def _replace_bookings_in_tx(cur, bookings):
    cur.execute("DELETE FROM bookings")
    rows = []
    for booking in _coerce_list(bookings):
        if not isinstance(booking, dict):
            continue
        try:
            user_id = _coerce_int(booking.get("user_id"), 0)
            table_id = _coerce_int(booking.get("table_id"), 0)
            if user_id <= 0 or table_id <= 0:
                continue
            rows.append(
                (
                    user_id,
                    table_id,
                    _parse_date(booking.get("date")),
                    _parse_time(booking.get("time")),
                    _coerce_text(booking.get("name")),
                    _parse_optional_datetime_utc(booking.get("created_at")) or datetime.now(timezone.utc),
                )
            )
        except (TypeError, ValueError):
            continue

    if rows:
        cur.executemany(
            """
            INSERT INTO bookings (
                user_id, table_id, booking_date, booking_time, name, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def _replace_orders_in_tx(cur, orders):
    cur.execute("DELETE FROM order_items")
    cur.execute("DELETE FROM orders")

    order_rows = []
    item_rows = []
    now = current_time_value()
    for order in _coerce_list(orders):
        if not isinstance(order, dict):
            continue
        normalized_order = apply_persisted_status_fields_value(dict(order), now)
        order_id = _coerce_int(normalized_order.get("id"), 0)
        user_id = _coerce_int(normalized_order.get("user_id"), 0)
        if order_id <= 0 or user_id <= 0:
            continue

        order_rows.append(
            (
                order_id,
                user_id,
                _coerce_text(normalized_order.get("order_type"), "dine_in") or "dine_in",
                _coerce_text(normalized_order.get("status"), "preparing") or "preparing",
                _coerce_text(normalized_order.get("effective_status"), "preparing") or "preparing",
                _parse_optional_datetime_utc(normalized_order.get("effective_status_updated_at")),
                bool(normalized_order.get("is_delivery_overdue")),
                _parse_optional_datetime_utc(normalized_order.get("created_at")) or datetime.now(timezone.utc),
                _coerce_int(normalized_order.get("items_total"), 0),
                _coerce_int(normalized_order.get("points_applied"), 0),
                _coerce_int(normalized_order.get("payable_total"), 0),
                _coerce_int(normalized_order.get("bonus_earned"), 0),
                _coerce_text(normalized_order.get("comment")),
                _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("mode")),
                _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("label")),
                _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("time")),
                (
                    _coerce_int((_coerce_dict(normalized_order.get("booking"))).get("table_id"), 0)
                    or None
                ),
                _parse_optional_date((_coerce_dict(normalized_order.get("booking"))).get("date")),
                _parse_optional_time((_coerce_dict(normalized_order.get("booking"))).get("time")),
                _coerce_text((_coerce_dict(normalized_order.get("booking"))).get("status")),
                _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("brand")),
                _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("last4")),
                _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("expiry")),
                _coerce_text(normalized_order.get("delivery_name")),
                _coerce_text(normalized_order.get("delivery_phone")),
                _coerce_text(normalized_order.get("delivery_street")),
                _coerce_text(normalized_order.get("delivery_house")),
                _coerce_text(normalized_order.get("delivery_apartment")),
                _coerce_text(normalized_order.get("delivery_entrance")),
                _coerce_text(normalized_order.get("delivery_floor")),
                _coerce_text(normalized_order.get("delivery_intercom")),
                _coerce_text(normalized_order.get("delivery_comment")),
                _coerce_text(normalized_order.get("delivery_address")),
                _coerce_int(normalized_order.get("delivery_eta_minutes"), 20),
                _parse_optional_datetime_utc(normalized_order.get("cancelled_at")),
            )
        )

        position = 0
        for item in _coerce_list(normalized_order.get("items")):
            if not isinstance(item, dict):
                continue
            item_rows.append(
                (
                    order_id,
                    position,
                    _coerce_int(item.get("id"), 0),
                    _coerce_text(item.get("name")),
                    _coerce_int(item.get("price"), 0),
                    _coerce_int(item.get("qty"), 0),
                    _coerce_text(item.get("photo")) or None,
                )
            )
            position += 1

    if order_rows:
        cur.executemany(
            """
            INSERT INTO orders (
                id,
                user_id,
                order_type,
                status,
                effective_status,
                effective_status_updated_at,
                is_delivery_overdue,
                created_at,
                items_total,
                points_applied,
                payable_total,
                bonus_earned,
                comment,
                serving_mode,
                serving_label,
                serving_time,
                booking_table_id,
                booking_date,
                booking_time,
                booking_status,
                payment_card_brand,
                payment_card_last4,
                payment_card_expiry,
                delivery_name,
                delivery_phone,
                delivery_street,
                delivery_house,
                delivery_apartment,
                delivery_entrance,
                delivery_floor,
                delivery_intercom,
                delivery_comment,
                delivery_address,
                delivery_eta_minutes,
                cancelled_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            """,
            order_rows,
        )

    if item_rows:
        cur.executemany(
            """
            INSERT INTO order_items (
                order_id, position, item_id, name, price, qty, photo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            item_rows,
        )


def _migrate_legacy_orders_columns(cur):
    if not _table_exists(cur, "orders"):
        return
    if not _column_exists(cur, "orders", "serving"):
        return

    cur.execute(
        """
        UPDATE orders
        SET
            serving_mode = CASE
                WHEN serving_mode = '' THEN COALESCE(serving ->> 'mode', '')
                ELSE serving_mode
            END,
            serving_label = CASE
                WHEN serving_label = '' THEN COALESCE(serving ->> 'label', '')
                ELSE serving_label
            END,
            serving_time = CASE
                WHEN serving_time = '' THEN COALESCE(serving ->> 'time', '')
                ELSE serving_time
            END,
            booking_table_id = CASE
                WHEN booking_table_id IS NULL AND NULLIF(booking_snapshot ->> 'table_id', '') IS NOT NULL
                    THEN (booking_snapshot ->> 'table_id')::INTEGER
                ELSE booking_table_id
            END,
            booking_date = CASE
                WHEN booking_date IS NULL AND NULLIF(booking_snapshot ->> 'date', '') IS NOT NULL
                    THEN (booking_snapshot ->> 'date')::DATE
                ELSE booking_date
            END,
            booking_time = CASE
                WHEN booking_time IS NULL AND NULLIF(booking_snapshot ->> 'time', '') IS NOT NULL
                    THEN (booking_snapshot ->> 'time')::TIME
                ELSE booking_time
            END,
            booking_status = CASE
                WHEN booking_status = '' THEN COALESCE(booking_snapshot ->> 'status', '')
                ELSE booking_status
            END,
            payment_card_brand = CASE
                WHEN payment_card_brand = '' THEN COALESCE(payment_card ->> 'brand', '')
                ELSE payment_card_brand
            END,
            payment_card_last4 = CASE
                WHEN payment_card_last4 = '' THEN COALESCE(payment_card ->> 'last4', '')
                ELSE payment_card_last4
            END,
            payment_card_expiry = CASE
                WHEN payment_card_expiry = '' THEN COALESCE(payment_card ->> 'expiry', '')
                ELSE payment_card_expiry
            END
        """
    )


def _read_legacy_meta(path: Path):
    data = {}
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            raw_text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw_text = path.read_text(encoding="utf-8", errors="replace")

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip().lower().lstrip("\ufeff")] = value.strip()
    return data


def _legacy_photo_path(item_dir: Path, root_path: Path, prefix: str, preferred_names):
    for photo_name in preferred_names:
        candidate = item_dir / photo_name
        if candidate.exists():
            try:
                relative_path = candidate.relative_to(root_path).as_posix()
            except ValueError:
                relative_path = candidate.name
            return f"{prefix}/{relative_path}"
    for extension in ("*.webp", "*.png", "*.jpg", "*.jpeg"):
        candidates = sorted(item_dir.glob(extension))
        if not candidates:
            continue
        candidate = candidates[0]
        try:
            relative_path = candidate.relative_to(root_path).as_posix()
        except ValueError:
            relative_path = candidate.name
        return f"{prefix}/{relative_path}"
    return ""


def _normalize_slug(value):
    text = _coerce_text(value).strip().replace("\\", "/")
    parts = [segment for segment in text.split("/") if segment]
    if len(parts) >= 3 and parts[0] == "promo_items" and parts[1] == "akciya":
        return "/".join(parts[2:-1]) or parts[-2]
    if len(parts) >= 3 and parts[0] == "menu_items":
        return parts[-2]
    if len(parts) >= 3 and parts[0] == "akciya":
        return "/".join(parts[1:])
    if parts:
        return "/".join(parts)
    return "promotion"


def _legacy_menu_item_rows():
    rows = []
    if not MENU_ITEMS_PATH.exists():
        return rows
    for meta_path in sorted(MENU_ITEMS_PATH.rglob("item.txt")):
        meta = _read_legacy_meta(meta_path)
        item_id = _coerce_int(meta.get("id"), 0)
        if item_id <= 0:
            continue
        name = _coerce_text(meta.get("name")).strip()
        lore = _coerce_text(meta.get("lore")).strip()
        item_type = _coerce_text(meta.get("type")).strip()
        if not name or not lore or not item_type:
            continue
        rows.append(
            {
                "id": item_id,
                "slug": meta_path.parent.name,
                "name": name,
                "lore": lore,
                "type": item_type,
                "price": _coerce_int(meta.get("price"), 0),
                "photo_path": _legacy_photo_path(
                    meta_path.parent,
                    MENU_ITEMS_PATH,
                    "menu_items",
                    MENU_PHOTO_NAMES,
                ),
                "portion_label": _coerce_text(
                    meta.get("portion")
                    or meta.get("weight")
                    or meta.get("grams")
                    or meta.get("gram")
                    or meta.get("volume")
                    or meta.get("serving")
                    or meta.get("yield")
                ).strip(),
                "popularity": _coerce_int(meta.get("popularity") or meta.get("orders_count"), 0),
                "featured": _coerce_bool(meta.get("featured"), False),
                "active": _coerce_bool(meta.get("active") if "active" in meta else meta.get("available"), True),
            }
        )
    return rows


def _legacy_promotion_rows():
    rows = []
    if not PROMO_ITEMS_PATH.exists():
        return rows
    for meta_path in sorted(PROMO_ITEMS_PATH.rglob("item.txt")):
        try:
            relative_parts = meta_path.relative_to(PROMO_ITEMS_PATH).parts
        except ValueError:
            continue
        if len(relative_parts) < 2 or relative_parts[0] not in {"akciya", "reklama"}:
            continue
        meta = _read_legacy_meta(meta_path)
        class_name = str(meta.get("class") or relative_parts[0]).strip().lower()
        if class_name not in {"akciya", "reklama"}:
            continue
        promo_id = _coerce_int(meta.get("id"), 0)
        if promo_id <= 0:
            continue
        photo_path = _legacy_photo_path(
            meta_path.parent,
            PROMO_ITEMS_PATH,
            "promo_items",
            ("photo.png", "photo.webp", "photo.jpg", "photo.jpeg"),
        )
        if class_name == "reklama":
            text = _coerce_text(meta.get("text")).strip()
            if not text:
                continue
            rows.append(
                {
                    "id": promo_id,
                    "slug": "/".join(relative_parts[1:-1]),
                    "name": f"reklama-{promo_id}",
                    "lore": "",
                    "class": class_name,
                    "text": text,
                    "link": _coerce_text(meta.get("link")).strip(),
                    "active": _coerce_bool(meta.get("active"), True),
                    "priority": _coerce_int(meta.get("priority"), 100),
                    "condition": "",
                    "reward": "",
                    "notify": "",
                    "reward_mode": "",
                    "limit_per_order": None,
                    "limit_per_user_per_day": None,
                    "start_at": _parse_optional_datetime(meta.get("start_at")),
                    "end_at": _parse_optional_datetime(meta.get("end_at")),
                    "photo_path": photo_path,
                }
            )
            continue
        name = _coerce_text(meta.get("name")).strip()
        lore = _coerce_text(meta.get("lore")).strip()
        if not name or not lore:
            continue
        rows.append(
            {
                "id": promo_id,
                "slug": "/".join(relative_parts[1:-1]),
                "name": name,
                "lore": lore,
                "class": class_name,
                "text": "",
                "link": "",
                "active": _coerce_bool(meta.get("active"), True),
                "priority": _coerce_int(meta.get("priority"), 100),
                "condition": _coerce_text(meta.get("condition")).strip(),
                "reward": _coerce_text(meta.get("reward")).strip(),
                "notify": _coerce_text(meta.get("notify")).strip(),
                "reward_mode": _coerce_text(meta.get("reward_mode"), "once").strip() or "once",
                "limit_per_order": _coerce_int(meta.get("limit_per_order"), 0) or None,
                "limit_per_user_per_day": _coerce_int(meta.get("limit_per_user_per_day"), 0) or None,
                "start_at": _parse_optional_datetime(meta.get("start_at")),
                "end_at": _parse_optional_datetime(meta.get("end_at")),
                "photo_path": photo_path,
            }
        )
    return rows


def _upsert_menu_items_in_tx(cur, menu_items):
    rows = []
    for menu_item in _coerce_list(menu_items):
        if not isinstance(menu_item, dict):
            continue
        item_id = _coerce_int(menu_item.get("id"), 0)
        if item_id <= 0:
            continue
        rows.append(
            (
                item_id,
                _normalize_slug(menu_item.get("slug") or menu_item.get("photo_path") or menu_item.get("name")),
                _coerce_text(menu_item.get("name")).strip(),
                _coerce_text(menu_item.get("lore")).strip(),
                _coerce_text(menu_item.get("type")).strip(),
                _coerce_int(menu_item.get("price"), 0),
                _coerce_text(menu_item.get("photo_path")).strip(),
                _coerce_text(menu_item.get("portion_label") or menu_item.get("weight")).strip(),
                _coerce_int(menu_item.get("popularity"), 0),
                _coerce_bool(menu_item.get("featured"), False),
                _coerce_bool(menu_item.get("active"), True),
                menu_item.get("created_by_admin_user_id"),
                menu_item.get("updated_by_admin_user_id"),
            )
        )
    if not rows:
        return
    cur.executemany(
        """
        INSERT INTO menu_items (
            id,
            slug,
            name,
            lore,
            type,
            price,
            photo_path,
            portion_label,
            popularity,
            featured,
            active,
            created_by_admin_user_id,
            updated_by_admin_user_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id)
        DO UPDATE SET
            slug = EXCLUDED.slug,
            name = EXCLUDED.name,
            lore = EXCLUDED.lore,
            type = EXCLUDED.type,
            price = EXCLUDED.price,
            photo_path = EXCLUDED.photo_path,
            portion_label = EXCLUDED.portion_label,
            popularity = EXCLUDED.popularity,
            featured = EXCLUDED.featured,
            active = EXCLUDED.active,
            updated_at = NOW(),
            updated_by_admin_user_id = EXCLUDED.updated_by_admin_user_id
        """,
        rows,
    )


def _upsert_promotions_in_tx(cur, promotions):
    rows = []
    for promotion in _coerce_list(promotions):
        if not isinstance(promotion, dict):
            continue
        promotion_id = _coerce_int(promotion.get("id"), 0)
        if promotion_id <= 0:
            continue
        class_name = _coerce_text(promotion.get("class") or promotion.get("class_name"), "akciya").strip() or "akciya"
        rows.append(
            (
                promotion_id,
                _normalize_slug(promotion.get("slug") or promotion.get("photo_path") or promotion.get("name") or promotion.get("text")),
                _coerce_text(promotion.get("name")).strip() or (f"reklama-{promotion_id}" if class_name == "reklama" else ""),
                _coerce_text(promotion.get("lore")).strip(),
                class_name,
                _coerce_text(promotion.get("text")).strip(),
                _coerce_text(promotion.get("link")).strip(),
                _coerce_bool(promotion.get("active"), True),
                _coerce_int(promotion.get("priority"), 100),
                _coerce_text(promotion.get("condition")).strip(),
                _coerce_text(promotion.get("reward")).strip(),
                _coerce_text(promotion.get("notify")).strip(),
                _coerce_text(promotion.get("reward_mode"), "once").strip() or "once",
                (_coerce_int(promotion.get("limit_per_order"), 0) or None),
                (_coerce_int(promotion.get("limit_per_user_per_day"), 0) or None),
                _parse_optional_datetime(promotion.get("start_at")),
                _parse_optional_datetime(promotion.get("end_at")),
                _coerce_text(promotion.get("photo_path")).strip(),
                promotion.get("created_by_admin_user_id"),
                promotion.get("updated_by_admin_user_id"),
            )
        )
    if not rows:
        return
    cur.executemany(
        """
        INSERT INTO promotions (
            id,
            slug,
            name,
            lore,
            class_name,
            text,
            link,
            active,
            priority,
            condition,
            reward,
            notify,
            reward_mode,
            limit_per_order,
            limit_per_user_per_day,
            start_at,
            end_at,
            photo_path,
            created_by_admin_user_id,
            updated_by_admin_user_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id)
        DO UPDATE SET
            slug = EXCLUDED.slug,
            name = EXCLUDED.name,
            lore = EXCLUDED.lore,
            class_name = EXCLUDED.class_name,
            text = EXCLUDED.text,
            link = EXCLUDED.link,
            active = EXCLUDED.active,
            priority = EXCLUDED.priority,
            condition = EXCLUDED.condition,
            reward = EXCLUDED.reward,
            notify = EXCLUDED.notify,
            reward_mode = EXCLUDED.reward_mode,
            limit_per_order = EXCLUDED.limit_per_order,
            limit_per_user_per_day = EXCLUDED.limit_per_user_per_day,
            start_at = EXCLUDED.start_at,
            end_at = EXCLUDED.end_at,
            photo_path = EXCLUDED.photo_path,
            updated_at = NOW(),
            updated_by_admin_user_id = EXCLUDED.updated_by_admin_user_id
        """,
        rows,
    )


def _maybe_migrate_legacy_promotions(cur):
    if _count_rows(cur, "promotions") > 0:
        return
    rows = _legacy_promotion_rows()
    if not rows:
        return
    _upsert_promotions_in_tx(cur, rows)


def _maybe_migrate_legacy_menu_items(cur):
    if _count_rows(cur, "menu_items") > 0:
        return
    rows = _legacy_menu_item_rows()
    if not rows:
        return
    _upsert_menu_items_in_tx(cur, rows)


def _delete_missing_menu_items_in_tx(cur, present_ids):
    normalized_ids = sorted({int(item_id) for item_id in present_ids if _coerce_int(item_id, 0) > 0})
    if normalized_ids:
        cur.execute(
            """
            UPDATE menu_items
            SET active = FALSE,
                updated_at = NOW()
            WHERE id <> ALL(%s)
              AND active <> FALSE
            """,
            (normalized_ids,),
        )
    else:
        cur.execute(
            """
            UPDATE menu_items
            SET active = FALSE,
                updated_at = NOW()
            WHERE active <> FALSE
            """
        )
    return _coerce_int(getattr(cur, "rowcount", 0), 0)


def _delete_missing_promotions_in_tx(cur, present_ids):
    normalized_ids = sorted({int(item_id) for item_id in present_ids if _coerce_int(item_id, 0) > 0})
    if normalized_ids:
        cur.execute(
            """
            UPDATE promotions
            SET active = FALSE,
                updated_at = NOW()
            WHERE class_name IN ('akciya', 'reklama')
              AND id <> ALL(%s)
              AND active <> FALSE
            """,
            (normalized_ids,),
        )
    else:
        cur.execute(
            """
            UPDATE promotions
            SET active = FALSE,
                updated_at = NOW()
            WHERE class_name IN ('akciya', 'reklama')
              AND active <> FALSE
            """
        )
    return _coerce_int(getattr(cur, "rowcount", 0), 0)


def _maybe_migrate_legacy_app_state(cur):
    if not _table_exists(cur, "app_state"):
        return

    if any(
        _count_rows(cur, table_name) > 0
        for table_name in ("users", "bookings", "orders")
    ):
        return

    cur.execute(
        """
        SELECT state_key, state_value
        FROM app_state
        WHERE state_key IN ('users', 'bookings', 'orders')
        """
    )
    state_map = {row[0]: row[1] for row in cur.fetchall()}
    users = _coerce_list(state_map.get("users"))
    bookings = _coerce_list(state_map.get("bookings"))
    orders = _coerce_list(state_map.get("orders"))
    if not users and not bookings and not orders:
        return

    _replace_users_in_tx(cur, users)
    _replace_bookings_in_tx(cur, bookings)
    _replace_orders_in_tx(cur, orders)


def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _execute_schema(cur)
                _normalize_legacy_temporal_columns(cur)
                _migrate_legacy_orders_columns(cur)
                _maybe_migrate_legacy_app_state(cur)
                _maybe_migrate_legacy_menu_items(cur)
                _maybe_migrate_legacy_promotions(cur)
        _SCHEMA_READY = True


def _run_db_operation(operation):
    last_error = None
    for attempt in range(DB_OPERATION_RETRIES):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            _reset_conn()
            if attempt == DB_OPERATION_RETRIES - 1:
                break
            time.sleep(DB_RETRY_DELAY_SECONDS)
    raise last_error


_ORDER_SELECT_COLUMNS = """
    id,
    user_id,
    order_type,
    status,
    effective_status,
    effective_status_updated_at,
    is_delivery_overdue,
    created_at,
    items_total,
    points_applied,
    payable_total,
    bonus_earned,
    comment,
    serving_mode,
    serving_label,
    serving_time,
    booking_table_id,
    booking_date,
    booking_time,
    booking_status,
    payment_card_brand,
    payment_card_last4,
    payment_card_expiry,
    delivery_name,
    delivery_phone,
    delivery_street,
    delivery_house,
    delivery_apartment,
    delivery_entrance,
    delivery_floor,
    delivery_intercom,
    delivery_comment,
    delivery_address,
    delivery_eta_minutes,
    cancelled_at
"""


def _booking_row_to_dict(row):
    return {
        "user_id": row[0],
        "table_id": row[1],
        "date": _serialize_date(row[2]),
        "time": _time_hhmm(row[3]),
        "name": _coerce_text(row[4]),
        "created_at": _serialize_datetime_utc(row[5]),
    }


def _parse_booking_datetime(booking: dict):
    date_value = _coerce_text((booking or {}).get("date")).strip()
    time_value = _coerce_text((booking or {}).get("time")).strip()
    if not date_value or not time_value:
        return None
    try:
        return datetime.fromisoformat(f"{date_value}T{time_value}")
    except ValueError:
        return None


def _next_integer_id(cur, table_name: str):
    if table_name not in {"users", "orders"}:
        raise ValueError(f"Unsupported table for integer id allocation: {table_name}")
    cur.execute(f"LOCK TABLE {table_name} IN EXCLUSIVE MODE")
    cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table_name}")
    row = cur.fetchone()
    return _coerce_int(row[0], 1) if row else 1


def _card_row_to_dict(row):
    return {
        "brand": _coerce_text(row[1]),
        "last4": _coerce_text(row[2]),
        "active": bool(row[3]),
        "holder": _coerce_text(row[4]) or None,
        "expiry": _coerce_text(row[5]) or None,
        "created_at": _serialize_datetime_utc(row[6]),
    }


def _load_user_cards_by_user_ids(cur, user_ids):
    if not user_ids:
        return {}
    cur.execute(
        """
        SELECT user_id, brand, last4, active, holder, expiry, created_at
        FROM user_cards
        WHERE user_id = ANY(%s)
        ORDER BY user_id, created_at, id
        """,
        (user_ids,),
    )
    cards_by_user = {}
    for row in cur.fetchall():
        cards_by_user.setdefault(row[0], []).append(_card_row_to_dict(row))
    return cards_by_user


def _user_row_to_dict(row, cards_by_user):
    return {
        "id": row[0],
        "name": _coerce_text(row[1]),
        "phone": _coerce_text(row[2]),
        "password_hash": _coerce_text(row[3]),
        "balance": _coerce_int(row[4], 0),
        "cards": cards_by_user.get(row[0], []),
        "created_at": _serialize_datetime_utc(row[5]),
    }


def _load_order_items_by_order_ids(cur, order_ids):
    if not order_ids:
        return {}
    cur.execute(
        """
        SELECT order_id, item_id, name, price, qty, photo
        FROM order_items
        WHERE order_id = ANY(%s)
        ORDER BY order_id, position
        """,
        (order_ids,),
    )
    items_by_order = {}
    for row in cur.fetchall():
        items_by_order.setdefault(row[0], []).append(
            {
                "id": row[1],
                "name": _coerce_text(row[2]),
                "price": _coerce_int(row[3], 0),
                "qty": _coerce_int(row[4], 0),
                "photo": row[5],
            }
        )
    return items_by_order


def _order_row_to_dict(row, items_by_order):
    order = {
        "id": row[0],
        "user_id": row[1],
        "status": _coerce_text(row[3]),
        "effective_status": _coerce_text(row[4]),
        "effective_status_updated_at": _serialize_datetime_utc(row[5]),
        "is_delivery_overdue": bool(row[6]),
        "created_at": _serialize_datetime_utc(row[7]),
        "items": items_by_order.get(row[0], []),
        "items_total": _coerce_int(row[8], 0),
        "points_applied": _coerce_int(row[9], 0),
        "payable_total": _coerce_int(row[10], 0),
        "bonus_earned": _coerce_int(row[11], 0),
        "comment": _coerce_text(row[12]),
        "serving": {
            "mode": _coerce_text(row[13]),
            "label": _coerce_text(row[14]),
            **({"time": _coerce_text(row[15])} if _coerce_text(row[15]) else {}),
        },
        "booking": {
            **({"table_id": row[16]} if row[16] is not None else {}),
            **({"date": _serialize_date(row[17])} if row[17] is not None else {}),
            **({"time": _time_hhmm(row[18])} if row[18] is not None else {}),
            **({"status": _coerce_text(row[19])} if _coerce_text(row[19]) else {}),
        },
        "payment_card": {
            **({"brand": _coerce_text(row[20])} if _coerce_text(row[20]) else {}),
            **({"last4": _coerce_text(row[21])} if _coerce_text(row[21]) else {}),
            **({"expiry": _coerce_text(row[22])} if _coerce_text(row[22]) else {}),
        },
        "delivery_name": _coerce_text(row[23]),
        "delivery_phone": _coerce_text(row[24]),
        "delivery_street": _coerce_text(row[25]),
        "delivery_house": _coerce_text(row[26]),
        "delivery_apartment": _coerce_text(row[27]),
        "delivery_entrance": _coerce_text(row[28]),
        "delivery_floor": _coerce_text(row[29]),
        "delivery_intercom": _coerce_text(row[30]),
        "delivery_comment": _coerce_text(row[31]),
        "delivery_address": _coerce_text(row[32]),
        "delivery_eta_minutes": _coerce_int(row[33], 20),
    }
    order_type = _coerce_text(row[2], "dine_in") or "dine_in"
    if order_type:
        order["order_type"] = order_type
    if not order["serving"].get("mode") and not order["serving"].get("label") and not order["serving"].get("time"):
        order["serving"] = {}
    if not order["booking"]:
        order["booking"] = {}
    if not order["payment_card"]:
        order["payment_card"] = {}
    cancelled_at = _serialize_datetime_utc(row[34])
    if cancelled_at:
        order["cancelled_at"] = cancelled_at
    return order


def _hydrate_orders(cur, order_rows, *, include_items: bool):
    order_ids = [row[0] for row in order_rows]
    items_by_order = _load_order_items_by_order_ids(cur, order_ids) if include_items else {}
    return [_order_row_to_dict(row, items_by_order) for row in order_rows]


def load_bookings_raw(_bookings_path):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, table_id, booking_date, booking_time, name, created_at
                FROM bookings
                ORDER BY booking_date, booking_time, created_at
                """
            )
            rows = cur.fetchall()
        return [_booking_row_to_dict(row) for row in rows]

    return _run_db_operation(operation)


def save_bookings(_bookings_path, bookings):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _replace_bookings_in_tx(cur, bookings)

    _run_db_operation(operation)


def load_bookings(bookings_path, parse_datetime_fn, booking_duration_minutes):
    bookings = load_bookings_raw(bookings_path)
    now = current_time_value()
    active = []
    for booking in bookings:
        booking_dt = parse_datetime_fn(booking.get("date"), booking.get("time"))
        if booking_dt is None:
            continue
        if booking_dt + timedelta(minutes=booking_duration_minutes) <= now:
            continue
        active.append(booking)
    if len(active) != len(bookings):
        save_bookings(bookings_path, active)
    return active


def load_orders(_orders_path):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT { _ORDER_SELECT_COLUMNS }
                FROM orders
                ORDER BY created_at, id
                """
            )
            order_rows = cur.fetchall()
            return _hydrate_orders(cur, order_rows, include_items=True)

    return _run_db_operation(operation)


def save_orders(_orders_path, orders):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _replace_orders_in_tx(cur, orders)

    _run_db_operation(operation)


def load_users(_users_path):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, phone, password_hash, balance, created_at
                FROM users
                ORDER BY id
                """
            )
            user_rows = cur.fetchall()
            cur.execute(
                """
                SELECT user_id, brand, last4, active, holder, expiry, created_at
                FROM user_cards
                ORDER BY user_id, created_at, id
                """
            )
            card_rows = cur.fetchall()
        cards_by_user = {}
        for row in card_rows:
            cards_by_user.setdefault(row[0], []).append(_card_row_to_dict(row))
        return [_user_row_to_dict(row, cards_by_user) for row in user_rows]

    return _run_db_operation(operation)


def get_user_by_id(user_id: int):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, phone, password_hash, balance, created_at
                FROM users
                WHERE id = %s
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cards_by_user = _load_user_cards_by_user_ids(cur, [int(user_id)])
        return _user_row_to_dict(row, cards_by_user)

    return _run_db_operation(operation)


def get_user_by_phone(phone: str):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if not digits:
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, phone, password_hash, balance, created_at
                FROM users
                WHERE regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') = %s
                LIMIT 1
                """,
                (digits,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cards_by_user = _load_user_cards_by_user_ids(cur, [row[0]])
        return _user_row_to_dict(row, cards_by_user)

    return _run_db_operation(operation)


def create_user(user: dict):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                user_id = _next_integer_id(cur, "users")
                cur.execute(
                    """
                    INSERT INTO users (id, name, phone, password_hash, balance, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        _coerce_text((user or {}).get("name")),
                        _coerce_text((user or {}).get("phone")),
                        _coerce_text((user or {}).get("password_hash")),
                        _coerce_int((user or {}).get("balance"), 0),
                        _parse_optional_datetime_utc((user or {}).get("created_at")) or datetime.now(timezone.utc),
                    ),
                )
                cur.execute(
                    """
                    SELECT id, name, phone, password_hash, balance, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                cards_by_user = _load_user_cards_by_user_ids(cur, [user_id])
        return _user_row_to_dict(row, cards_by_user) if row is not None else None

    return _run_db_operation(operation)


def update_user_password_hash(user_id: int, password_hash: str):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s
                    WHERE id = %s
                    RETURNING id, name, phone, password_hash, balance, created_at
                    """,
                    (_coerce_text(password_hash), int(user_id)),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cards_by_user = _load_user_cards_by_user_ids(cur, [int(user_id)])
        return _user_row_to_dict(row, cards_by_user)

    return _run_db_operation(operation)


def add_user_card(user_id: int, card: dict):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        normalized_user_id = int(user_id)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE id = %s", (normalized_user_id,))
                if cur.fetchone() is None:
                    return None
                cur.execute("UPDATE user_cards SET active = FALSE WHERE user_id = %s", (normalized_user_id,))
                cur.execute(
                    """
                    INSERT INTO user_cards (
                        user_id, brand, last4, active, holder, expiry, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        normalized_user_id,
                        _coerce_text((card or {}).get("brand"), "MIR"),
                        _coerce_text((card or {}).get("last4")),
                        _coerce_bool((card or {}).get("active"), True),
                        _coerce_text((card or {}).get("holder")) or None,
                        _coerce_text((card or {}).get("expiry")) or None,
                        _parse_optional_datetime_utc((card or {}).get("created_at")) or datetime.now(timezone.utc),
                    ),
                )
                cur.execute(
                    """
                    SELECT id, name, phone, password_hash, balance, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (normalized_user_id,),
                )
                row = cur.fetchone()
                cards_by_user = _load_user_cards_by_user_ids(cur, [normalized_user_id])
        return _user_row_to_dict(row, cards_by_user) if row is not None else None

    return _run_db_operation(operation)


def remove_user_card(user_id: int, *, created_at: str = "", last4: str = ""):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        normalized_user_id = int(user_id)
        normalized_created_at = _parse_optional_datetime_utc(created_at)
        normalized_last4 = _coerce_text(last4).strip()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, phone, password_hash, balance, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (normalized_user_id,),
                )
                user_row = cur.fetchone()
                if user_row is None:
                    return {"user": None, "removed": False}
                target_id = None
                removed_card_active = False
                if normalized_created_at is not None:
                    cur.execute(
                        """
                        SELECT id, active
                        FROM user_cards
                        WHERE user_id = %s AND created_at = %s
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (normalized_user_id, normalized_created_at),
                    )
                    target_row = cur.fetchone()
                    if target_row is not None:
                        target_id = target_row[0]
                        removed_card_active = bool(target_row[1])
                if target_id is None and normalized_last4:
                    cur.execute(
                        """
                        SELECT id, active
                        FROM user_cards
                        WHERE user_id = %s AND last4 = %s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        (normalized_user_id, normalized_last4),
                    )
                    target_row = cur.fetchone()
                    if target_row is not None:
                        target_id = target_row[0]
                        removed_card_active = bool(target_row[1])
                if target_id is None:
                    cards_by_user = _load_user_cards_by_user_ids(cur, [normalized_user_id])
                    return {"user": _user_row_to_dict(user_row, cards_by_user), "removed": False}
                cur.execute("DELETE FROM user_cards WHERE id = %s", (target_id,))
                if removed_card_active:
                    cur.execute(
                        """
                        SELECT id
                        FROM user_cards
                        WHERE user_id = %s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        (normalized_user_id,),
                    )
                    replacement = cur.fetchone()
                    if replacement is not None:
                        cur.execute("UPDATE user_cards SET active = TRUE WHERE id = %s", (replacement[0],))
                cards_by_user = _load_user_cards_by_user_ids(cur, [normalized_user_id])
        return {
            "user": _user_row_to_dict(user_row, cards_by_user) if user_row is not None else None,
            "removed": True,
        }

    return _run_db_operation(operation)


def list_user_bookings(user_id: int, *, include_expired: bool = False, booking_duration_minutes: int = 60):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, table_id, booking_date, booking_time, name, created_at
                FROM bookings
                WHERE user_id = %s
                ORDER BY booking_date DESC, booking_time DESC, created_at DESC, id DESC
                """,
                (int(user_id),),
            )
            rows = cur.fetchall()
        bookings = [_booking_row_to_dict(row) for row in rows]
        if include_expired:
            return bookings
        now = current_time_value()
        active = []
        for booking in bookings:
            booking_dt = _parse_booking_datetime(booking)
            if booking_dt is None:
                continue
            if booking_dt + timedelta(minutes=max(1, int(booking_duration_minutes or 60))) <= now:
                continue
            active.append(booking)
        return active

    return _run_db_operation(operation)


def list_reserved_table_ids(date_str: str, time_str: str, *, booking_duration_minutes: int = 60):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        selected_at = datetime.fromisoformat(f"{_coerce_text(date_str)}T{_coerce_text(time_str)}")
        selected_until = selected_at + timedelta(minutes=max(1, int(booking_duration_minutes or 60)))
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT table_id
                FROM bookings
                WHERE tsrange(
                    booking_date + booking_time,
                    booking_date + booking_time + make_interval(mins => %s),
                    '[)'
                ) && tsrange(%s::timestamp, %s::timestamp, '[)')
                ORDER BY table_id ASC
                """,
                (max(1, int(booking_duration_minutes or 60)), selected_at, selected_until),
            )
            rows = cur.fetchall()
        return [_coerce_int(row[0], 0) for row in rows if _coerce_int(row[0], 0) > 0]

    return _run_db_operation(operation)


def list_user_orders(user_id: int):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT { _ORDER_SELECT_COLUMNS }
                FROM orders
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (int(user_id),),
            )
            order_rows = cur.fetchall()
            return _hydrate_orders(cur, order_rows, include_items=False)

    return _run_db_operation(operation)


def get_user_order(user_id: int, order_id: int):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT { _ORDER_SELECT_COLUMNS }
                FROM orders
                WHERE user_id = %s AND id = %s
                LIMIT 1
                """,
                (int(user_id), int(order_id)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            orders = _hydrate_orders(cur, [row], include_items=True)
            return orders[0] if orders else None

    return _run_db_operation(operation)


def create_booking_if_available(booking: dict, *, booking_duration_minutes: int = 60):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        normalized_user_id = _coerce_int((booking or {}).get("user_id"), 0)
        normalized_table_id = _coerce_int((booking or {}).get("table_id"), 0)
        booking_date = _parse_date((booking or {}).get("date"))
        booking_time = _parse_time((booking or {}).get("time"))
        selected_at = datetime.fromisoformat(f"{booking_date.isoformat()}T{booking_time.strftime('%H:%M:%S')}")
        selected_until = selected_at + timedelta(minutes=max(1, int(booking_duration_minutes or 60)))
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("LOCK TABLE bookings IN SHARE ROW EXCLUSIVE MODE")
                cur.execute(
                    """
                    SELECT 1
                    FROM bookings
                    WHERE table_id = %s
                      AND tsrange(
                            booking_date + booking_time,
                            booking_date + booking_time + make_interval(mins => %s),
                            '[)'
                      ) && tsrange(%s::timestamp, %s::timestamp, '[)')
                    LIMIT 1
                    """,
                    (
                        normalized_table_id,
                        max(1, int(booking_duration_minutes or 60)),
                        selected_at,
                        selected_until,
                    ),
                )
                if cur.fetchone() is not None:
                    return False
                cur.execute(
                    """
                    INSERT INTO bookings (
                        user_id, table_id, booking_date, booking_time, name, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        normalized_user_id,
                        normalized_table_id,
                        booking_date,
                        booking_time,
                        _coerce_text((booking or {}).get("name")),
                        _parse_optional_datetime_utc((booking or {}).get("created_at")) or datetime.now(timezone.utc),
                    ),
                )
                return True

    return _run_db_operation(operation)


def delete_user_booking(user_id: int, table_id: int, date_str: str, time_str: str):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM bookings
                    WHERE user_id = %s
                      AND table_id = %s
                      AND booking_date = %s
                      AND booking_time = %s
                    RETURNING id
                    """,
                    (int(user_id), int(table_id), _parse_date(date_str), _parse_time(time_str)),
                )
                return cur.fetchone() is not None

    return _run_db_operation(operation)


def cancel_booking_with_orders(user_id: int, table_id: int, date_str: str, time_str: str, cancelled_at: str):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        normalized_user_id = int(user_id)
        normalized_table_id = int(table_id)
        normalized_date = _parse_date(date_str)
        normalized_time = _parse_time(time_str)
        normalized_cancelled_at = _parse_optional_datetime_utc(cancelled_at) or datetime.now(timezone.utc)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM bookings
                    WHERE user_id = %s
                      AND table_id = %s
                      AND booking_date = %s
                      AND booking_time = %s
                    RETURNING id
                    """,
                    (normalized_user_id, normalized_table_id, normalized_date, normalized_time),
                )
                booking_removed = cur.fetchone() is not None
                if not booking_removed:
                    return False
                cur.execute(
                    """
                    UPDATE orders
                    SET
                        status = 'cancelled',
                        effective_status = 'cancelled',
                        effective_status_updated_at = %s,
                        is_delivery_overdue = FALSE,
                        cancelled_at = %s
                    WHERE user_id = %s
                      AND LOWER(COALESCE(order_type, 'dine_in')) <> 'delivery'
                      AND LOWER(COALESCE(status, '')) NOT IN ('cancelled', 'canceled')
                      AND booking_table_id = %s
                      AND booking_date = %s
                      AND booking_time = %s
                    """,
                    (
                        normalized_cancelled_at,
                        normalized_cancelled_at,
                        normalized_user_id,
                        normalized_table_id,
                        normalized_date,
                        normalized_time,
                    ),
                )
                return True

    return _run_db_operation(operation)


def refresh_persisted_order_fields(*, order_ids: list[int] | None = None, user_id: int | None = None, active_only: bool = False):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        conditions = []
        params = []
        if order_ids:
            normalized_order_ids = [int(order_id) for order_id in order_ids if int(order_id) > 0]
            if not normalized_order_ids:
                return 0
            conditions.append("id = ANY(%s)")
            params.append(normalized_order_ids)
        if user_id is not None:
            conditions.append("user_id = %s")
            params.append(int(user_id))
        if active_only:
            conditions.append(
                """
                (
                    COALESCE(effective_status, '') = ''
                    OR LOWER(COALESCE(effective_status, status, '')) NOT IN ('served', 'cancelled')
                    OR (LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' AND COALESCE(is_delivery_overdue, FALSE) = FALSE)
                )
                """
            )
        where_sql = "WHERE " + " AND ".join(condition.strip() for condition in conditions) if conditions else ""
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT { _ORDER_SELECT_COLUMNS }
                    FROM orders
                    {where_sql}
                    ORDER BY id ASC
                    """,
                    tuple(params),
                )
                order_rows = cur.fetchall()
                orders = _hydrate_orders(cur, order_rows, include_items=False)
                current = current_time_value()
                updates = []
                for order in orders:
                    persisted = apply_persisted_status_fields_value(dict(order), current)
                    effective_status_changed = _coerce_text(order.get("effective_status")) != _coerce_text(persisted.get("effective_status"))
                    overdue_changed = bool(order.get("is_delivery_overdue")) != bool(persisted.get("is_delivery_overdue"))
                    if not effective_status_changed and not overdue_changed:
                        continue
                    updates.append(
                        (
                            _coerce_text(persisted.get("effective_status"), "preparing") or "preparing",
                            _coerce_text(persisted.get("effective_status_updated_at")),
                            bool(persisted.get("is_delivery_overdue")),
                            int(order["id"]),
                        )
                    )
                if updates:
                    cur.executemany(
                        """
                        UPDATE orders
                        SET
                            effective_status = %s,
                            effective_status_updated_at = %s,
                            is_delivery_overdue = %s
                        WHERE id = %s
                        """,
                        updates,
                    )
                return len(updates)

    return _run_db_operation(operation)


def create_order(order: dict):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                order_id = _next_integer_id(cur, "orders")
                now = current_time_value()
                normalized_order = apply_persisted_status_fields_value({**dict(order or {}), "id": order_id}, now)
                user_id = _coerce_int(normalized_order.get("user_id"), 0)
                if user_id <= 0:
                    raise ValueError("Order user_id is required")
                cur.execute(
                    """
                    INSERT INTO orders (
                        id,
                        user_id,
                        order_type,
                        status,
                        effective_status,
                        effective_status_updated_at,
                        is_delivery_overdue,
                        created_at,
                        items_total,
                        points_applied,
                        payable_total,
                        bonus_earned,
                        comment,
                        serving_mode,
                        serving_label,
                        serving_time,
                        booking_table_id,
                        booking_date,
                        booking_time,
                        booking_status,
                        payment_card_brand,
                        payment_card_last4,
                        payment_card_expiry,
                        delivery_name,
                        delivery_phone,
                        delivery_street,
                        delivery_house,
                        delivery_apartment,
                        delivery_entrance,
                        delivery_floor,
                        delivery_intercom,
                        delivery_comment,
                        delivery_address,
                        delivery_eta_minutes,
                        cancelled_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        order_id,
                        user_id,
                        _coerce_text(normalized_order.get("order_type"), "dine_in") or "dine_in",
                        _coerce_text(normalized_order.get("status"), "preparing") or "preparing",
                        _coerce_text(normalized_order.get("effective_status"), "preparing") or "preparing",
                        _parse_optional_datetime_utc(normalized_order.get("effective_status_updated_at")),
                        bool(normalized_order.get("is_delivery_overdue")),
                        _parse_optional_datetime_utc(normalized_order.get("created_at")) or datetime.now(timezone.utc),
                        _coerce_int(normalized_order.get("items_total"), 0),
                        _coerce_int(normalized_order.get("points_applied"), 0),
                        _coerce_int(normalized_order.get("payable_total"), 0),
                        _coerce_int(normalized_order.get("bonus_earned"), 0),
                        _coerce_text(normalized_order.get("comment")),
                        _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("mode")),
                        _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("label")),
                        _coerce_text((_coerce_dict(normalized_order.get("serving"))).get("time")),
                        _coerce_int((_coerce_dict(normalized_order.get("booking"))).get("table_id"), 0) or None,
                        _parse_optional_date((_coerce_dict(normalized_order.get("booking"))).get("date")),
                        _parse_optional_time((_coerce_dict(normalized_order.get("booking"))).get("time")),
                        _coerce_text((_coerce_dict(normalized_order.get("booking"))).get("status")),
                        _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("brand")),
                        _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("last4")),
                        _coerce_text((_coerce_dict(normalized_order.get("payment_card"))).get("expiry")),
                        _coerce_text(normalized_order.get("delivery_name")),
                        _coerce_text(normalized_order.get("delivery_phone")),
                        _coerce_text(normalized_order.get("delivery_street")),
                        _coerce_text(normalized_order.get("delivery_house")),
                        _coerce_text(normalized_order.get("delivery_apartment")),
                        _coerce_text(normalized_order.get("delivery_entrance")),
                        _coerce_text(normalized_order.get("delivery_floor")),
                        _coerce_text(normalized_order.get("delivery_intercom")),
                        _coerce_text(normalized_order.get("delivery_comment")),
                        _coerce_text(normalized_order.get("delivery_address")),
                        _coerce_int(normalized_order.get("delivery_eta_minutes"), 20),
                        _parse_optional_datetime_utc(normalized_order.get("cancelled_at")),
                    ),
                )
                item_rows = []
                for position, item in enumerate(_coerce_list(normalized_order.get("items"))):
                    if not isinstance(item, dict):
                        continue
                    item_rows.append(
                        (
                            order_id,
                            position,
                            _coerce_int(item.get("id"), 0),
                            _coerce_text(item.get("name")),
                            _coerce_int(item.get("price"), 0),
                            _coerce_int(item.get("qty"), 0),
                            _coerce_text(item.get("photo")) or None,
                        )
                    )
                if item_rows:
                    cur.executemany(
                        """
                        INSERT INTO order_items (
                            order_id, position, item_id, name, price, qty, photo
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        item_rows,
                    )
                return normalized_order

    return _run_db_operation(operation)


def apply_user_balance_delta(user_id: int, delta: int):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        normalized_user_id = int(user_id)
        normalized_delta = int(delta)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET balance = GREATEST(0, COALESCE(balance, 0) + %s)
                    WHERE id = %s
                    RETURNING id, name, phone, password_hash, balance, created_at
                    """,
                    (normalized_delta, normalized_user_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cards_by_user = _load_user_cards_by_user_ids(cur, [normalized_user_id])
        return _user_row_to_dict(row, cards_by_user)

    return _run_db_operation(operation)


def save_users(_users_path, users):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _replace_users_in_tx(cur, users)

    _run_db_operation(operation)


def replace_all_state(users, bookings, orders):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM order_items")
                cur.execute("DELETE FROM orders")
                cur.execute("DELETE FROM bookings")
                cur.execute("DELETE FROM user_cards")
                cur.execute("DELETE FROM users")
                _replace_users_in_tx(cur, users)
                _replace_bookings_in_tx(cur, bookings)
                _replace_orders_in_tx(cur, orders)

    _run_db_operation(operation)


def next_user_id(users):
    if not users:
        return 1
    return max(u.get("id", 0) for u in users) + 1


def next_order_id(orders):
    if not orders:
        return 1
    return max(o.get("id", 0) for o in orders) + 1


def ping():
    def operation():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True

    return _run_db_operation(operation)


def load_menu_items(*, include_inactive: bool = False):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            if include_inactive:
                cur.execute(
                    """
                    SELECT
                        id,
                        slug,
                        name,
                        lore,
                        type,
                        price,
                        photo_path,
                        portion_label,
                        popularity,
                        featured,
                        active
                    FROM menu_items
                    ORDER BY id ASC
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        id,
                        slug,
                        name,
                        lore,
                        type,
                        price,
                        photo_path,
                        portion_label,
                        popularity,
                        featured,
                        active
                    FROM menu_items
                    WHERE active = TRUE
                    ORDER BY id ASC
                    """
                )
            rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "slug": _coerce_text(row[1]),
                "name": _coerce_text(row[2]),
                "lore": _coerce_text(row[3]),
                "type": _coerce_text(row[4]),
                "price": _coerce_int(row[5], 0),
                "photo": _coerce_text(row[6]),
                "portion_label": _coerce_text(row[7]),
                "popularity": _coerce_int(row[8], 0),
                "featured": bool(row[9]),
                "active": bool(row[10]),
            }
            for row in rows
        ]

    return _run_db_operation(operation)


def upsert_menu_item(menu_item: dict):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM menu_items")
                next_id_row = cur.fetchone()
                item_id = _coerce_int(menu_item.get("id"), 0) or _coerce_int(next_id_row[0], 1)
                payload = dict(menu_item)
                payload["id"] = item_id
                _upsert_menu_items_in_tx(cur, [payload])
        return item_id

    return _run_db_operation(operation)


def sync_menu_items_from_disk():
    def operation():
        _ensure_schema()
        rows = _legacy_menu_item_rows()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _upsert_menu_items_in_tx(cur, rows)
                deleted_count = _delete_missing_menu_items_in_tx(cur, [row.get("id") for row in rows])
        return {
            "scanned": len(rows),
            "synced": len(rows),
            "disabled": deleted_count,
            "deleted": deleted_count,
        }

    return _run_db_operation(operation)


def load_promotions():
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    slug,
                    name,
                    lore,
                    class_name,
                    text,
                    link,
                    active,
                    priority,
                    condition,
                    reward,
                    notify,
                    reward_mode,
                    limit_per_order,
                    limit_per_user_per_day,
                    start_at,
                    end_at,
                    photo_path
                FROM promotions
                WHERE class_name IN ('akciya', 'reklama')
                ORDER BY priority DESC, id ASC
                """
            )
            rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "slug": _coerce_text(row[1]),
                "class": _coerce_text(row[4], "akciya") or "akciya",
                "name": _coerce_text(row[2]),
                "lore": _coerce_text(row[3]),
                "text": _coerce_text(row[5]),
                "link": _coerce_text(row[6]),
                "active": bool(row[7]),
                "priority": _coerce_int(row[8], 100),
                "condition": _coerce_text(row[9]),
                "reward": _coerce_text(row[10]),
                "notify": _coerce_text(row[11]),
                "reward_mode": _coerce_text(row[12], "once") or "once",
                "limit_per_order": "" if row[13] is None else str(row[13]),
                "limit_per_user_per_day": "" if row[14] is None else str(row[14]),
                "start_at": row[15].isoformat() if isinstance(row[15], datetime) else _coerce_text(row[15]),
                "end_at": row[16].isoformat() if isinstance(row[16], datetime) else _coerce_text(row[16]),
                "photo": _coerce_text(row[17]) or None,
            }
            for row in rows
        ]

    return _run_db_operation(operation)


def upsert_promotion(promotion: dict):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(id), 0) + 1 FROM promotions"
                )
                next_id_row = cur.fetchone()
                promotion_id = _coerce_int(promotion.get("id"), 0) or _coerce_int(next_id_row[0], 1)
                payload = dict(promotion)
                payload["id"] = promotion_id
                _upsert_promotions_in_tx(cur, [payload])
        return promotion_id

    return _run_db_operation(operation)


def delete_promotion(promotion_id: int):
    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM promotions WHERE id = %s", (int(promotion_id),))

    _run_db_operation(operation)


def sync_promotions_from_disk():
    def operation():
        _ensure_schema()
        rows = _legacy_promotion_rows()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                _upsert_promotions_in_tx(cur, rows)
                deleted_count = _delete_missing_promotions_in_tx(cur, [row.get("id") for row in rows])
        return {
            "scanned": len(rows),
            "synced": len(rows),
            "disabled": deleted_count,
            "deleted": deleted_count,
        }

    return _run_db_operation(operation)


def load_promotion_application_counts(*, user_id: int | None, at: datetime | None = None):
    if not user_id:
        return {}

    def operation():
        _ensure_schema()
        conn = _get_conn()
        current = at or datetime.now()
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT promotion_id, COALESCE(SUM(applied_count), 0) AS applied_total
                FROM promotion_applications
                WHERE user_id = %s
                  AND applied_at >= %s
                  AND applied_at < %s
                GROUP BY promotion_id
                """,
                (int(user_id), day_start, day_end),
            )
            rows = cur.fetchall()
        return {int(row[0]): _coerce_int(row[1], 0) for row in rows}

    return _run_db_operation(operation)


def save_promotion_applications(*, order_id: int, user_id: int, applied_promotions: list[dict], applied_at: datetime | None = None):
    if not applied_promotions:
        return

    def operation():
        _ensure_schema()
        conn = _get_conn()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM promotion_applications WHERE order_id = %s", (int(order_id),))
                rows = []
                for applied in _coerce_list(applied_promotions):
                    if not isinstance(applied, dict):
                        continue
                    promotion_id = _coerce_int(applied.get("promo_id"), 0)
                    applied_count = _coerce_int(applied.get("applied_count"), 0)
                    if promotion_id <= 0 or applied_count <= 0:
                        continue
                    reward_snapshot = json.dumps(
                        {
                            "promotion_name": _coerce_text(applied.get("name")),
                            "reward_kind": _coerce_text(applied.get("reward_kind")),
                            "notify": _coerce_text(applied.get("notify")),
                            "priority": _coerce_int(applied.get("priority"), 0),
                        },
                        ensure_ascii=False,
                    )
                    rows.append(
                        (
                            promotion_id,
                            int(user_id),
                            int(order_id),
                            applied_at or datetime.now(),
                            applied_count,
                            reward_snapshot,
                        )
                    )
                if rows:
                    cur.executemany(
                        """
                        INSERT INTO promotion_applications (
                            promotion_id,
                            user_id,
                            order_id,
                            applied_at,
                            applied_count,
                            reward_snapshot
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        rows,
                    )

    _run_db_operation(operation)
