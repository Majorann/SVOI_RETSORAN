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

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)
# Хранилища JSON
BOOKINGS_PATH = Path(__file__).with_name("bookings.json")
USERS_PATH = Path(__file__).with_name("users.json")
MENU_ITEMS_PATH = Path(__file__).with_name("static") / "menu_items"
PROMO_ITEMS_PATH = Path(__file__).with_name("static") / "promo_items"
# Длительность брони в минутах (для проверки пересечений)
BOOKING_DURATION_MINUTES = 60
# Секрет для сессий (в проде заменить)
app.secret_key = "replace-me-in-production"
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
    promo_items = load_promo_items()
    promo_news = promo_items_to_news_cards(promo_items)
    news_cards = promo_news or NEWS_CARDS
    all_menu_items = load_menu_items()
    popular_menu = [item for item in all_menu_items if item.get("featured")][:3]
    if not popular_menu:
        popular_menu = all_menu_items[:3]
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
    else:
        bookings = []
    return render_template("index.html", news=news_cards, menu=popular_menu, bookings=bookings)


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
    # Уведомления — это брони текущего пользователя
    user_id = session.get("user_id")
    bookings = load_bookings()
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
    else:
        bookings = []
    bookings_sorted = sorted(
        bookings,
        key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")),
        reverse=True,
    )
    return render_template("notifications.html", bookings=bookings_sorted)


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
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
    else:
        bookings = []
    return {"notifications_count": len(bookings), "current_user_name": session.get("user_name")}


@app.route("/orders")
def orders():
    return render_template("placeholder.html", title="История заказов")


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


def save_bookings(bookings):
    # Сохранение bookings.json
    BOOKINGS_PATH.write_text(json.dumps(bookings, ensure_ascii=False, indent=2), encoding="utf-8")


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

