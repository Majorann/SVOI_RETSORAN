"""
Restaurant demo app (Flask).
- Landing, hall reservation, menu, notifications, auth
- Bookings/users stored in JSON files
"""

from flask import Flask, render_template, url_for, request, jsonify, session, redirect
from datetime import datetime, date, timedelta
from pathlib import Path
from dataclasses import dataclass
import json
import hashlib
import os

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
# Карусель на главной
NEWS_CARDS = []

MENU_PHOTO_NAME = "photo.png"
MENU_META_NAME = "item.txt"
PROMO_PHOTO_NAME = "photo.png"
PROMO_META_NAME = "item.txt"


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
    else:
        bookings = []
    return render_template(
        "index.html",
        news=news_cards,
        menu=popular_menu,
        bookings=bookings,
        preparing_orders=preparing_orders,
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
    return render_template("placeholder.html", title="Мои баллы")


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
    # Регистрация нового пользователя в users.json
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        if not name or not phone or not password:
            return render_template("register.html", error="Заполните все поля.")
        users = load_users()
        if any(u.get("phone") == phone for u in users):
            return render_template("register.html", error="Этот номер уже зарегистрирован.")
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
        return redirect(url_for("login", error="Войдите, чтобы завершить оплату."))
    preview = session.get("checkout_preview")
    if not preview:
        return redirect(url_for("checkout", error="Сессия оплаты устарела. Повторите оформление."))

    orders = load_orders()
    order_id = next_order_id(orders)
    new_order = {
        "id": order_id,
        "user_id": user_id,
        "status": "preparing",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "items": preview.get("items", []),
        "items_total": preview.get("items_total", 0),
        "points_applied": preview.get("points_applied", 0),
        "payable_total": preview.get("payable_total", preview.get("items_total", 0)),
        "comment": preview.get("comment", ""),
        "serving": preview.get("serving", {}),
        "booking": preview.get("booking", {}),
        "payment_card": preview.get("payment_card", {}),
    }
    orders.append(new_order)
    save_orders(orders)

    points_applied = int(preview.get("points_applied", 0) or 0)
    if points_applied > 0:
        users = load_users()
        user = next((u for u in users if u.get("id") == user_id), None)
        if user is not None:
            current_balance = int(user.get("balance", 0) or 0)
            user["balance"] = max(0, current_balance - points_applied)
            save_users(users)

    session.pop("checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)


@app.post("/book")
def book_table():
    # Создать бронь (нужен вход)
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    table_id = data.get("table_id")
    date_str = data.get("date")
    time_str = data.get("time")
    name = (data.get("name") or "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Требуется вход в аккаунт."}), 401
    if not all([table_id, date_str, time_str, name]):
        return jsonify({"ok": False, "error": "Заполните все поля."}), 400

    try:
        booking_dt = datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError:
        return jsonify({"ok": False, "error": "Неверные дата/время."}), 400

    if booking_dt < datetime.now():
        return jsonify({"ok": False, "error": "Время не может быть в прошлом."}), 400

    bookings = load_bookings()
    if any(
        b.get("table_id") == table_id and overlaps_booking(b, booking_dt)
        for b in bookings
    ):
        return jsonify({"ok": False, "error": "Столик уже занят на это время."}), 409

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
        photo_path = item_dir / MENU_PHOTO_NAME
        if not meta_path.exists() or not photo_path.exists():
            continue

        meta = parse_menu_meta(meta_path)
        menu_item = parse_menu_item(meta, item_dir.name)
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
        photo_path = item_dir / PROMO_PHOTO_NAME
        if not meta_path.exists():
            continue

        meta = parse_menu_meta(meta_path)
        promo_item = parse_promo_item(meta, item_dir.name, photo_path.exists())
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
    for raw_line in meta_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip().lower().lstrip("\ufeff")
        data[normalized_key] = value.strip()
    return data


def parse_menu_item(meta: dict, slug: str):
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
        photo=f"menu_items/{slug}/{MENU_PHOTO_NAME}",
        popularity=popularity,
        featured=featured,
    )
    return item.__dict__


def parse_promo_item(meta: dict, slug: str, has_photo: bool):
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
    photo = f"promo_items/{slug}/{PROMO_PHOTO_NAME}" if has_photo else None

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
    preparing_now = []
    for order in orders:
        window = order_cooking_window(order)
        if window is None:
            continue
        cook_start, ready_time, booking_end = window
        # После конца брони уведомления по этому заказу не показываем.
        if now >= booking_end:
            continue
        # Показываем только "Заказ готовится" в 20-минутном окне.
        if cook_start <= now < ready_time:
            enriched = dict(order)
            enriched["cooking_expires_at"] = ready_time.isoformat(timespec="seconds")
            preparing_now.append(enriched)
    preparing_now.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return preparing_now


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
    # Заглушка (будущий сценарий для персонала)
    return jsonify({"ok": False, "error": "Освобождение столиков будет добавлено позже."}), 501

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
        return redirect(url_for("profile", error="Введите корректный номер карты."))

    if expiry and "/" not in expiry:
        return redirect(url_for("profile", error="Введите срок в формате ММ/ГГ."))

    brand = "МИР"

    users = load_users()
    user_record = next((u for u in users if u.get("id") == user_id), None)
    if not user_record:
        return redirect(url_for("profile", error="Пользователь не найден."))

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
        return redirect(url_for("profile", error="Не удалось определить карту для удаления."))

    users = load_users()
    user_record = next((u for u in users if u.get("id") == user_id), None)
    if not user_record:
        return redirect(url_for("profile", error="Пользователь не найден."))

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
        return redirect(url_for("profile", error="Карта не найдена."))

    removed_card = cards.pop(removed_index)
    if removed_card.get("active") and cards and not any(card.get("active") for card in cards):
        cards[-1]["active"] = True

    user_record["cards"] = cards
    save_users(users)
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True)


