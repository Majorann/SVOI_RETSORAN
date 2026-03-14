import os
import threading
from datetime import datetime, timedelta

import psycopg


_SCHEMA_READY = False
_SCHEMA_LOCK = threading.Lock()
_LOCAL = threading.local()


def _database_url():
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _connect():
    return psycopg.connect(_database_url(), autocommit=True, connect_timeout=5)


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


def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    state_key TEXT PRIMARY KEY,
                    state_value JSONB NOT NULL DEFAULT '[]'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                INSERT INTO app_state(state_key, state_value)
                VALUES
                    ('users', '[]'::jsonb),
                    ('bookings', '[]'::jsonb),
                    ('orders', '[]'::jsonb)
                ON CONFLICT (state_key) DO NOTHING;
                """
            )
        _SCHEMA_READY = True


def _load_state(key):
    _ensure_schema()
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT state_value FROM app_state WHERE state_key = %s", (key,))
        row = cur.fetchone()
    value = row[0] if row else []
    return value if isinstance(value, list) else []


def _save_state(key, items):
    _ensure_schema()
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_state(state_key, state_value, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (state_key)
            DO UPDATE SET state_value = EXCLUDED.state_value, updated_at = NOW()
            """,
            (key, psycopg.types.json.Jsonb(items)),
        )


def load_bookings_raw(_bookings_path):
    return _load_state("bookings")


def save_bookings(_bookings_path, bookings):
    _save_state("bookings", bookings)


def load_bookings(bookings_path, parse_datetime_fn, booking_duration_minutes):
    bookings = _load_state("bookings")
    now = datetime.now()
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
    return _load_state("orders")


def save_orders(_orders_path, orders):
    _save_state("orders", orders)


def load_users(_users_path):
    return _load_state("users")


def save_users(_users_path, users):
    _save_state("users", users)


def next_user_id(users):
    if not users:
        return 1
    return max(u.get("id", 0) for u in users) + 1


def next_order_id(orders):
    if not orders:
        return 1
    return max(o.get("id", 0) for o in orders) + 1


def ping():
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        _reset_conn()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
