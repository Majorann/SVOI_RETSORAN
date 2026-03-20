import os
import threading
import time
from datetime import date, datetime, time as dt_time, timedelta

import psycopg
from services.business_logic import current_time_value


_SCHEMA_READY = False
_SCHEMA_LOCK = threading.Lock()
_LOCAL = threading.local()


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


def _database_url():
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _connect():
    return psycopg.connect(_database_url(), autocommit=True, connect_timeout=10)


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
            created_at TEXT NOT NULL DEFAULT ''
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
            created_at TEXT NOT NULL DEFAULT '',
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
            created_at TEXT NOT NULL DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS admin_users (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT '',
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
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_mode TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_label TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS serving_time TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS service_fee INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_table_id INTEGER")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_date DATE")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_time TIME")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS booking_status TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_brand TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_last4 TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_card_expiry TEXT NOT NULL DEFAULT ''")
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
        "CREATE INDEX IF NOT EXISTS idx_orders_booking_slot ON orders(booking_table_id, booking_date, booking_time);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_date_time ON bookings(booking_date, booking_time);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);"
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
                _coerce_text(user.get("created_at")),
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
                    _coerce_text(card.get("created_at")),
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
                    _coerce_text(booking.get("created_at")),
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
    for order in _coerce_list(orders):
        if not isinstance(order, dict):
            continue
        order_id = _coerce_int(order.get("id"), 0)
        user_id = _coerce_int(order.get("user_id"), 0)
        if order_id <= 0 or user_id <= 0:
            continue

        order_rows.append(
            (
                order_id,
                user_id,
                _coerce_text(order.get("order_type"), "dine_in") or "dine_in",
                _coerce_text(order.get("status"), "preparing") or "preparing",
                _coerce_text(order.get("created_at")),
                _coerce_int(order.get("items_total"), 0),
                _coerce_int(order.get("points_applied"), 0),
                _coerce_int(order.get("payable_total"), 0),
                _coerce_int(order.get("bonus_earned"), 0),
                _coerce_text(order.get("comment")),
                _coerce_text((_coerce_dict(order.get("serving"))).get("mode")),
                _coerce_text((_coerce_dict(order.get("serving"))).get("label")),
                _coerce_text((_coerce_dict(order.get("serving"))).get("time")),
                (
                    _coerce_int((_coerce_dict(order.get("booking"))).get("table_id"), 0)
                    or None
                ),
                _parse_optional_date((_coerce_dict(order.get("booking"))).get("date")),
                _parse_optional_time((_coerce_dict(order.get("booking"))).get("time")),
                _coerce_text((_coerce_dict(order.get("booking"))).get("status")),
                _coerce_text((_coerce_dict(order.get("payment_card"))).get("brand")),
                _coerce_text((_coerce_dict(order.get("payment_card"))).get("last4")),
                _coerce_text((_coerce_dict(order.get("payment_card"))).get("expiry")),
                _coerce_text(order.get("delivery_name")),
                _coerce_text(order.get("delivery_phone")),
                _coerce_text(order.get("delivery_street")),
                _coerce_text(order.get("delivery_house")),
                _coerce_text(order.get("delivery_apartment")),
                _coerce_text(order.get("delivery_entrance")),
                _coerce_text(order.get("delivery_floor")),
                _coerce_text(order.get("delivery_intercom")),
                _coerce_text(order.get("delivery_comment")),
                _coerce_text(order.get("delivery_address")),
                _coerce_int(order.get("delivery_eta_minutes"), 20),
                _coerce_text(order.get("cancelled_at")),
            )
        )

        position = 0
        for item in _coerce_list(order.get("items")):
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
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                _migrate_legacy_orders_columns(cur)
                _maybe_migrate_legacy_app_state(cur)
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
        return [
            {
                "user_id": row[0],
                "table_id": row[1],
                "date": row[2].isoformat() if isinstance(row[2], date) else _coerce_text(row[2]),
                "time": _time_hhmm(row[3]),
                "name": _coerce_text(row[4]),
                "created_at": _coerce_text(row[5]),
            }
            for row in rows
        ]

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
                """
                SELECT
                    id,
                    user_id,
                    order_type,
                    status,
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
                FROM orders
                ORDER BY created_at, id
                """
            )
            order_rows = cur.fetchall()
            cur.execute(
                """
                SELECT order_id, item_id, name, price, qty, photo
                FROM order_items
                ORDER BY order_id, position
                """
            )
            item_rows = cur.fetchall()

        items_by_order = {}
        for row in item_rows:
            items_by_order.setdefault(row[0], []).append(
                {
                    "id": row[1],
                    "name": _coerce_text(row[2]),
                    "price": _coerce_int(row[3], 0),
                    "qty": _coerce_int(row[4], 0),
                    "photo": row[5],
                }
            )

        orders = []
        for row in order_rows:
            order = {
                "id": row[0],
                "user_id": row[1],
                "status": _coerce_text(row[3]),
                "created_at": _coerce_text(row[4]),
                "items": items_by_order.get(row[0], []),
                "items_total": _coerce_int(row[5], 0),
                "points_applied": _coerce_int(row[6], 0),
                "payable_total": _coerce_int(row[7], 0),
                "bonus_earned": _coerce_int(row[8], 0),
                "comment": _coerce_text(row[9]),
                "serving": {
                    "mode": _coerce_text(row[10]),
                    "label": _coerce_text(row[11]),
                    **({"time": _coerce_text(row[12])} if _coerce_text(row[12]) else {}),
                },
                "booking": {
                    **({"table_id": row[13]} if row[13] is not None else {}),
                    **({"date": row[14].isoformat()} if isinstance(row[14], date) else {}),
                    **({"time": _time_hhmm(row[15])} if row[15] is not None else {}),
                    **({"status": _coerce_text(row[16])} if _coerce_text(row[16]) else {}),
                },
                "payment_card": {
                    **({"brand": _coerce_text(row[17])} if _coerce_text(row[17]) else {}),
                    **({"last4": _coerce_text(row[18])} if _coerce_text(row[18]) else {}),
                    **({"expiry": _coerce_text(row[19])} if _coerce_text(row[19]) else {}),
                },
                "delivery_name": _coerce_text(row[20]),
                "delivery_phone": _coerce_text(row[21]),
                "delivery_street": _coerce_text(row[22]),
                "delivery_house": _coerce_text(row[23]),
                "delivery_apartment": _coerce_text(row[24]),
                "delivery_entrance": _coerce_text(row[25]),
                "delivery_floor": _coerce_text(row[26]),
                "delivery_intercom": _coerce_text(row[27]),
                "delivery_comment": _coerce_text(row[28]),
                "delivery_address": _coerce_text(row[29]),
                "delivery_eta_minutes": _coerce_int(row[30], 20),
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
            cancelled_at = _coerce_text(row[31])
            if cancelled_at:
                order["cancelled_at"] = cancelled_at
            orders.append(order)
        return orders

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
            cards_by_user.setdefault(row[0], []).append(
                {
                    "brand": _coerce_text(row[1]),
                    "last4": _coerce_text(row[2]),
                    "active": bool(row[3]),
                    "holder": _coerce_text(row[4]) or None,
                    "expiry": _coerce_text(row[5]) or None,
                    "created_at": _coerce_text(row[6]),
                }
            )

        return [
            {
                "id": row[0],
                "name": _coerce_text(row[1]),
                "phone": _coerce_text(row[2]),
                "password_hash": _coerce_text(row[3]),
                "balance": _coerce_int(row[4], 0),
                "cards": cards_by_user.get(row[0], []),
                "created_at": _coerce_text(row[5]),
            }
            for row in user_rows
        ]

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
