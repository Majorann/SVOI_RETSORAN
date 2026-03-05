"""
Restaurant demo app (Flask).
- Landing, hall reservation, menu, notifications, auth
- Bookings/users stored in JSON files
"""

from flask import Flask, render_template, url_for, request, jsonify, session, redirect
from datetime import datetime, date, timedelta
from pathlib import Path
from dataclasses import dataclass
from contextlib import contextmanager
import json
import hashlib
import os
import secrets
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
# Хранилища JSON
BOOKINGS_PATH = Path(__file__).with_name("bookings.json")
USERS_PATH = Path(__file__).with_name("users.json")
ORDERS_PATH = Path(__file__).with_name("orders.json")
MENU_ITEMS_PATH = Path(__file__).with_name("static") / "menu_items"
PROMO_ITEMS_PATH = Path(__file__).with_name("static") / "promo_items"
# Длительность брони в минутах (для проверки пересечений)
BOOKING_DURATION_MINUTES = 60
# Секрет для сессий (в проде заменить)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-me-in-production")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = env_bool("SESSION_COOKIE_SECURE", True)
app.config["PREFERRED_URL_SCHEME"] = "https"
if env_bool("TRUST_PROXY_HEADERS", True):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
# Карусель на главной
NEWS_CARDS = []

MENU_PHOTO_NAMES = ("photo.png", "photo.webp")
MENU_META_NAME = "item.txt"
PROMO_PHOTO_NAMES = ("photo.png", "photo.webp")
PROMO_META_NAME = "item.txt"
_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.RLock()
ORDER_STATUS_STEPS = (
    {"key": "preparing", "duration_seconds": 15 * 60},
    {"key": "delivering", "duration_seconds": 60},
    {"key": "served", "duration_seconds": 60},
)


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


@dataclass
class MenuItem:
    id: int
    name: str
    lore: str
    type: str
    price: int
    photo: str
    popularity: int = 0
    featured: bool = False


@app.before_request
def keep_user_session():
    user_id = session.get("user_id")
    if not user_id:
        return
    session.permanent = True
    if session.get("user_name"):
        return
    user = next((u for u in load_users() if u.get("id") == user_id), None)
    if user:
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

# Схема зала: координаты и расстановка стульев (в процентах)
TABLES = [
    {
        "id": 1,
        "label": "Стол 1",
        "seats": 5,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 12,
        "shape": "rect",
        "chairs": {"top": "Sofa", "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 2,
        "label": "Стол 2",
        "seats": 4,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 32,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 3,
        "label": "Стол 3",
        "seats": 4,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 4,
        "label": "Стол 4",
        "seats": 2,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 32,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 1, "left": 0, "right": 0},
    },
    {
        "id": 5,
        "label": "Стол 5",
        "seats": 2,
        "window": False,
        "status": "free",
        "x": 50,
        "y": 32,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 1, "left": 0, "right": 0},
    },
    {
        "id": 6,
        "label": "Стол 6",
        "seats": 3,
        "window": False,
        "status": "free",
        "x": 90,
        "y": 28,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 0, "left": 1, "right": 1},
    },
    {
        "id": 7,
        "label": "Стол 7",
        "seats": 5,
        "window": False,
        "status": "free",
        "x": 60,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 1, "right": 0},
    },
    {
        "id": 8,
        "label": "Стол 8",
        "seats": 4,
        "window": False,
        "status": "free",
        "x": 90,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 9,
        "label": "Стол 9",
        "seats": 8,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": "Sofa", "left": 0, "right": "Sofa"},
    },
    {
        "id": 10,
        "label": "Стол 10",
        "seats": 15,
        "window": False,
        "status": "free",
        "x": 80,
        "y": 89,
        "shape": "long",
        "chairs": {"top": 5, "bottom": "Sofa", "left": 1, "right": "Sofa"},
    },
    {
        "id": 11,
        "label": "Стол 11",
        "seats": 5,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 89,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": "Sofa", "left": 0, "right": 0},
    },
    {
        "id": 12,
        "label": "Стол 12",
        "seats": 9,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 89,
        "shape": "rect",
        "chairs": {"top": "Sofa", "bottom": "Sofa", "left": 0, "right": "Sofa"},
    },
    {
        "id": 13,
        "label": "Стол 13",
        "seats": 6,
        "window": False,
        "status": "free",
        "x": 80,
        "y": 46,
        "shape": "long",
        "chairs": {"top": "Sofa", "bottom": "Sofa", "left": 1, "right": 1},
    }
]

# Стены задаются CSS-классами
WALLS = [
    {"class": "wall--wc-left"},
    {"class": "wall--wc-top"},
    {"class": "wall--left-upper"},
    {"class": "wall--left-lower"},
    {"class": "wall--mid-l"},
    {"class": "wall--mid-down"},
]


@app.route("/")
def index():
    user_id = session.get("user_id")
    bookings = load_bookings()
    preparing_orders = []
    order_status = None
    order_statuses = []
    points_balance = 0
    promo_items = load_promo_items()
    promo_news = promo_items_to_news_cards(promo_items)
    news_cards = promo_news or NEWS_CARDS
    all_menu_items = load_menu_items()
    popular_menu = [item for item in all_menu_items if item.get("featured")][:3]
    if not popular_menu:
        popular_menu = all_menu_items[:3]
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
        preparing_orders = get_user_preparing_orders(user_id)
        order_statuses = list_active_order_statuses(user_id)
        order_status = order_statuses[0] if order_statuses else None
        user = next((u for u in load_users() if u.get("id") == user_id), None)
        points_balance = int((user or {}).get("balance", 0) or 0)
    else:
        bookings = []
    points_balance_formatted = f"{points_balance:,}".replace(",", " ")
    return render_template(
        "index.html",
        news=news_cards,
        menu=popular_menu,
        bookings=bookings,
        preparing_orders=preparing_orders,
        order_status=order_status,
        order_statuses=order_statuses,
        points_balance=points_balance,
        points_balance_formatted=points_balance_formatted,
    )


@app.route("/reserve")
def reserve():
    # Определяем занятость столов на выбранные дату/время
    selected_date = request.args.get("date")
    if selected_date is None:
        selected_date = date.today().isoformat()
    selected_time = request.args.get("time")
    if selected_time is None:
        selected_time = datetime.now().strftime("%H:%M")

    bookings = load_bookings()
    selected_dt = parse_datetime(selected_date, selected_time)
    reserved_ids = {
        item["table_id"]
        for item in bookings
        if selected_dt and overlaps_booking(item, selected_dt)
    }

    tables = []
    for table in TABLES:
        updated = dict(table)
        if updated["id"] in reserved_ids:
            updated["status"] = "reserved"
        tables.append(updated)

    return render_template("reserve.html", tables=tables, walls=WALLS)


@app.get("/availability")
def availability():
    # API: список занятых столов на дату/время (окно 1 час)
    selected_date = request.args.get("date")
    selected_time = request.args.get("time")
    if not selected_date or not selected_time:
        return jsonify({"ok": False, "error": "date/time required"}), 400
    bookings = load_bookings()
    selected_dt = parse_datetime(selected_date, selected_time)
    if selected_dt is None:
        return jsonify({"ok": False, "error": "Invalid date/time"}), 400
    reserved_ids = [
        item["table_id"]
        for item in bookings
        if overlaps_booking(item, selected_dt)
    ]
    return jsonify({"ok": True, "reserved": reserved_ids})


@app.route("/points")
def points():
    return redirect(url_for("index"))


@app.route("/profile")
def profile():
    # Профиль показывает имя, баланс, карты и свои брони
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите в аккаунт, чтобы открыть профиль."))

    user_name = session.get("user_name")
    error = request.args.get("error")
    user_record = None
    user_record = next((u for u in load_users() if u.get("id") == user_id), None)
    user = {
        "name": user_name or (user_record or {}).get("name") or "Имя пользователя",
        "avatar": None,
        "balance": (user_record or {}).get("balance", 0),
        "cards": (user_record or {}).get("cards", []),
    }
    bookings = load_bookings()
    bookings = [b for b in bookings if b.get("user_id") == user_id]
    return render_template(
        "profile.html",
        user=user,
        cards=user["cards"],
        bookings=bookings,
        is_authenticated=bool(user_id),
        payment_error=error,
    )


@app.route("/delivery")
def delivery():
    return render_template("placeholder.html", title="Доставка")


@app.route("/notifications")
def notifications():
    # Уведомления: брони + статусы заказов
    user_id = session.get("user_id")
    bookings = load_bookings()
    preparing_orders = []
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
        preparing_orders = get_user_preparing_orders(user_id)
    else:
        bookings = []
    bookings_sorted = sorted(
        bookings,
        key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")),
        reverse=True,
    )
    return render_template(
        "notifications.html",
        bookings=bookings_sorted,
        preparing_orders=preparing_orders,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    # Вход через users.json
    initial_error = request.args.get("error")
    if request.method == "POST":
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        users = load_users()
        user = next((u for u in users if u.get("phone") == phone), None)
        if not user or user.get("password_hash") != hash_password(password):
            return render_template("login.html", error="Неверный телефон или пароль.")
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True
        return redirect(url_for("index"))
    return render_template("login.html", error=initial_error)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Register new user in users.json
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        if not name or not phone or not password:
            return render_template("register.html", error="Fill in all fields.")
        with json_file_lock(USERS_PATH):
            users = load_users()
            if any(u.get("phone") == phone for u in users):
                return render_template("register.html", error="This phone is already registered.")
            new_user = {
                "id": next_user_id(users),
                "name": name,
                "phone": phone,
                "password_hash": hash_password(password),
                "balance": 0,
                "cards": [],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            users.append(new_user)
            save_users(users)
        session["user_id"] = new_user["id"]
        session["user_name"] = new_user["name"]
        session.permanent = True
        return redirect(url_for("index"))
    return render_template("register.html", error=None)

@app.route("/logout")
def logout():
    # Очищаем сессию и уходим на логин
    session.clear()
    return redirect(url_for("login"))


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
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть историю заказов."))
    user_orders = [o for o in load_orders() if o.get("user_id") == user_id]
    user_orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return render_template("orders.html", orders=user_orders)


@app.route("/orders/<int:order_id>")
def order_detail(order_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть детали заказа."))
    order = next((o for o in load_orders() if o.get("id") == order_id and o.get("user_id") == user_id), None)
    if order is None:
        return render_template("placeholder.html", title="Заказ не найден"), 404
    return render_template("order-detail.html", order=order)


@app.route("/reviews")
def reviews():
    return render_template("placeholder.html", title="Мои отзывы")


@app.route("/menu/<int:item_id>")
def menu_item(item_id: int):
    item = next((dish for dish in load_menu_items() if dish["id"] == item_id), None)
    if item is None:
        return render_template("placeholder.html", title="Блюдо не найдено"), 404
    return render_template("menu-item.html", item=item)


@app.route("/menu")
def menu():
    return render_template("menu.html", items=load_menu_items())


@app.route("/checkout")
def checkout():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы оформить заказ."))
    booking_state = latest_user_booking_status(user_id)
    booking = booking_state.get("booking")
    checkout_state = booking_state.get("state", "no_booking")
    custom_time_max = None
    if booking and checkout_state == "active":
        booking_dt = parse_datetime(booking.get("date"), booking.get("time"))
        if booking_dt:
            custom_time_max = (booking_dt + timedelta(minutes=BOOKING_DURATION_MINUTES - 1)).strftime("%H:%M")
    users = load_users()
    user = next((u for u in users if u.get("id") == user_id), None)
    cards = list((user or {}).get("cards", []))
    active_card = next((card for card in cards if card.get("active")), None)
    checkout_error = request.args.get("error")
    menu_catalog = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "price": item.get("price"),
            "photo": item.get("photo"),
        }
        for item in load_menu_items()
    ]
    user_balance = int((user or {}).get("balance", 0) or 0)
    return render_template(
        "checkout.html",
        booking=booking,
        checkout_state=checkout_state,
        custom_time_max=custom_time_max,
        active_card=active_card,
        user_balance=user_balance,
        checkout_error=checkout_error,
        menu_catalog=menu_catalog,
    )


@app.post("/payment")
def payment():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы продолжить оплату."))

    users = load_users()
    user = next((u for u in users if u.get("id") == user_id), None)
    cards = list((user or {}).get("cards", []))
    active_card = next((card for card in cards if card.get("active")), None)
    user_balance = int((user or {}).get("balance", 0) or 0)

    booking_status = latest_user_booking_status(user_id)
    booking = booking_status.get("booking")
    booking_state = booking_status.get("state")

    items = resolve_order_items(request.form.get("items_json"))

    comment = (request.form.get("comment") or "").strip()[:300]
    serve_mode = (request.form.get("serve_mode") or "").strip()
    serve_custom_time = (request.form.get("serve_custom_time") or "").strip()
    serving = parse_serving_option(serve_mode, serve_custom_time, booking or {})
    if serving is None:
        serving = {"mode": "booking_start", "label": "К началу брони"}

    items_total = sum(item["price"] * item["qty"] for item in items)
    use_points = (request.form.get("use_points") or "") == "1"
    points_applied = min(user_balance, items_total) if use_points else 0
    payable_total = items_total - points_applied
    payment_error_code = None
    payment_error_text = None
    if booking_state == "no_booking":
        payment_error_code = "no_booking"
        payment_error_text = "Нет активной брони. Сначала забронируйте столик."
    elif booking_state == "expired_booking":
        payment_error_code = "expired_booking"
        payment_error_text = "Ваша бронь устарела. Забронируйте столик заново."
    elif not items:
        payment_error_code = "empty_cart"
        payment_error_text = "Корзина пуста. Добавьте блюда в меню."
    elif not active_card:
        payment_error_code = "no_card"
        payment_error_text = "Карта не привязана. Перейдите в профиль и добавьте карту."

    can_pay = payment_error_code is None
    preview = {
        "items": items,
        "items_total": items_total,
        "items_count": sum(item["qty"] for item in items),
        "points_applied": points_applied,
        "payable_total": payable_total,
        "comment": comment,
        "serving": serving,
        "booking": {
            "table_id": (booking or {}).get("table_id"),
            "date": (booking or {}).get("date"),
            "time": (booking or {}).get("time"),
            "status": "Активна" if booking_state == "active" else "Неактивна",
        },
        "payment_card": {
            "brand": (active_card or {}).get("brand", "Карта"),
            "last4": (active_card or {}).get("last4", "0000"),
            "expiry": (active_card or {}).get("expiry"),
        },
    }
    session["checkout_preview"] = preview if can_pay else None
    return render_template(
        "payment.html",
        preview=preview,
        can_pay=can_pay,
        payment_error_code=payment_error_code,
        payment_error_text=payment_error_text,
    )


@app.post("/payment/confirm")
def payment_confirm():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Log in to complete payment."))

    preview = session.get("checkout_preview")
    if not preview:
        return redirect(url_for("checkout", error="Payment session expired. Repeat checkout."))

    booking_status = latest_user_booking_status(user_id)
    booking = booking_status.get("booking")
    if booking_status.get("state") != "active":
        session.pop("checkout_preview", None)
        return redirect(url_for("checkout", error="Booking is no longer active."))

    users = load_users()
    user = next((u for u in users if u.get("id") == user_id), None)
    if user is None:
        session.clear()
        return redirect(url_for("login", error="User not found. Please log in again."))

    active_card = next((card for card in user.get("cards", []) if card.get("active")), None)
    if active_card is None:
        session.pop("checkout_preview", None)
        return redirect(url_for("checkout", error="No active payment card."))

    preview_items = preview.get("items")
    if not isinstance(preview_items, list):
        session.pop("checkout_preview", None)
        return redirect(url_for("checkout", error="Invalid order data."))

    items = []
    for item in preview_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id"))
            qty = int(item.get("qty"))
            price = int(item.get("price"))
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price < 0:
            continue
        items.append(
            {
                "id": item_id,
                "name": item.get("name", ""),
                "price": price,
                "qty": qty,
                "photo": item.get("photo"),
            }
        )

    if not items:
        session.pop("checkout_preview", None)
        return redirect(url_for("checkout", error="Cart is empty."))

    items_total = sum(item["price"] * item["qty"] for item in items)
    current_balance = int(user.get("balance", 0) or 0)
    requested_points = int(preview.get("points_applied", 0) or 0)
    points_applied = max(0, min(requested_points, current_balance, items_total))
    payable_total = items_total - points_applied
    bonus_earned = int(payable_total * 0.05)

    with json_file_lock(ORDERS_PATH):
        orders = load_orders()
        order_id = next_order_id(orders)
        new_order = {
            "id": order_id,
            "user_id": user_id,
            "status": "preparing",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "items": items,
            "items_total": items_total,
            "points_applied": points_applied,
            "payable_total": payable_total,
            "bonus_earned": bonus_earned,
            "comment": preview.get("comment", ""),
            "serving": preview.get("serving", {}),
            "booking": {
                "table_id": booking.get("table_id"),
                "date": booking.get("date"),
                "time": booking.get("time"),
                "status": "Active",
            },
            "payment_card": {
                "brand": active_card.get("brand", "Card"),
                "last4": active_card.get("last4", "0000"),
                "expiry": active_card.get("expiry"),
            },
        }
        orders.append(new_order)
        save_orders(orders)

    with json_file_lock(USERS_PATH):
        users = load_users()
        user = next((u for u in users if u.get("id") == user_id), None)
        if user is not None:
            current_balance = int(user.get("balance", 0) or 0)
            user["balance"] = max(0, current_balance - points_applied) + bonus_earned
            save_users(users)

    session.pop("checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)



@app.post("/book")
def book_table():
    # Create a booking (requires login)
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    table_id = data.get("table_id")
    date_str = data.get("date")
    time_str = data.get("time")
    name = (data.get("name") or "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Login is required."}), 401
    if not all([table_id, date_str, time_str, name]):
        return jsonify({"ok": False, "error": "Fill in all fields."}), 400

    try:
        booking_dt = datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date/time."}), 400

    if booking_dt < datetime.now():
        return jsonify({"ok": False, "error": "Time cannot be in the past."}), 400

    with json_file_lock(BOOKINGS_PATH):
        bookings = load_bookings()
        if any(
            b.get("table_id") == table_id and overlaps_booking(b, booking_dt)
            for b in bookings
        ):
            return jsonify({"ok": False, "error": "Table is already reserved for this time."}), 409

        bookings.append(
            {
                "table_id": table_id,
                "date": date_str,
                "time": time_str,
                "name": name,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_bookings(bookings)
    return jsonify({"ok": True})


def load_menu_items():
    # Загружаем блюда из static/menu_items/<slug>/item.txt + photo.png
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


def load_promo_items():
    # Загружаем promo из static/promo_items/<slug>/item.txt (+ optional photo.png)
    items = []
    if not PROMO_ITEMS_PATH.exists():
        return items

    for item_dir in sorted(PROMO_ITEMS_PATH.iterdir()):
        if not item_dir.is_dir():
            continue
        meta_path = item_dir / PROMO_META_NAME
        photo_name = resolve_photo_name(item_dir, PROMO_PHOTO_NAMES)
        if not meta_path.exists():
            continue

        meta = parse_menu_meta(meta_path)
        promo_item = parse_promo_item(meta, item_dir.name, photo_name)
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
    return item.__dict__


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
        return {
            "id": item_id,
            "class": item_class,
            "text": text,
            "link": link,
            "priority": priority,
            "active": active,
            "photo": photo,
        }

    name = (meta.get("name", "") or "").strip()
    lore = (meta.get("lore", "") or "").strip()
    if not name or not lore:
        return None
    return {
        "id": item_id,
        "class": item_class,
        "name": name,
        "lore": lore,
        "priority": priority,
        "active": active,
        "photo": photo,
    }


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
    # Безопасное чтение bookings.json
    if not BOOKINGS_PATH.exists():
        return []
    try:
        bookings = json.loads(BOOKINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    now = datetime.now()
    active = []
    for booking in bookings:
        booking_dt = parse_datetime(booking.get("date"), booking.get("time"))
        if booking_dt is None:
            continue
        if booking_dt + timedelta(minutes=BOOKING_DURATION_MINUTES) <= now:
            continue
        active.append(booking)
    if len(active) != len(bookings):
        save_bookings(active)
    return active


def load_bookings_raw():
    if not BOOKINGS_PATH.exists():
        return []
    try:
        return json.loads(BOOKINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_bookings(bookings):
    # Сохранение bookings.json
    BOOKINGS_PATH.write_text(json.dumps(bookings, ensure_ascii=False, indent=2), encoding="utf-8")


def load_orders():
    if not ORDERS_PATH.exists():
        return []
    try:
        return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_orders(orders):
    ORDERS_PATH.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")


def load_users():
    # Безопасное чтение users.json
    if not USERS_PATH.exists():
        return []
    try:
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_users(users):
    # Сохранение users.json
    USERS_PATH.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def next_user_id(users):
    # Авто‑инкремент id в users.json
    if not users:
        return 1
    return max(u.get("id", 0) for u in users) + 1


def next_order_id(orders):
    if not orders:
        return 1
    return max(o.get("id", 0) for o in orders) + 1


def hash_password(password):
    # Простой хеш для демо (без соли)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def parse_datetime(date_str, time_str):
    # Помощник для парсинга ISO даты/времени
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str}")
    except (TypeError, ValueError):
        return None


def overlaps_booking(booking, selected_dt):
    # Проверяем, попадает ли время в окно брони
    booking_dt = parse_datetime(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return False
    end_dt = booking_dt + timedelta(minutes=BOOKING_DURATION_MINUTES)
    return booking_dt <= selected_dt < end_dt


def latest_user_booking(user_id):
    bookings = [b for b in load_bookings() if b.get("user_id") == user_id]
    if not bookings:
        return None
    bookings.sort(key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")), reverse=True)
    return bookings[0]


def get_user_preparing_orders(user_id):
    orders = [o for o in load_orders() if o.get("user_id") == user_id]
    now = datetime.now()
    active_orders = []
    status_titles = {
        "preparing": "Заказ готовится",
        "delivering": "Заказ несут",
        "served": "Заказ выдан",
    }
    status_texts = {
        "preparing": "Осталось",
        "delivering": "Сейчас принесём",
        "served": "Можно забирать",
    }

    for order in orders:
        timeline = build_order_status_timeline(order, now)
        if timeline is None:
            continue

        phase = timeline.get("phase")
        remaining_seconds = int(timeline.get("phase_remaining_seconds", 0) or 0)
        remaining_seconds = max(0, remaining_seconds)
        minutes, seconds = divmod(remaining_seconds, 60)

        enriched = dict(order)
        enriched["status_phase"] = phase
        enriched["status_title"] = status_titles.get(phase, "Статус заказа")
        enriched["status_text"] = status_texts.get(phase, "Осталось")
        enriched["status_remaining_seconds"] = remaining_seconds
        enriched["status_remaining_mmss"] = f"{minutes:02d}:{seconds:02d}"
        active_orders.append(enriched)

    active_orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return active_orders


def order_cooking_window(order):
    booking = order.get("booking") or {}
    booking_dt = parse_datetime(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return None
    booking_end = booking_dt + timedelta(minutes=BOOKING_DURATION_MINUTES)

    order_time = parse_iso_datetime(order.get("created_at"))
    if order_time is None:
        order_time = booking_dt

    serve_dt = compute_serve_datetime(order, booking_dt)
    if serve_dt is None:
        serve_dt = booking_dt

    # clamp serve_time в рамки окна брони
    if serve_dt < booking_dt:
        serve_dt = booking_dt
    if serve_dt > booking_end:
        serve_dt = booking_end

    cook_start = max(order_time, serve_dt - timedelta(minutes=20))
    ready_time = cook_start + timedelta(minutes=20)
    return cook_start, ready_time, booking_end


def compute_serve_datetime(order, booking_dt):
    serving = order.get("serving") or {}
    mode = serving.get("mode")
    if mode == "booking_start":
        return booking_dt
    if mode == "plus_15":
        return booking_dt + timedelta(minutes=15)
    if mode == "plus_30":
        return booking_dt + timedelta(minutes=30)
    if mode == "plus_45":
        return booking_dt + timedelta(minutes=45)
    if mode == "plus_60":
        return booking_dt + timedelta(minutes=60)
    if mode == "custom":
        custom_time = serving.get("time")
        if not custom_time:
            return None
        return parse_datetime(booking_dt.date().isoformat(), custom_time)
    return None


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def build_order_status_timeline(order, now: datetime):
    created_at = parse_iso_datetime(order.get("created_at"))
    if created_at is None:
        return None

    total_duration = sum(step["duration_seconds"] for step in ORDER_STATUS_STEPS)
    elapsed = int((now - created_at).total_seconds())
    if elapsed < 0:
        elapsed = 0
    if elapsed >= total_duration:
        return None

    phase_key = ORDER_STATUS_STEPS[-1]["key"]
    phase_duration = ORDER_STATUS_STEPS[-1]["duration_seconds"]
    phase_start_offset = 0
    elapsed_acc = 0
    for step in ORDER_STATUS_STEPS:
        next_acc = elapsed_acc + step["duration_seconds"]
        if elapsed < next_acc:
            phase_key = step["key"]
            phase_duration = step["duration_seconds"]
            phase_start_offset = elapsed_acc
            break
        elapsed_acc = next_acc

    phase_elapsed = elapsed - phase_start_offset
    phase_remaining = max(0, phase_duration - phase_elapsed)
    cycle_end = created_at + timedelta(seconds=total_duration)
    phase_start = created_at + timedelta(seconds=phase_start_offset)
    phase_end = phase_start + timedelta(seconds=phase_duration)

    return {
        "order_id": order.get("id"),
        "phase": phase_key,
        "phase_elapsed_seconds": phase_elapsed,
        "phase_remaining_seconds": phase_remaining,
        "phase_duration_seconds": phase_duration,
        "phase_progress_ratio": (phase_elapsed / phase_duration) if phase_duration else 1.0,
        "cycle_started_at": created_at.isoformat(timespec="seconds"),
        "phase_started_at": phase_start.isoformat(timespec="seconds"),
        "phase_ends_at": phase_end.isoformat(timespec="seconds"),
        "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
    }


def latest_active_order_status(user_id):
    active = list_active_order_statuses(user_id)
    return active[0] if active else None


def list_active_order_statuses(user_id):
    now = datetime.now()
    orders = [o for o in load_orders() if o.get("user_id") == user_id]
    active = []
    phase_priority = {"served": 0, "delivering": 1, "preparing": 2}

    for order in orders:
        timeline = build_order_status_timeline(order, now)
        if timeline is None:
            continue
        timeline["created_at"] = order.get("created_at", "")
        active.append(timeline)

    active.sort(
        key=lambda item: (
            phase_priority.get(item.get("phase"), 99),
            int(item.get("phase_remaining_seconds", 0) or 0),
            item.get("created_at", ""),
            int(item.get("order_id", 0) or 0),
        )
    )
    return active


def latest_user_booking_status(user_id):
    bookings = [b for b in load_bookings_raw() if b.get("user_id") == user_id]
    if not bookings:
        return {"state": "no_booking", "booking": None}
    bookings.sort(
        key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")),
        reverse=True,
    )
    booking = bookings[0]
    booking_dt = parse_datetime(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return {"state": "no_booking", "booking": None}
    if booking_dt + timedelta(minutes=BOOKING_DURATION_MINUTES) <= datetime.now():
        return {"state": "expired_booking", "booking": booking}
    return {"state": "active", "booking": booking}


def resolve_order_items(raw_items_json):
    try:
        raw_items = json.loads(raw_items_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_items, list):
        return []

    normalized = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id"))
            qty = int(item.get("qty"))
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        normalized[item_id] = normalized.get(item_id, 0) + qty

    if not normalized:
        return []

    menu_index = {m["id"]: m for m in load_menu_items()}
    items = []
    for item_id, qty in normalized.items():
        menu_item = menu_index.get(item_id)
        if not menu_item:
            continue
        items.append(
            {
                "id": menu_item["id"],
                "name": menu_item["name"],
                "price": menu_item["price"],
                "qty": qty,
                "photo": menu_item.get("photo"),
            }
        )
    return items


def parse_serving_option(serve_mode, serve_custom_time, booking):
    labels = {
        "booking_start": "К началу брони",
        "plus_15": "Через 15 минут",
        "plus_30": "Через 30 минут",
        "plus_45": "Через 45 минут",
        "plus_60": "Через 60 минут",
    }
    if serve_mode in labels:
        return {"mode": serve_mode, "label": labels[serve_mode]}
    if serve_mode == "custom":
        if not serve_custom_time:
            return None
        booking_start = parse_datetime(booking.get("date"), booking.get("time"))
        custom_time = parse_datetime(booking.get("date"), serve_custom_time)
        if booking_start is None or custom_time is None:
            return None
        booking_end = booking_start + timedelta(minutes=BOOKING_DURATION_MINUTES)
        if not (booking_start <= custom_time < booking_end):
            return None
        return {"mode": "custom", "label": f"В своё время ({serve_custom_time})", "time": serve_custom_time}
    return None


@app.post("/release")
def release_table():
    # Placeholder for future staff flow.
    return jsonify({"ok": False, "error": "Table release will be added later."}), 501


@app.post("/bookings/cancel")
def cancel_booking():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    table_id = request.form.get("table_id", type=int)
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    if not table_id or not date_str or not time_str:
        return redirect(url_for("index"))

    with json_file_lock(BOOKINGS_PATH):
        bookings = load_bookings()
        remaining = []
        removed = False
        for booking in bookings:
            if (
                not removed
                and booking.get("user_id") == user_id
                and booking.get("table_id") == table_id
                and booking.get("date") == date_str
                and booking.get("time") == time_str
            ):
                removed = True
                continue
            remaining.append(booking)
        if removed:
            save_bookings(remaining)
    return redirect(url_for("index"))


@app.post("/cards/add")
def add_card():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    number = (request.form.get("card_number") or "").strip()
    expiry = (request.form.get("expiry") or "").strip()
    holder = (request.form.get("holder") or "").strip()

    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) < 12:
        return redirect(url_for("profile", error="Enter a valid card number."))

    if expiry and "/" not in expiry:
        return redirect(url_for("profile", error="Enter expiry in MM/YY format."))

    brand = "MIR"

    with json_file_lock(USERS_PATH):
        users = load_users()
        user_record = next((u for u in users if u.get("id") == user_id), None)
        if not user_record:
            return redirect(url_for("profile", error="User not found."))

        cards = user_record.get("cards", [])
        for card in cards:
            card["active"] = False
        cards.append(
            {
                "brand": brand,
                "last4": digits[-4:],
                "active": True,
                "holder": holder or None,
                "expiry": expiry or None,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        user_record["cards"] = cards
        save_users(users)
    return redirect(url_for("profile"))


@app.post("/cards/delete")
def delete_card():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    created_at = (request.form.get("created_at") or "").strip()
    last4 = (request.form.get("last4") or "").strip()
    if not created_at and not last4:
        return redirect(url_for("profile", error="Failed to identify card to delete."))

    with json_file_lock(USERS_PATH):
        users = load_users()
        user_record = next((u for u in users if u.get("id") == user_id), None)
        if not user_record:
            return redirect(url_for("profile", error="User not found."))

        cards = list(user_record.get("cards", []))
        removed_index = None
        for idx, card in enumerate(cards):
            if created_at and card.get("created_at") == created_at:
                removed_index = idx
                break
        if removed_index is None and last4:
            for idx, card in enumerate(cards):
                if card.get("last4") == last4:
                    removed_index = idx
                    break

        if removed_index is None:
            return redirect(url_for("profile", error="Card not found."))

        removed_card = cards.pop(removed_index)
        if removed_card.get("active") and cards and not any(card.get("active") for card in cards):
            cards[-1]["active"] = True

        user_record["cards"] = cards
        save_users(users)
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True)

