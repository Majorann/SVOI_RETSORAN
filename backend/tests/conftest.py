import importlib
import json
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "Lax")
    monkeypatch.setenv("SESSION_COOKIE_PARTITIONED", "0")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "0")
    monkeypatch.setenv("LOGIN_DEBUG_ENABLED", "0")
    monkeypatch.setenv("SESSION_DEBUG_ENABLED", "0")
    monkeypatch.setenv("MENU_CACHE_ENABLED", "0")
    monkeypatch.setenv("DB_KEEPALIVE_ENABLED", "0")

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    sys.modules.pop("app", None)
    sys.modules.pop("config", None)
    app_module = importlib.import_module("app")
    app_module.app.config["TESTING"] = True
    return app_module


@pytest.fixture()
def client(app_module):
    write_json(app_module.USERS_PATH, [])
    write_json(app_module.BOOKINGS_PATH, [])
    write_json(app_module.ORDERS_PATH, [])
    return app_module.app.test_client()
