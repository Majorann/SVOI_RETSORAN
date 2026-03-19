"""
Restaurant demo app (Flask).
- Landing, hall reservation, menu, notifications, auth
- Bookings/users stored in JSON files
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from pathlib import Path
import os
import threading
import time
from itsdangerous import URLSafeTimedSerializer
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
    current_time_value,
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
from services.auth_session import AuthSessionService
from services.menu_content import MenuContentService
from services.passwords import (
    hash_password as hash_password_value,
    verify_password as verify_password_value,
    verify_and_upgrade_password as verify_and_upgrade_password_value,
)
from services.storage_facade import StorageFacade
from config import (
    BOOKINGS_PATH,
    BOOKING_DURATION_MINUTES,
    DATA_DIR,
    NEWS_CARDS,
    POPULAR_MENU_LIMIT,
    ORDERS_PATH,
    ORDER_STATUS_STEPS,
    TABLES,
    USERS_PATH,
    WALLS,
)


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
AUTH_SESSION_COOKIE_NAME = env_str("AUTH_SESSION_COOKIE_NAME", "auth_session")
AUTH_SESSION_COOKIE_MAX_AGE_SECONDS = max(
    300,
    env_int("AUTH_SESSION_COOKIE_MAX_AGE_SECONDS", 30 * 24 * 60 * 60),
)
PASSWORD_HASH_METHOD = env_str("PASSWORD_HASH_METHOD", "pbkdf2:sha256:600000")
_AUTH_SESSION_SERIALIZER = URLSafeTimedSerializer(app.secret_key, salt="auth-session-v1")
CHECKOUT_PREVIEW_MAX_AGE_SECONDS = max(300, env_int("CHECKOUT_PREVIEW_MAX_AGE_SECONDS", 30 * 60))
_CHECKOUT_PREVIEW_SERIALIZER = URLSafeTimedSerializer(app.secret_key, salt="checkout-preview-v1")
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

print(
    "[storage] backend={0} users={1} bookings={2} orders={3} cookie_secure={4} cookie_samesite={5} cookie_partitioned={6} login_debug={7} session_debug={8} auth_session_cookie={9}".format(
        ACTIVE_STORAGE,
        USERS_PATH,
        BOOKINGS_PATH,
        ORDERS_PATH,
        app.config["SESSION_COOKIE_SECURE"],
        app.config["SESSION_COOKIE_SAMESITE"],
        app.config["SESSION_COOKIE_PARTITIONED"],
        LOGIN_DEBUG_ENABLED,
        SESSION_DEBUG_ENABLED,
        AUTH_SESSION_COOKIE_NAME,
    )
)
if LOGIN_DEBUG_ENABLED:
    print(f"[auth-debug] failed login log path={LOGIN_DEBUG_LOG_PATH}")
if SESSION_DEBUG_ENABLED:
    print(f"[session-debug] session log path={SESSION_DEBUG_LOG_PATH}")

storage = StorageFacade(
    active_storage=ACTIVE_STORAGE,
    bookings_path=BOOKINGS_PATH,
    booking_duration_minutes=BOOKING_DURATION_MINUTES,
    orders_path=ORDERS_PATH,
    users_path=USERS_PATH,
    order_retention_days=ORDER_RETENTION_DAYS,
    order_prune_interval_seconds=ORDER_PRUNE_INTERVAL_SECONDS,
    parse_datetime_fn=parse_datetime_value,
    current_time_fn=current_time_value,
    parse_iso_datetime_fn=parse_iso_datetime_value,
    build_order_status_timeline_fn=lambda order, now: build_order_status_timeline_value(
        order,
        now,
        ORDER_STATUS_STEPS,
        parse_iso_datetime_value,
    ),
    store_load_bookings=store_load_bookings,
    store_load_bookings_raw=store_load_bookings_raw,
    store_load_orders=store_load_orders,
    store_load_users=store_load_users,
    store_next_order_id=store_next_order_id,
    store_next_user_id=store_next_user_id,
    store_save_bookings=store_save_bookings,
    store_save_orders=store_save_orders,
    store_save_users=store_save_users,
)
menu_content = MenuContentService(
    menu_cache_enabled=MENU_CACHE_ENABLED,
    menu_cache_key=MENU_CACHE_KEY,
    menu_cache_ttl_seconds=MENU_CACHE_TTL_SECONDS,
    redis_module=_redis_module,
    redis_url=_REDIS_URL,
)

load_bookings = storage.load_bookings
load_bookings_raw = storage.load_bookings_raw
save_bookings = storage.save_bookings
load_orders = storage.load_orders
save_orders = storage.save_orders
load_users = storage.load_users
save_users = storage.save_users
next_user_id = storage.next_user_id
next_order_id = storage.next_order_id
json_file_lock = storage.json_file_lock
storage_write_lock = storage.storage_write_lock
load_menu_items = menu_content.load_menu_items
load_promo_items = menu_content.load_promo_items
promo_items_to_news_cards = menu_content.promo_items_to_news_cards


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
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }
    )

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
    return profile_route(load_users, load_bookings, BOOKING_DURATION_MINUTES)


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
    return notifications_route(load_bookings, get_user_preparing_orders, load_promo_items, BOOKING_DURATION_MINUTES)


@app.route("/login", methods=["GET", "POST"])
def login():
    return login_route(
        load_users,
        save_users,
        verify_and_upgrade_password,
        storage_write_lock,
        USERS_PATH,
        debug_login_failure,
        log_session_debug,
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
    )

@app.route("/logout")
def logout():
    return logout_route()


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
        parse_datetime,
        storage_write_lock,
        BOOKINGS_PATH,
    )


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


def hash_password(password):
    return hash_password_value(password, PASSWORD_HASH_METHOD)


def verify_password(password, password_hash):
    return verify_password_value(password, password_hash)


def verify_and_upgrade_password(user, password):
    return verify_and_upgrade_password_value(user, password, PASSWORD_HASH_METHOD)


auth_session = AuthSessionService(
    app=app,
    auth_session_cookie_name=AUTH_SESSION_COOKIE_NAME,
    auth_session_cookie_max_age_seconds=AUTH_SESSION_COOKIE_MAX_AGE_SECONDS,
    auth_session_serializer=_AUTH_SESSION_SERIALIZER,
    checkout_preview_max_age_seconds=CHECKOUT_PREVIEW_MAX_AGE_SECONDS,
    checkout_preview_serializer=_CHECKOUT_PREVIEW_SERIALIZER,
    login_debug_enabled=LOGIN_DEBUG_ENABLED,
    login_debug_log_path=LOGIN_DEBUG_LOG_PATH,
    login_debug_lock=_LOGIN_DEBUG_LOCK,
    session_debug_enabled=SESSION_DEBUG_ENABLED,
    session_debug_log_path=SESSION_DEBUG_LOG_PATH,
    session_debug_lock=_SESSION_DEBUG_LOCK,
    load_users=load_users,
    load_bookings=load_bookings,
    get_user_preparing_orders=get_user_preparing_orders,
)
debug_login_failure = auth_session.debug_login_failure
log_session_debug = auth_session.log_session_debug
issue_auth_session_cookie = auth_session.issue_auth_session_cookie
verify_auth_session_cookie = auth_session.verify_auth_session_cookie
issue_checkout_preview_token = auth_session.issue_checkout_preview_token
verify_checkout_preview_token = auth_session.verify_checkout_preview_token
get_request_user = auth_session.get_request_user
get_request_notification_data = auth_session.get_request_notification_data
auth_session.register_hooks()


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
