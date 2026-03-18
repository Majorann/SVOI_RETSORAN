"""
Restaurant demo app (Flask).
- Landing, hall reservation, menu, notifications, auth
- Bookings/users stored in JSON files
"""

from flask import Flask, render_template, url_for, request, jsonify, session, redirect, g
from datetime import datetime, date, timedelta
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import json
import hashlib
import os
import re
import secrets
import threading
import time
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.auth_routes import login_route, register_route, logout_route
from routes.booking_routes import (
    availability_route,
    book_table_route,
    cancel_booking_with_orders_route,
    reserve_route,
)
from routes.profile_routes import add_card_route, delete_card_route, profile_route
from routes.orders_routes import (
    checkout_route,
    order_detail_route,
    orders_route,
    payment_confirm_route,
    payment_route,
)
from routes.menu_routes import menu_item_route, menu_route
from routes.delivery_routes import (
    delivery_checkout_route,
    delivery_confirm_route,
    delivery_menu_route,
    delivery_payment_page_route,
    delivery_payment_route,
)
from routes.main_routes import (
    index_route,
    notifications_route,
    points_route,
    reviews_route,
)
from storage.json_store import (
    load_bookings as store_load_bookings,
    load_bookings_raw as store_load_bookings_raw,
    load_orders as store_load_orders,
    load_users as store_load_users,
    next_order_id as store_next_order_id,
    next_user_id as store_next_user_id,
    save_bookings as store_save_bookings,
    save_orders as store_save_orders,
    save_users as store_save_users,
)

ACTIVE_STORAGE = "json"
_pg_store_module = None
_DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
if _DATABASE_URL:
    try:
        from storage import pg_store as _pg_store_module
    except Exception as exc:
        raise RuntimeError(f"Postgres storage import failed: {exc}") from exc

_redis_module = None
_REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
if _REDIS_URL:
    try:
        import redis as _redis_module
    except Exception as exc:
        print(f"[cache] redis import failed ({exc}), menu cache disabled")
from services.business_logic import (
    build_order_status_timeline_value,
    compute_serve_datetime_value,
    get_user_preparing_orders_value,
    latest_active_order_status_value,
    latest_user_booking_entry,
    latest_user_booking_status_value,
    list_active_order_statuses_value,
    order_cooking_window_value,
    overlaps_booking_window,
    parse_datetime_value,
    parse_iso_datetime_value,
    parse_serving_option_value,
    resolve_order_items_value,
)
from config import (
    BOOKINGS_PATH,
    BOOKING_DURATION_MINUTES,
    DATA_DIR,
    MENU_ITEMS_PATH,
    MENU_META_NAME,
    MENU_PHOTO_NAMES,
    NEWS_CARDS,
    POPULAR_MENU_LIMIT,
    ORDERS_PATH,
    ORDER_STATUS_STEPS,
    PROMO_ITEMS_PATH,
    PROMO_META_NAME,
    PROMO_PHOTO_NAMES,
    TABLES,
    USERS_PATH,
    WALLS,
)
from models import MenuItem, PromoItem


def _env_int_early(name: str, default: int) -> int:
    value = (os.getenv(name) or "").strip()
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


POSTGRES_STARTUP_RETRIES = max(1, _env_int_early("POSTGRES_STARTUP_RETRIES", 4))
POSTGRES_STARTUP_RETRY_DELAY_SECONDS = max(
    1,
    _env_int_early("POSTGRES_STARTUP_RETRY_DELAY_SECONDS", 3),
)


def _activate_postgres_storage():
    global ACTIVE_STORAGE
    global store_load_bookings
    global store_load_bookings_raw
    global store_load_orders
    global store_load_users
    global store_next_order_id
    global store_next_user_id
    global store_save_bookings
    global store_save_orders
    global store_save_users

    if not _DATABASE_URL:
        return

    if _pg_store_module is None:
        raise RuntimeError("DATABASE_URL is set, but postgres storage is unavailable")

    last_error = None
    for attempt in range(POSTGRES_STARTUP_RETRIES):
        try:
            # Neon may need a few seconds to wake up on a cold start.
            _pg_store_module.load_users(USERS_PATH)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if attempt == POSTGRES_STARTUP_RETRIES - 1:
                break
            print(
                "[storage] postgres startup retry {0}/{1} failed ({2}), waiting {3}s".format(
                    attempt + 1,
                    POSTGRES_STARTUP_RETRIES,
                    exc,
                    POSTGRES_STARTUP_RETRY_DELAY_SECONDS,
                )
            )
            time.sleep(POSTGRES_STARTUP_RETRY_DELAY_SECONDS)

    if last_error is not None:
        raise RuntimeError(f"Postgres connect failed during startup: {last_error}") from last_error

    store_load_bookings = _pg_store_module.load_bookings
    store_load_bookings_raw = _pg_store_module.load_bookings_raw
    store_load_orders = _pg_store_module.load_orders
    store_load_users = _pg_store_module.load_users
    store_next_order_id = _pg_store_module.next_order_id
    store_next_user_id = _pg_store_module.next_user_id
    store_save_bookings = _pg_store_module.save_bookings
    store_save_orders = _pg_store_module.save_orders
    store_save_users = _pg_store_module.save_users
    ACTIVE_STORAGE = "postgres"


def _assert_storage_configuration():
    if _DATABASE_URL and ACTIVE_STORAGE != "postgres":
        raise RuntimeError("DATABASE_URL is set, but backend is not using Postgres")

    if not _DATABASE_URL and ACTIVE_STORAGE != "json":
        raise RuntimeError("DATABASE_URL is not set, but backend is not using JSON storage")


_activate_postgres_storage()
_assert_storage_configuration()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
# Секрет для сессий (в проде заменить)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "ueW2Td8Y-PNMoNazTFEkVLUDxqIEoyzN66MtcjACM5d7AxkZYaYDL9RtFEF5F2vedmzvzJ-P6vGflZYxfzu7EA",
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
# На hosted-платформах (в т.ч. HF Spaces в iframe) Lax может блокировать сессию.
is_hf_space = bool(os.getenv("SPACE_ID") or os.getenv("HF_SPACE_ID"))
public_base_url = env_str("PUBLIC_BASE_URL", "")
default_samesite = "None" if is_hf_space else "Lax"
session_samesite = env_str("SESSION_COOKIE_SAMESITE", default_samesite)
default_secure_cookie = is_hf_space or public_base_url.lower().startswith("https://")
if session_samesite.strip().lower() == "none":
    # Browsers require SameSite=None cookies to be marked Secure.
    default_secure_cookie = True
app.config["SESSION_COOKIE_SAMESITE"] = session_samesite
app.config["SESSION_COOKIE_SECURE"] = env_bool("SESSION_COOKIE_SECURE", default_secure_cookie)
app.config["SESSION_COOKIE_PARTITIONED"] = env_bool("SESSION_COOKIE_PARTITIONED", is_hf_space)
app.config["PREFERRED_URL_SCHEME"] = "https" if app.config["SESSION_COOKIE_SECURE"] else "http"
if env_bool("TRUST_PROXY_HEADERS", True):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
AUTH_MODE = env_str("AUTH_MODE", "hybrid").lower()
if AUTH_MODE not in {"token", "hybrid", "session"}:
    AUTH_MODE = "hybrid"
TOKEN_AUTH_ENABLED = AUTH_MODE in {"token", "hybrid"}
COOKIE_AUTH_ENABLED = AUTH_MODE in {"hybrid", "session"}
AUTH_TOKEN_STORAGE_KEY = env_str("AUTH_TOKEN_STORAGE_KEY", "auth_token")
AUTH_TOKEN_QUERY_PARAM = env_str("AUTH_TOKEN_QUERY_PARAM", "auth_token")
AUTH_TOKEN_MAX_AGE_SECONDS = max(300, env_int("AUTH_TOKEN_MAX_AGE_SECONDS", 30 * 24 * 60 * 60))
_AUTH_TOKEN_SERIALIZER = URLSafeTimedSerializer(app.secret_key, salt="auth-token-v1")
AUTH_SESSION_COOKIE_NAME = env_str("AUTH_SESSION_COOKIE_NAME", "auth_session")
AUTH_SESSION_COOKIE_MAX_AGE_SECONDS = max(
    300,
    env_int("AUTH_SESSION_COOKIE_MAX_AGE_SECONDS", 30 * 24 * 60 * 60),
)
_AUTH_SESSION_SERIALIZER = URLSafeTimedSerializer(app.secret_key, salt="auth-session-v1")
CHECKOUT_PREVIEW_MAX_AGE_SECONDS = max(300, env_int("CHECKOUT_PREVIEW_MAX_AGE_SECONDS", 30 * 60))
_CHECKOUT_PREVIEW_SERIALIZER = URLSafeTimedSerializer(app.secret_key, salt="checkout-preview-v1")
_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.RLock()
_ORDER_PRUNE_LOCK = threading.RLock()
_LAST_ORDER_PRUNE_AT = 0.0
ORDER_RETENTION_DAYS = max(0, env_int("ORDER_RETENTION_DAYS", 7))
ORDER_PRUNE_INTERVAL_SECONDS = max(15, env_int("ORDER_PRUNE_INTERVAL_SECONDS", 60))
LOGIN_DEBUG_ENABLED = env_bool("LOGIN_DEBUG_ENABLED", False)
LOGIN_DEBUG_LOG_PATH = Path(
    env_str("LOGIN_DEBUG_LOG_PATH", str(DATA_DIR / "login_failed_attempts.jsonl"))
)
_LOGIN_DEBUG_LOCK = threading.RLock()
SESSION_DEBUG_ENABLED = env_bool("SESSION_DEBUG_ENABLED", False)
SESSION_DEBUG_LOG_PATH = Path(
    env_str("SESSION_DEBUG_LOG_PATH", str(DATA_DIR / "session_debug.jsonl"))
)
_SESSION_DEBUG_LOCK = threading.RLock()
DB_KEEPALIVE_ENABLED = env_bool("DB_KEEPALIVE_ENABLED", True)
DB_KEEPALIVE_INTERVAL_SECONDS = max(60, env_int("DB_KEEPALIVE_INTERVAL_SECONDS", 600))
_DB_KEEPALIVE_STARTED = False
_DB_KEEPALIVE_LOCK = threading.Lock()
DEBUG_STORAGE_ENABLED = env_bool("DEBUG_STORAGE_ENABLED", False)
MENU_CACHE_ENABLED = env_bool("MENU_CACHE_ENABLED", True)
MENU_CACHE_TTL_SECONDS = max(30, env_int("MENU_CACHE_TTL_SECONDS", 600))
MENU_CACHE_KEY = env_str("MENU_CACHE_KEY", "menu:items:v1")
_REDIS_CLIENT = None
_REDIS_CLIENT_LOCK = threading.Lock()

print(
    "[storage] backend={0} users={1} bookings={2} orders={3} cookie_secure={4} cookie_samesite={5} cookie_partitioned={6} login_debug={7} session_debug={8} auth_mode={9} auth_token_key={10} auth_session_cookie={11}".format(
        ACTIVE_STORAGE,
        USERS_PATH,
        BOOKINGS_PATH,
        ORDERS_PATH,
        app.config["SESSION_COOKIE_SECURE"],
        app.config["SESSION_COOKIE_SAMESITE"],
        app.config["SESSION_COOKIE_PARTITIONED"],
        LOGIN_DEBUG_ENABLED,
        SESSION_DEBUG_ENABLED,
        AUTH_MODE,
        AUTH_TOKEN_QUERY_PARAM,
        AUTH_SESSION_COOKIE_NAME,
    )
)
if LOGIN_DEBUG_ENABLED:
    print(f"[auth-debug] failed login log path={LOGIN_DEBUG_LOG_PATH}")
if SESSION_DEBUG_ENABLED:
    print(f"[session-debug] session log path={SESSION_DEBUG_LOG_PATH}")


def debug_login_failure(reason: str, phone_raw: str = "", normalized_phone: str | None = None):
    if not LOGIN_DEBUG_ENABLED:
        return

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "reason": reason,
        "phone_raw": phone_raw,
        "normalized_phone": normalized_phone,
        "request": {
            "method": request.method,
            "path": request.path,
            "scheme": request.scheme,
            "host": request.host,
            "remote_addr": request.remote_addr,
            "forwarded_for": request.headers.get("X-Forwarded-For"),
            "real_ip": request.headers.get("X-Real-Ip"),
            "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
            "user_agent": request.headers.get("User-Agent"),
            "referer": request.headers.get("Referer"),
            "origin": request.headers.get("Origin"),
        },
    }

    try:
        LOGIN_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(log_entry, ensure_ascii=False)
        with _LOGIN_DEBUG_LOCK:
            with LOGIN_DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")
    except OSError as exc:
        print(f"[auth-debug] failed to write login debug log ({exc})")


def log_session_debug(event: str, extra: dict | None = None):
    if not SESSION_DEBUG_ENABLED:
        return

    session_keys = sorted(session.keys())
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        "request": {
            "method": request.method,
            "path": request.path,
            "query_string": request.query_string.decode("utf-8", errors="ignore"),
            "scheme": request.scheme,
            "host": request.host,
            "remote_addr": request.remote_addr,
            "forwarded_for": request.headers.get("X-Forwarded-For"),
            "real_ip": request.headers.get("X-Real-Ip"),
            "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
            "forwarded_proto": request.headers.get("X-Forwarded-Proto"),
            "user_agent": request.headers.get("User-Agent"),
            "referer": request.headers.get("Referer"),
            "origin": request.headers.get("Origin"),
        },
        "session": {
            "has_user_id": "user_id" in session,
            "user_id": session.get("user_id"),
            "user_name": session.get("user_name"),
            "has_csrf_token": "csrf_token" in session,
            "session_keys": session_keys,
            "permanent": session.permanent,
            "cookie_secure": app.config["SESSION_COOKIE_SECURE"],
            "cookie_samesite": app.config["SESSION_COOKIE_SAMESITE"],
            "cookie_partitioned": app.config["SESSION_COOKIE_PARTITIONED"],
        },
    }
    if extra:
        log_entry["extra"] = extra

    try:
        SESSION_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(log_entry, ensure_ascii=False)
        with _SESSION_DEBUG_LOCK:
            with SESSION_DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")
    except OSError as exc:
        print(f"[session-debug] failed to write session debug log ({exc})")


def issue_auth_token(user_id: int) -> str:
    return _AUTH_TOKEN_SERIALIZER.dumps({"user_id": int(user_id), "v": 1})


def verify_auth_token(token: str | None):
    if not token:
        return None
    try:
        payload = _AUTH_TOKEN_SERIALIZER.loads(token, max_age=AUTH_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    try:
        user_id = int(payload.get("user_id"))
    except (TypeError, ValueError, AttributeError):
        return None
    if user_id <= 0:
        return None
    return {"user_id": user_id}


def issue_auth_session_cookie(user_id: int) -> str:
    return _AUTH_SESSION_SERIALIZER.dumps({"user_id": int(user_id), "v": 1})


def verify_auth_session_cookie(cookie_value: str | None):
    if not cookie_value:
        return None
    try:
        payload = _AUTH_SESSION_SERIALIZER.loads(
            cookie_value,
            max_age=AUTH_SESSION_COOKIE_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return None
    try:
        user_id = int(payload.get("user_id"))
    except (TypeError, ValueError, AttributeError):
        return None
    if user_id <= 0:
        return None
    return {"user_id": user_id}


def issue_checkout_preview_token(preview: dict) -> str:
    return _CHECKOUT_PREVIEW_SERIALIZER.dumps({"preview": preview, "v": 1})


def verify_checkout_preview_token(token: str | None):
    if not token:
        return None
    try:
        payload = _CHECKOUT_PREVIEW_SERIALIZER.loads(
            token,
            max_age=CHECKOUT_PREVIEW_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return None
    preview = payload.get("preview")
    return preview if isinstance(preview, dict) else None


def extract_request_auth_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token, "authorization"

    query_token = (request.args.get(AUTH_TOKEN_QUERY_PARAM) or "").strip()
    if query_token:
        return query_token, "query"

    form_token = (request.form.get(AUTH_TOKEN_QUERY_PARAM) or "").strip()
    if form_token:
        return form_token, "form"

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        json_token = str(payload.get("token") or "").strip()
        if json_token:
            return json_token, "json"

    return None, None


def normalize_next_url(raw_url: str | None):
    fallback = url_for("index")
    if not raw_url:
        return fallback

    candidate = str(raw_url).strip()
    if not candidate:
        return fallback

    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return fallback

    path = parts.path or "/"
    if not path.startswith("/"):
        return fallback

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != AUTH_TOKEN_QUERY_PARAM
    ]
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit(("", "", path, query, parts.fragment))


def append_auth_token_to_url(raw_url: str | None, token: str | None):
    if not raw_url or not token:
        return raw_url

    parts = urlsplit(str(raw_url))
    if parts.scheme or parts.netloc:
        request_origin = f"{request.scheme}://{request.host}"
        target_origin = f"{parts.scheme}://{parts.netloc}"
        if target_origin != request_origin:
            return raw_url

    path = parts.path or "/"
    if path.startswith("/static/"):
        return raw_url

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != AUTH_TOKEN_QUERY_PARAM
    ]
    filtered_query.append((AUTH_TOKEN_QUERY_PARAM, token))
    next_query = urlencode(filtered_query, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, path, next_query, parts.fragment))


def get_navigation_auth_token():
    if not TOKEN_AUTH_ENABLED:
        return None
    token, _source = extract_request_auth_token()
    payload = verify_auth_token(token)
    if payload is not None:
        return token

    user_id = session.get("user_id")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None
    return issue_auth_token(user_id)


def apply_session_user(user: dict):
    preserved_csrf = session.get("csrf_token")
    session.clear()
    if preserved_csrf:
        session["csrf_token"] = preserved_csrf
    session["user_id"] = user.get("id")
    session["user_name"] = user.get("name")
    session.permanent = True


def build_auth_session_cookie_kwargs(max_age=None):
    cookie_kwargs = {
        "httponly": True,
        "path": "/",
        "secure": app.config["SESSION_COOKIE_SECURE"],
        "samesite": app.config["SESSION_COOKIE_SAMESITE"],
    }
    if max_age is not None:
        cookie_kwargs["max_age"] = max_age
    if app.config["SESSION_COOKIE_PARTITIONED"]:
        cookie_kwargs["partitioned"] = True
    return cookie_kwargs


def set_auth_session_cookie(response, user_id: int):
    cookie_kwargs = build_auth_session_cookie_kwargs(
        max_age=AUTH_SESSION_COOKIE_MAX_AGE_SECONDS
    )
    cookie_value = issue_auth_session_cookie(user_id)
    try:
        response.set_cookie(
            AUTH_SESSION_COOKIE_NAME,
            cookie_value,
            **cookie_kwargs,
        )
    except TypeError:
        cookie_kwargs.pop("partitioned", None)
        response.set_cookie(
            AUTH_SESSION_COOKIE_NAME,
            cookie_value,
            **cookie_kwargs,
        )


def clear_auth_session_cookie(response):
    cookie_kwargs = build_auth_session_cookie_kwargs()
    try:
        response.set_cookie(
            AUTH_SESSION_COOKIE_NAME,
            "",
            expires=0,
            max_age=0,
            **cookie_kwargs,
        )
    except TypeError:
        cookie_kwargs.pop("partitioned", None)
        response.set_cookie(
            AUTH_SESSION_COOKIE_NAME,
            "",
            expires=0,
            max_age=0,
            **cookie_kwargs,
        )


def _set_request_user(user: dict | None):
    g.current_user_loaded = True
    g.current_user = user
    try:
        g.current_user_id = int(user.get("id")) if user else None
    except (TypeError, ValueError, AttributeError):
        g.current_user_id = None


def get_request_user(user_id=None):
    try:
        normalized_user_id = int(user_id if user_id is not None else session.get("user_id"))
    except (TypeError, ValueError):
        _set_request_user(None)
        return None

    if normalized_user_id <= 0:
        _set_request_user(None)
        return None

    if getattr(g, "current_user_loaded", False) and getattr(g, "current_user_id", None) == normalized_user_id:
        return getattr(g, "current_user", None)

    user = next((u for u in load_users() if u.get("id") == normalized_user_id), None)
    _set_request_user(user)
    return user


def get_request_notification_data():
    if getattr(g, "notifications_loaded", False):
        return getattr(g, "notification_bookings", []), getattr(g, "notification_preparing_orders", [])

    user_id = session.get("user_id")
    if not user_id:
        g.notifications_loaded = True
        g.notification_bookings = []
        g.notification_preparing_orders = []
        return g.notification_bookings, g.notification_preparing_orders

    bookings = [b for b in load_bookings() if b.get("user_id") == user_id]
    preparing_orders = get_user_preparing_orders(user_id)
    g.notifications_loaded = True
    g.notification_bookings = bookings
    g.notification_preparing_orders = preparing_orders
    return bookings, preparing_orders


def _db_keepalive_loop():
    while True:
        time.sleep(DB_KEEPALIVE_INTERVAL_SECONDS)
        if ACTIVE_STORAGE != "postgres" or _pg_store_module is None:
            continue
        try:
            _pg_store_module.ping()
            print("[storage] postgres keepalive ok")
        except Exception as exc:
            print(f"[storage] postgres keepalive failed ({exc})")


def start_db_keepalive():
    global _DB_KEEPALIVE_STARTED
    if not DB_KEEPALIVE_ENABLED or ACTIVE_STORAGE != "postgres" or _pg_store_module is None:
        return

    with _DB_KEEPALIVE_LOCK:
        if _DB_KEEPALIVE_STARTED:
            return
        worker = threading.Thread(
            target=_db_keepalive_loop,
            name="postgres-keepalive",
            daemon=True,
        )
        worker.start()
        _DB_KEEPALIVE_STARTED = True
        print(
            "[storage] postgres keepalive started interval={0}s".format(
                DB_KEEPALIVE_INTERVAL_SECONDS
            )
        )


def get_redis_client():
    global _REDIS_CLIENT
    if not MENU_CACHE_ENABLED or not _REDIS_URL or _redis_module is None:
        return None

    with _REDIS_CLIENT_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        try:
            client = _redis_module.Redis.from_url(
                _REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            client.ping()
        except Exception as exc:
            print(f"[cache] redis connect failed ({exc}), menu cache disabled")
            return None
        _REDIS_CLIENT = client
        print(
            "[cache] redis menu cache enabled ttl={0}s key={1}".format(
                MENU_CACHE_TTL_SECONDS,
                MENU_CACHE_KEY,
            )
        )
        return _REDIS_CLIENT


def load_menu_items_from_disk():
    items_with_meta = []
    if not MENU_ITEMS_PATH.exists():
        return []

    for item_dir in sorted(MENU_ITEMS_PATH.iterdir()):
        if not item_dir.is_dir():
            continue
        meta_path = item_dir / MENU_META_NAME
        photo_name = resolve_photo_name(item_dir, MENU_PHOTO_NAMES)
        if not meta_path.exists() or not photo_name:
            continue

        meta = parse_menu_meta(meta_path)
        menu_item = parse_menu_item(meta, item_dir.name, photo_name)
        if menu_item is None:
            continue
        items_with_meta.append((menu_item, meta_path))

    items = ensure_unique_menu_item_ids(items_with_meta)
    items.sort(key=lambda item: item["id"])
    return items


def update_menu_meta_id(meta_path: Path, new_id: int):
    raw_text = read_text_with_fallback(meta_path, ("utf-8", "utf-8-sig", "cp1251"))
    lines = raw_text.splitlines(keepends=True)
    updated = False

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, _value = raw_line.split("=", 1)
        normalized_key = key.strip().lower().lstrip("\ufeff")
        if normalized_key != "id":
            continue
        line_ending = "\n" if raw_line.endswith("\n") else ""
        lines[index] = f"id={int(new_id)}{line_ending}"
        updated = True
        break

    if not updated:
        prefix = f"id={int(new_id)}\n"
        lines.insert(0, prefix)

    payload = "".join(lines)
    if payload == raw_text:
        return

    tmp_path = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, meta_path)


def ensure_unique_menu_item_ids(items_with_meta):
    items = [item for item, _meta_path in items_with_meta]
    used_ids = set()
    max_id = max(
        (
            item_id
            for item, _meta_path in items_with_meta
            for item_id in [item.get("id")]
            if isinstance(item_id, int) and item_id > 0
        ),
        default=0,
    )

    for item, meta_path in items_with_meta:
        item_id = item.get("id")
        if isinstance(item_id, int) and item_id > 0 and item_id not in used_ids:
            used_ids.add(item_id)
            continue

        new_id = max_id + 1
        while new_id in used_ids:
            new_id += 1

        if isinstance(item_id, int) and item_id > 0:
            message = "[menu] duplicate item id detected for '{0}': {1} -> {2}"
        else:
            message = "[menu] invalid item id detected for '{0}': {1} -> {2}"

        print(
            message.format(
                item.get("name", "unknown"),
                item_id,
                new_id,
            )
        )
        item["id"] = new_id
        try:
            update_menu_meta_id(meta_path, new_id)
        except OSError as exc:
            print(
                "[menu] failed to persist item id for '{0}' in {1} ({2})".format(
                    item.get("name", "unknown"),
                    meta_path,
                    exc,
                )
            )
        used_ids.add(new_id)
        max_id = new_id

    return items


def load_menu_items():
    client = get_redis_client()
    if client is not None:
        try:
            cached_payload = client.get(MENU_CACHE_KEY)
            if cached_payload:
                items = json.loads(cached_payload)
                if isinstance(items, list):
                    return items
        except Exception as exc:
            print(f"[cache] redis menu read failed ({exc}), fallback=disk")

    items = load_menu_items_from_disk()

    if client is not None:
        try:
            client.setex(
                MENU_CACHE_KEY,
                MENU_CACHE_TTL_SECONDS,
                json.dumps(items, ensure_ascii=False),
            )
        except Exception as exc:
            print(f"[cache] redis menu write failed ({exc})")
    return items


@contextmanager
def json_file_lock(path: Path, timeout_seconds: float = 5.0, poll_interval: float = 0.05):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        process_lock = _PROCESS_LOCKS.setdefault(lock_key, threading.RLock())

    with process_lock:
        started_at = time.monotonic()
        lock_fd = None
        while True:
            try:
                lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(lock_fd, f"{os.getpid()}:{threading.get_ident()}".encode("utf-8"))
                os.close(lock_fd)
                lock_fd = None
                break
            except FileExistsError:
                if time.monotonic() - started_at >= timeout_seconds:
                    raise TimeoutError(f"Timeout while waiting lock for {path.name}")
                time.sleep(poll_interval)

        try:
            yield
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


@contextmanager
def storage_write_lock(path: Path, timeout_seconds: float = 5.0, poll_interval: float = 0.05):
    if ACTIVE_STORAGE == "json":
        with json_file_lock(path, timeout_seconds=timeout_seconds, poll_interval=poll_interval):
            yield
        return
    yield


@app.before_request
def restore_auth_from_cookies_or_token():
    if request.endpoint == "static":
        return

    current_user_id = session.get("user_id")
    auth_candidate = None

    if COOKIE_AUTH_ENABLED:
        cookie_value = request.cookies.get(AUTH_SESSION_COOKIE_NAME)
        if cookie_value:
            payload = verify_auth_session_cookie(cookie_value)
            if payload is None:
                g.clear_auth_session_cookie = True
                if SESSION_DEBUG_ENABLED:
                    log_session_debug(
                        "auth_session_cookie_invalid",
                        extra={"cookie_name": AUTH_SESSION_COOKIE_NAME},
                    )
            else:
                auth_candidate = {
                    "user_id": payload["user_id"],
                    "source": "auth_session_cookie",
                }

    if auth_candidate is None and TOKEN_AUTH_ENABLED:
        token, token_source = extract_request_auth_token()
        if token:
            payload = verify_auth_token(token)
            if payload is None:
                if SESSION_DEBUG_ENABLED:
                    log_session_debug("auth_token_invalid", extra={"source": token_source})
            else:
                auth_candidate = {
                    "user_id": payload["user_id"],
                    "source": f"auth_token:{token_source}",
                }

    if auth_candidate is None:
        return

    user_id = auth_candidate["user_id"]
    source = auth_candidate["source"]
    if current_user_id == user_id and session.get("user_name"):
        session.permanent = True
        if SESSION_DEBUG_ENABLED:
            log_session_debug(
                "auth_session_confirmed",
                extra={"source": source, "user_id": user_id},
            )
        return

    user = get_request_user(user_id)
    if not user:
        if source == "auth_session_cookie":
            g.clear_auth_session_cookie = True
        if SESSION_DEBUG_ENABLED:
            log_session_debug("auth_user_missing", extra={"source": source, "user_id": user_id})
        return

    apply_session_user(user)
    _set_request_user(user)
    if SESSION_DEBUG_ENABLED:
        log_session_debug(
            "auth_session_restored",
            extra={
                "source": source,
                "user_id": user_id,
                "previous_user_id": current_user_id,
            },
        )


@app.before_request
def hydrate_current_user():
    if request.endpoint == "static":
        return

    user_id = session.get("user_id")
    if not user_id:
        _set_request_user(None)
        return

    get_request_user(user_id)


@app.before_request
def keep_user_session():
    if request.endpoint == "static":
        return

    if SESSION_DEBUG_ENABLED and request.endpoint in {"login", "profile", "index"}:
        log_session_debug("before_request")

    user_id = session.get("user_id")
    if not user_id:
        return

    session.permanent = True
    if session.get("user_name"):
        return

    user = get_request_user(user_id)
    if not user:
        # Do not hard-drop session on a single miss.
        # A concurrent JSON write may produce a transient empty read.
        return
    if not session.get("user_name"):
        session["user_name"] = user.get("name")
        if SESSION_DEBUG_ENABLED and request.endpoint in {"login", "profile", "index"}:
            log_session_debug("user_name_restored")


@app.before_request
def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)


@app.before_request
def validate_csrf_token():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if request.endpoint == "static":
        return

    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if token and token == session.get("csrf_token"):
        return

    if request.is_json:
        return jsonify({"ok": False, "error": "CSRF token is missing or invalid."}), 400
    return redirect(url_for("index"))


@app.after_request
def preserve_auth_token_on_redirects(response):
    if AUTH_MODE != "token":
        return response
    if not (300 <= response.status_code < 400):
        return response

    location = response.headers.get("Location")
    if not location:
        return response

    token = get_navigation_auth_token()
    if not token:
        return response

    next_location = append_auth_token_to_url(location, token)
    if next_location and next_location != location:
        response.headers["Location"] = next_location
    return response


@app.after_request
def sync_auth_session_cookie_response(response):
    if request.endpoint == "static":
        return response

    session_user_id = session.get("user_id")
    try:
        normalized_user_id = int(session_user_id)
    except (TypeError, ValueError):
        normalized_user_id = None

    if COOKIE_AUTH_ENABLED and normalized_user_id and normalized_user_id > 0:
        set_auth_session_cookie(response, normalized_user_id)
        return response

    has_auth_cookie = bool(request.cookies.get(AUTH_SESSION_COOKIE_NAME))
    if has_auth_cookie or getattr(g, "clear_auth_session_cookie", False):
        clear_auth_session_cookie(response)
    return response

@app.route("/")
def index():
    return index_route(
        load_bookings,
        load_promo_items,
        promo_items_to_news_cards,
        NEWS_CARDS,
        load_menu_items,
        get_user_preparing_orders,
        list_active_order_statuses,
        load_users,
        POPULAR_MENU_LIMIT,
    )


@app.get("/api/order-statuses")
def api_order_statuses():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": True, "order_statuses": []})
    return jsonify(
        {
            "ok": True,
            "order_statuses": list_active_order_statuses(user_id),
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }
    )


@app.get("/api/index-summary")
def api_index_summary():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": True,
                "authenticated": False,
                "points_balance": 0,
                "points_balance_formatted": "0",
                "order_statuses": [],
                "server_time": datetime.now().isoformat(timespec="seconds"),
            }
        )

    user = get_request_user(user_id)
    points_balance = int((user or {}).get("balance", 0) or 0)
    return jsonify(
        {
            "ok": True,
            "authenticated": True,
            "points_balance": points_balance,
            "points_balance_formatted": f"{points_balance:,}".replace(",", " "),
            "order_statuses": list_active_order_statuses(user_id),
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }
    )


@app.get("/debug/storage")
def debug_storage():
    if not DEBUG_STORAGE_ENABLED:
        return render_template("placeholder.html", title="Страница не найдена"), 404
    users = load_users()
    bookings = load_bookings_raw()
    orders = load_orders()
    return jsonify(
        {
            "ok": True,
            "storage_backend": ACTIVE_STORAGE,
            "users_path": str(USERS_PATH),
            "bookings_path": str(BOOKINGS_PATH),
            "orders_path": str(ORDERS_PATH),
            "users_count": len(users),
            "bookings_count": len(bookings),
            "orders_count": len(orders),
            "last_user_id": users[-1].get("id") if users else None,
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }
    )


@app.get("/debug/session")
def debug_session():
    if not SESSION_DEBUG_ENABLED:
        return render_template("placeholder.html", title="Страница не найдена"), 404
    return jsonify(
        {
            "ok": True,
            "request": {
                "method": request.method,
                "path": request.path,
                "scheme": request.scheme,
                "host": request.host,
                "remote_addr": request.remote_addr,
                "forwarded_for": request.headers.get("X-Forwarded-For"),
                "real_ip": request.headers.get("X-Real-Ip"),
                "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
                "forwarded_proto": request.headers.get("X-Forwarded-Proto"),
                "user_agent": request.headers.get("User-Agent"),
                "referer": request.headers.get("Referer"),
                "origin": request.headers.get("Origin"),
            },
            "session": {
                "has_user_id": "user_id" in session,
                "user_id": session.get("user_id"),
                "user_name": session.get("user_name"),
                "has_csrf_token": "csrf_token" in session,
                "session_keys": sorted(session.keys()),
                "permanent": session.permanent,
            },
            "cookies": {
                "session_cookie_present": bool(request.cookies.get(app.config.get("SESSION_COOKIE_NAME", "session"))),
                "cookie_name": app.config.get("SESSION_COOKIE_NAME", "session"),
                "secure": app.config["SESSION_COOKIE_SECURE"],
                "samesite": app.config["SESSION_COOKIE_SAMESITE"],
                "partitioned": app.config["SESSION_COOKIE_PARTITIONED"],
                "auth_session_cookie_present": bool(request.cookies.get(AUTH_SESSION_COOKIE_NAME)),
                "auth_session_cookie_name": AUTH_SESSION_COOKIE_NAME,
            },
            "auth": {
                "mode": AUTH_MODE,
                "token_enabled": TOKEN_AUTH_ENABLED,
                "cookie_enabled": COOKIE_AUTH_ENABLED,
            },
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }
    )


@app.get("/auth-bridge")
def auth_bridge():
    next_url = normalize_next_url(request.args.get("next"))
    return render_template("auth-bridge.html", next_url=next_url)


@app.post("/api/auth/session")
def api_auth_session():
    if not TOKEN_AUTH_ENABLED:
        return jsonify({"ok": False, "error": "Legacy token sync is disabled."}), 404

    token, source = extract_request_auth_token()
    payload = verify_auth_token(token)
    if payload is None:
        if SESSION_DEBUG_ENABLED and token:
            log_session_debug(
                "auth_token_invalid",
                extra={"source": source, "endpoint": "api_auth_session"},
            )
        return jsonify({"ok": False, "error": "Authorization token is missing or invalid."}), 401

    user_id = payload["user_id"]
    user = get_request_user(user_id)
    if not user:
        if SESSION_DEBUG_ENABLED:
            log_session_debug(
                "auth_token_user_missing",
                extra={"source": source, "user_id": user_id, "endpoint": "api_auth_session"},
            )
        return jsonify({"ok": False, "error": "User not found."}), 401

    previous_user_id = session.get("user_id")
    apply_session_user(user)
    _set_request_user(user)
    if SESSION_DEBUG_ENABLED:
        log_session_debug(
            "auth_token_session_synced",
            extra={"source": source, "user_id": user_id, "previous_user_id": previous_user_id},
        )
    return jsonify({"ok": True, "user_id": user_id, "user_name": user.get("name")})


@app.route("/reserve")
def reserve():
    return reserve_route(load_bookings, parse_datetime, overlaps_booking, TABLES, WALLS)


@app.get("/availability")
def availability():
    return availability_route(load_bookings, parse_datetime, overlaps_booking)


@app.route("/points")
def points():
    return points_route()


@app.route("/profile")
def profile():
    return profile_route(load_users, load_bookings)


@app.route("/delivery")
def delivery():
    return delivery_menu_route(load_menu_items)


@app.get("/delivery/checkout")
def delivery_checkout():
    return delivery_checkout_route(load_users)


@app.post("/delivery/confirm")
def delivery_confirm():
    return delivery_confirm_route(
        storage_write_lock,
        ORDERS_PATH,
        load_orders,
        next_order_id,
        save_orders,
        verify_checkout_preview_token,
    )


@app.post("/delivery/payment")
def delivery_payment():
    return delivery_payment_route(resolve_order_items, issue_checkout_preview_token)


@app.get("/delivery/payment")
def delivery_payment_page():
    return delivery_payment_page_route(verify_checkout_preview_token)


@app.route("/notifications")
def notifications():
    return notifications_route(load_bookings, get_user_preparing_orders)


@app.route("/login", methods=["GET", "POST"])
def login():
    return login_route(
        load_users,
        hash_password,
        debug_login_failure,
        log_session_debug,
        issue_auth_token if TOKEN_AUTH_ENABLED else None,
        AUTH_TOKEN_STORAGE_KEY,
        AUTH_TOKEN_QUERY_PARAM,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    return register_route(
        load_users,
        save_users,
        next_user_id,
        hash_password,
        storage_write_lock,
        USERS_PATH,
        issue_auth_token if TOKEN_AUTH_ENABLED else None,
        AUTH_TOKEN_STORAGE_KEY,
        AUTH_TOKEN_QUERY_PARAM,
    )

@app.route("/logout")
def logout():
    return logout_route(AUTH_TOKEN_STORAGE_KEY)


@app.get("/post-login")
def post_login():
    if SESSION_DEBUG_ENABLED:
        log_session_debug("post_login_landing")
    return redirect(url_for("index"))


@app.context_processor
def inject_notifications_count():
    # Бейдж уведомлений в нижнем меню
    bookings, preparing_orders = get_request_notification_data()
    return {
        "notifications_count": len(bookings) + len(preparing_orders),
        "current_user_name": session.get("user_name"),
        "current_user_id": session.get("user_id"),
        "csrf_token": session.get("csrf_token", ""),
        "auth_mode": AUTH_MODE,
        "auth_token_enabled": TOKEN_AUTH_ENABLED,
        "auth_storage_key": AUTH_TOKEN_STORAGE_KEY,
        "auth_query_param": AUTH_TOKEN_QUERY_PARAM,
    }


@app.route("/orders")
def orders():
    return orders_route(load_orders)


@app.route("/orders/<int:order_id>")
def order_detail(order_id: int):
    return order_detail_route(order_id, load_orders)


@app.route("/reviews")
def reviews():
    return reviews_route()


@app.route("/menu/<int:item_id>")
def menu_item(item_id: int):
    return menu_item_route(item_id, load_menu_items)


@app.route("/menu")
def menu():
    return menu_route(load_menu_items)


@app.route("/checkout")
def checkout():
    return checkout_route(
        latest_user_booking_status,
        parse_datetime,
        BOOKING_DURATION_MINUTES,
        load_users,
        load_menu_items,
    )


@app.post("/payment")
def payment():
    return payment_route(
        load_users,
        latest_user_booking_status,
        resolve_order_items,
        parse_serving_option,
        issue_checkout_preview_token,
    )


@app.post("/payment/confirm")
def payment_confirm():
    return payment_confirm_route(
        latest_user_booking_status,
        load_users,
        storage_write_lock,
        ORDERS_PATH,
        load_orders,
        next_order_id,
        save_orders,
        USERS_PATH,
        save_users,
        verify_checkout_preview_token,
    )



@app.post("/book")
def book_table():
    return book_table_route(
        load_bookings,
        save_bookings,
        overlaps_booking,
        storage_write_lock,
        BOOKINGS_PATH,
    )


def load_promo_items():
    # Загружаем promo из static/promo_items/**/item.txt (включая вложенные папки)
    items = []
    if not PROMO_ITEMS_PATH.exists():
        return items

    meta_paths = sorted(PROMO_ITEMS_PATH.rglob(PROMO_META_NAME))
    for meta_path in meta_paths:
        item_dir = meta_path.parent
        relative_slug = item_dir.relative_to(PROMO_ITEMS_PATH).as_posix()
        photo_name = resolve_photo_name(item_dir, PROMO_PHOTO_NAMES)

        meta = parse_menu_meta(meta_path)
        promo_item = parse_promo_item(meta, relative_slug, photo_name)
        if promo_item is None:
            continue
        if not promo_item.get("active", True):
            continue
        items.append(promo_item)

    items.sort(key=lambda item: (item.get("priority", 100), item["id"]))
    return items


def is_placeholder_promo(meta: dict) -> bool:
    item_class = (meta.get("class", "") or "").strip().lower()
    if item_class == "reklama":
        text = (meta.get("text", "") or "").strip()
        link = (meta.get("link", "") or "").strip()
        return text == "Текст рекламного блока." and link == "https://example.com"
    if item_class == "akciya":
        name = (meta.get("name", "") or "").strip()
        lore = (meta.get("lore", "") or "").strip()
        return name == "Название акции" and lore == "Описание акции и условия."
    return False


def parse_menu_meta(meta_path: Path):
    # Формат item.txt: key=value, пустые строки и # комментарии игнорируются
    data = {}
    raw_text = read_text_with_fallback(meta_path, ("utf-8", "utf-8-sig", "cp1251"))
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip().lower().lstrip("\ufeff")
        data[normalized_key] = value.strip()
    return data


def read_text_with_fallback(path: Path, encodings):
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def resolve_photo_name(item_dir: Path, photo_names):
    for photo_name in photo_names:
        if (item_dir / photo_name).exists():
            return photo_name
    # Фолбэк: подхватываем любое изображение в папке, если нет стандартного photo.*
    for extension in ("*.webp", "*.png", "*.jpg", "*.jpeg"):
        candidates = sorted(item_dir.glob(extension))
        if candidates:
            return candidates[0].name
    return None


def normalize_portion_label(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    numeric_match = re.fullmatch(r"(\d{2,4})(?:[.,]\d+)?", value)
    if numeric_match:
        return f"{numeric_match.group(1)} г"

    unit_match = re.fullmatch(r"(\d{2,4})(?:[.,]\d+)?\s*(г|гр|g|мл|ml)", value, re.IGNORECASE)
    if unit_match:
        unit = unit_match.group(2).lower()
        normalized_unit = "мл" if unit in {"ml", "мл"} else "г"
        return f"{unit_match.group(1)} {normalized_unit}"

    return value


def resolve_menu_portion_label(meta: dict) -> str:
    for key in ("portion", "weight", "grams", "gram", "volume", "serving", "yield"):
        value = normalize_portion_label(meta.get(key, ""))
        if value:
            return value
    return ""


def extract_portion_amount(portion_label: str) -> float | None:
    match = re.search(r"(\d{2,4})(?:[.,]\d+)?", portion_label or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def build_portion_tone_rgb(portion_label: str) -> str:
    amount = extract_portion_amount(portion_label)
    if amount is None:
        return "194, 168, 144"

    # Smoothly shift from creamy coffee to terracotta orange as the portion grows.
    min_amount = 160.0
    max_amount = 420.0
    t = max(0.0, min(1.0, (amount - min_amount) / (max_amount - min_amount)))

    start = (194, 168, 144)
    end = (214, 112, 74)
    rgb = tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))
    return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"


def parse_menu_item(meta: dict, slug: str, photo_name: str):
    try:
        price = int(meta.get("price", ""))
    except ValueError:
        return None
    try:
        item_id = int(meta.get("id", ""))
        if item_id <= 0:
            item_id = None
    except ValueError:
        item_id = None
    try:
        popularity = int(meta.get("popularity", meta.get("orders_count", "0")))
    except ValueError:
        popularity = 0

    name = meta.get("name", "")
    lore = meta.get("lore", "")
    dish_type = meta.get("type", "")
    if not all([name, lore, dish_type]):
        return None

    featured_value = meta.get("featured", "false").lower()
    featured = featured_value in {"1", "true", "yes", "y", "on"}
    portion_label = resolve_menu_portion_label(meta)
    portion_tone_rgb = build_portion_tone_rgb(portion_label) if portion_label else ""
    item = MenuItem(
        id=item_id,
        name=name,
        lore=lore,
        type=dish_type,
        price=price,
        photo=f"menu_items/{slug}/{photo_name}",
        portion_label=portion_label,
        portion_tone_rgb=portion_tone_rgb,
        popularity=popularity,
        featured=featured,
    )
    return item.to_dict()


def parse_promo_item(meta: dict, slug: str, photo_name):
    try:
        item_id = int(meta.get("id", ""))
    except ValueError:
        return None

    item_class = (meta.get("class", "") or "").strip().lower()
    if item_class not in {"reklama", "akciya"}:
        return None
    if is_placeholder_promo(meta):
        return None

    try:
        priority = int(meta.get("priority", "100"))
    except ValueError:
        priority = 100

    active_value = (meta.get("active", "true") or "").lower()
    active = active_value in {"1", "true", "yes", "y", "on"}
    photo = f"promo_items/{slug}/{photo_name}" if photo_name else None

    if item_class == "reklama":
        text = (meta.get("text", "") or "").strip()
        link = (meta.get("link", "") or "").strip()
        if not text:
            return None
        item = PromoItem(
            id=item_id,
            class_name=item_class,
            priority=priority,
            active=active,
            photo=photo,
            text=text,
            link=link,
        )
        return item.to_dict()

    name = (meta.get("name", "") or "").strip()
    lore = (meta.get("lore", "") or "").strip()
    if not name or not lore:
        return None
    item = PromoItem(
        id=item_id,
        class_name=item_class,
        priority=priority,
        active=active,
        photo=photo,
        name=name,
        lore=lore,
    )
    return item.to_dict()


def promo_items_to_news_cards(items):
    # Приводим promo-элементы к формату карточек главной страницы
    cards = []
    for item in items:
        if item.get("class") == "reklama":
            cards.append(
                {
                    "title": "Реклама",
                    "text": item.get("text", ""),
                    "accent": "Реклама",
                    "photo": item.get("photo"),
                    "link": item.get("link"),
                }
            )
            continue
        cards.append(
            {
                "title": item.get("name", ""),
                "text": item.get("lore", ""),
                "accent": "Акция",
                "photo": item.get("photo"),
                "link": "",
            }
        )
    return cards[:3]


def load_bookings():
    return store_load_bookings(BOOKINGS_PATH, parse_datetime, BOOKING_DURATION_MINUTES)


def load_bookings_raw():
    return store_load_bookings_raw(BOOKINGS_PATH)


def save_bookings(bookings):
    store_save_bookings(BOOKINGS_PATH, bookings)


def load_orders():
    orders = store_load_orders(ORDERS_PATH)
    return prune_orders(orders)


def save_orders(orders):
    store_save_orders(ORDERS_PATH, orders)


def prune_orders(orders):
    global _LAST_ORDER_PRUNE_AT
    if ORDER_RETENTION_DAYS <= 0:
        return orders

    now_monotonic = time.monotonic()
    with _ORDER_PRUNE_LOCK:
        if now_monotonic - _LAST_ORDER_PRUNE_AT < ORDER_PRUNE_INTERVAL_SECONDS:
            return orders
        _LAST_ORDER_PRUNE_AT = now_monotonic

    now_dt = datetime.now()
    retention_delta = timedelta(days=ORDER_RETENTION_DAYS)
    cleaned = []
    changed = False

    for order in orders:
        if not isinstance(order, dict):
            changed = True
            continue

        created_at = parse_iso_datetime_value(order.get("created_at"))
        if created_at is None:
            cleaned.append(order)
            continue

        timeline = build_order_status_timeline_value(order, now_dt, ORDER_STATUS_STEPS, parse_iso_datetime_value)
        is_active = timeline is not None
        is_fresh = (now_dt - created_at) <= retention_delta

        if is_active or is_fresh:
            cleaned.append(order)
            continue
        changed = True

    if changed:
        try:
            store_save_orders(ORDERS_PATH, cleaned)
        except Exception:
            return orders
        return cleaned
    return orders


def load_users():
    return store_load_users(USERS_PATH)


def save_users(users):
    store_save_users(USERS_PATH, users)


def next_user_id(users):
    return store_next_user_id(users)


def next_order_id(orders):
    return store_next_order_id(orders)


def hash_password(password):
    # Простой хеш для демо (без соли)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def parse_datetime(date_str, time_str):
    return parse_datetime_value(date_str, time_str)


def overlaps_booking(booking, selected_dt):
    return overlaps_booking_window(booking, selected_dt, parse_datetime, BOOKING_DURATION_MINUTES)


def latest_user_booking(user_id):
    return latest_user_booking_entry(user_id, load_bookings)


def get_user_preparing_orders(user_id):
    return get_user_preparing_orders_value(user_id, load_orders, build_order_status_timeline)


def order_cooking_window(order):
    return order_cooking_window_value(
        order,
        parse_datetime,
        parse_iso_datetime,
        compute_serve_datetime,
        BOOKING_DURATION_MINUTES,
    )


def compute_serve_datetime(order, booking_dt):
    return compute_serve_datetime_value(order, booking_dt, parse_datetime)


def parse_iso_datetime(value):
    return parse_iso_datetime_value(value)


def build_order_status_timeline(order, now: datetime):
    return build_order_status_timeline_value(order, now, ORDER_STATUS_STEPS, parse_iso_datetime)


def latest_active_order_status(user_id):
    return latest_active_order_status_value(user_id, list_active_order_statuses)


def list_active_order_statuses(user_id):
    return list_active_order_statuses_value(user_id, load_orders, build_order_status_timeline)


def latest_user_booking_status(user_id):
    return latest_user_booking_status_value(
        user_id,
        load_bookings_raw,
        parse_datetime,
        BOOKING_DURATION_MINUTES,
    )


def resolve_order_items(raw_items_json):
    return resolve_order_items_value(raw_items_json, load_menu_items)


def parse_serving_option(serve_mode, serve_custom_time, booking):
    return parse_serving_option_value(
        serve_mode,
        serve_custom_time,
        booking,
        parse_datetime,
        BOOKING_DURATION_MINUTES,
    )


@app.post("/release")
def release_table():
    # Placeholder for future staff flow.
    return jsonify({"ok": False, "error": "Table release will be added later."}), 501


@app.post("/bookings/cancel")
def cancel_booking():
    return cancel_booking_with_orders_route(
        load_bookings,
        save_bookings,
        storage_write_lock,
        BOOKINGS_PATH,
        load_orders,
        save_orders,
        ORDERS_PATH,
    )


@app.post("/cards/add")
def add_card():
    return add_card_route(load_users, save_users, storage_write_lock, USERS_PATH)


@app.post("/cards/delete")
def delete_card():
    return delete_card_route(load_users, save_users, storage_write_lock, USERS_PATH)


start_db_keepalive()


if __name__ == "__main__":
    app.run(debug=True)
