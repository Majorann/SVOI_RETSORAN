"""
One-time migration: backend/*.json -> Neon app_state.

Usage (PowerShell):
  $env:DATABASE_URL="postgresql://..."; .\.venv\Scripts\python.exe ops\migrate_json_to_neon.py
"""

import json
import os
from pathlib import Path

import psycopg


BASE_DIR = Path(__file__).resolve().parents[1]
USERS_PATH = BASE_DIR / "users.json"
BOOKINGS_PATH = BASE_DIR / "bookings.json"
ORDERS_PATH = BASE_DIR / "orders.json"


def read_list(path: Path):
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def main():
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is not set")

    users = read_list(USERS_PATH)
    bookings = read_list(BOOKINGS_PATH)
    orders = read_list(ORDERS_PATH)

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
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
                ('users', %s::jsonb),
                ('bookings', %s::jsonb),
                ('orders', %s::jsonb)
            ON CONFLICT (state_key)
            DO UPDATE SET state_value = EXCLUDED.state_value, updated_at = NOW();
            """,
            (
                psycopg.types.json.Jsonb(users),
                psycopg.types.json.Jsonb(bookings),
                psycopg.types.json.Jsonb(orders),
            ),
        )

    print(
        "Migrated: users={0}, bookings={1}, orders={2}".format(
            len(users),
            len(bookings),
            len(orders),
        )
    )


if __name__ == "__main__":
    main()
