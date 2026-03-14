"""
Restaurant demo app (Flask).
- Landing, hall reservation, menu, notifications, auth
- Bookings/users stored in JSON files
"""

from flask import Flask, render_template, url_for, request, jsonify, session, redirect
from datetime import datetime, date, timedelta
from pathlib import Path
from contextlib import contextmanager
import json
import hashlib
import os
import secrets
import threading
import time
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
default_samesite = "None" if is_hf_space else "Lax"
session_samesite = env_str("SESSION_COOKIE_SAMESITE", default_samesite)
app.config["SESSION_COOKIE_SAMESITE"] = session_samesite
app.config["SESSION_COOKIE_SECURE"] = env_bool("SESSION_COOKIE_SECURE", True)
app.config["SESSION_COOKIE_PARTITIONED"] = env_bool("SESSION_COOKIE_PARTITIONED", is_hf_space)
app.config["PREFERRED_URL_SCHEME"] = "https"
if env_bool("TRUST_PROXY_HEADERS", True):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.RLock()
_ORDER_PRUNE_LOCK = threading.RLock()
_LAST_ORDER_PRUNE_AT = 0.0
ORDER_RETENTION_DAYS = max(0, env_int("ORDER_RETENTION_DAYS", 7))
ORDER_PRUNE_INTERVAL_SECONDS = max(15, env_int("ORDER_PRUNE_INTERVAL_SECONDS", 60))
DB_KEEPALIVE_ENABLED = env_bool("DB_KEEPALIVE_ENABLED", True)
DB_KEEPALIVE_INTERVAL_SECONDS = max(60, env_int("DB_KEEPALIVE_INTERVAL_SECONDS", 600))
_DB_KEEPALIVE_STARTED = False
_DB_KEEPALIVE_LOCK = threading.Lock()
DEBUG_STORAGE_ENABLED = env_bool("DEBUG_STORAGE_ENABLED", False)
MOBILE_REQUEST_LOGGING_ENABLED = env_bool("MOBILE_REQUEST_LOGGING_ENABLED", True)
MOBILE_REQUEST_LOG_DIR = Path(__file__).resolve().parent / "mobile_request_logs"
MENU_CACHE_ENABLED = env_bool("MENU_CACHE_ENABLED", True)
MENU_CACHE_TTL_SECONDS = max(30, env_int("MENU_CACHE_TTL_SECONDS", 600))
MENU_CACHE_KEY = env_str("MENU_CACHE_KEY", "menu:items:v1")
_REDIS_CLIENT = None
_REDIS_CLIENT_LOCK = threading.Lock()
_MOBILE_LOG_LOCK = threading.Lock()

print(
    "[storage] backend={0} users={1} bookings={2} orders={3}".format(
        ACTIVE_STORAGE,
        USERS_PATH,
        BOOKINGS_PATH,
        ORDERS_PATH,
    )
)


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
    items = []
    if not MENU_ITEMS_PATH.exists():
        return items

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
        items.append(menu_item)

    items.sort(key=lambda item: item["id"])
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


def is_mobile_request():
    sec_ch_mobile = (request.headers.get("Sec-CH-UA-Mobile") or "").strip()
    if sec_ch_mobile == "?1":
        return True

    user_agent = (request.headers.get("User-Agent") or "").lower()
    mobile_markers = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
        "opera mini",
        "windows phone",
        "blackberry",
    )
    return any(marker in user_agent for marker in mobile_markers)


def write_mobile_request_log(response):
    if not MOBILE_REQUEST_LOGGING_ENABLED:
        return response
    if request.endpoint == "static":
        return response
    if not is_mobile_request():
        return response

    try:
        MOBILE_REQUEST_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = MOBILE_REQUEST_LOG_DIR / f"mobile-requests-{date.today().isoformat()}.log"
        log_entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "method": request.method,
            "path": request.path,
            "query_string": request.query_string.decode("utf-8", errors="replace"),
            "status_code": response.status_code,
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
            "user_agent": request.headers.get("User-Agent", ""),
            "origin": request.headers.get("Origin", ""),
            "referer": request.headers.get("Referer", ""),
            "host": request.host,
            "storage_backend": ACTIVE_STORAGE,
            "session_user_id": session.get("user_id"),
            "has_session_cookie": bool(request.cookies.get(app.config.get("SESSION_COOKIE_NAME", "session"))),
            "content_type": request.content_type or "",
            "form_keys": sorted(request.form.keys()),
            "json_keys": sorted((request.get_json(silent=True) or {}).keys()) if request.is_json else [],
        }
        with _MOBILE_LOG_LOCK:
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[mobile-log] write failed ({exc})")
    return response

@app.before_request
def keep_user_session():
    if request.endpoint == "static":
        return

    user_id = session.get("user_id")
    if not user_id:
        return

    session.permanent = True
    if session.get("user_name"):
        return

    user = next((u for u in load_users() if u.get("id") == user_id), None)
    if not user:
        # Do not hard-drop session on a single miss.
        # A concurrent JSON write may produce a transient empty read.
        return
    if not session.get("user_name"):
        session["user_name"] = user.get("name")


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
def log_mobile_requests(response):
    return write_mobile_request_log(response)

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
    )


@app.post("/delivery/payment")
def delivery_payment():
    return delivery_payment_route(resolve_order_items)


@app.get("/delivery/payment")
def delivery_payment_page():
    return delivery_payment_page_route()


@app.route("/notifications")
def notifications():
    return notifications_route(load_bookings, get_user_preparing_orders)


@app.route("/login", methods=["GET", "POST"])
def login():
    return login_route(load_users, hash_password)


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


@app.context_processor
def inject_notifications_count():
    # Бейдж уведомлений в нижнем меню
    user_id = session.get("user_id")
    bookings = load_bookings()
    preparing_orders = []
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
        preparing_orders = get_user_preparing_orders(user_id)
    else:
        bookings = []
    return {
        "notifications_count": len(bookings) + len(preparing_orders),
        "current_user_name": session.get("user_name"),
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
    return payment_route(load_users, latest_user_booking_status, resolve_order_items, parse_serving_option)


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


def parse_menu_item(meta: dict, slug: str, photo_name: str):
    try:
        item_id = int(meta.get("id", ""))
        price = int(meta.get("price", ""))
    except ValueError:
        return None
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
    item = MenuItem(
        id=item_id,
        name=name,
        lore=lore,
        type=dish_type,
        price=price,
        photo=f"menu_items/{slug}/{photo_name}",
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
