r"""
One-time migration: backend/*.json -> Neon relational tables.

Usage (PowerShell):
  $env:DATABASE_URL="postgresql://..."; .\.venv\Scripts\python.exe ops\migrate_json_to_neon.py
"""

import json
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
USERS_PATH = BASE_DIR / "users.json"
BOOKINGS_PATH = BASE_DIR / "bookings.json"
ORDERS_PATH = BASE_DIR / "orders.json"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from storage import pg_store  # noqa: E402


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

    pg_store.replace_all_state(users, bookings, orders)

    print(
        "Migrated to relational Neon tables: users={0}, bookings={1}, orders={2}".format(
            len(users),
            len(bookings),
            len(orders),
        )
    )


if __name__ == "__main__":
    main()
