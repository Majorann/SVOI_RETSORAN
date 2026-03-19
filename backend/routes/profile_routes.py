import re

from flask import g, redirect, render_template, request, session, url_for
from services.business_logic import current_local_datetime_value, current_timestamp_value

TRANSLIT_MAP = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
    "Е": "E", "Ё": "YO", "Ж": "ZH", "З": "Z", "И": "I",
    "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
    "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH",
    "Ш": "SH", "Щ": "SHCH", "Ъ": "", "Ы": "Y", "Ь": "",
    "Э": "E", "Ю": "YU", "Я": "YA",
    "а": "A", "б": "B", "в": "V", "г": "G", "д": "D",
    "е": "E", "ё": "YO", "ж": "ZH", "з": "Z", "и": "I",
    "й": "Y", "к": "K", "л": "L", "м": "M", "н": "N",
    "о": "O", "п": "P", "р": "R", "с": "S", "т": "T",
    "у": "U", "ф": "F", "х": "KH", "ц": "TS", "ч": "CH",
    "ш": "SH", "щ": "SHCH", "ъ": "", "ы": "Y", "ь": "",
    "э": "E", "ю": "YU", "я": "YA",
}


def normalize_card_holder(value: str, max_length: int = 26):
    transliterated = "".join(TRANSLIT_MAP.get(ch, ch) for ch in str(value or ""))
    cleaned = "".join(ch for ch in transliterated.upper() if ("A" <= ch <= "Z") or ch in {" ", "-"})
    compact = " ".join(cleaned.split()).strip()
    if not compact:
        return None
    return compact[:max_length]


def normalize_and_validate_expiry(value: str):
    raw = str(value or "").strip()
    if not raw:
        return None, None

    match = re.fullmatch(r"(\d{2})/(\d{2})", raw)
    if not match:
        return None, "Введите срок действия в формате ММ/ГГ."

    month = int(match.group(1))
    year = int(match.group(2))
    if month < 1 or month > 12:
        return None, "Месяц должен быть в диапазоне от 01 до 12."

    now = current_local_datetime_value()
    current_year = now.year % 100
    current_month = now.month
    if year < current_year or (year == current_year and month < current_month):
        return None, "Срок действия карты уже истёк."

    return f"{month:02d}/{year:02d}", None


def profile_route(load_users, load_bookings, booking_duration_minutes):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите в аккаунт, чтобы открыть профиль."))

    user_name = session.get("user_name")
    error = request.args.get("error")
    card_added = (request.args.get("card_added") or "") == "1"
    user_record = getattr(g, "current_user", None)
    if not user_record or user_record.get("id") != user_id:
        user_record = next((u for u in load_users() if u.get("id") == user_id), None)
    if not user_record:
        # Avoid hard logout on a transient storage miss (e.g. temporary DB hiccup).
        if not user_name:
            session.clear()
            return redirect(url_for("login", error="Сессия устарела. Войдите снова."))
        return render_template(
            "profile.html",
            user={
                "name": user_name,
                "avatar": None,
                "balance": 0,
                "cards": [],
            },
            cards=[],
            bookings=[],
            is_authenticated=True,
            payment_error="Профиль временно недоступен, обновите страницу.",
        )
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
        payment_success="Карта успешно добавлена" if card_added else "",
        booking_duration_minutes=booking_duration_minutes,
    )


def add_card_route(load_users, save_users, json_file_lock, users_path):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    number = (request.form.get("card_number") or "").strip()
    expiry_input = (request.form.get("expiry") or "").strip()
    holder_raw = (request.form.get("holder") or "").strip()
    holder = normalize_card_holder(holder_raw) if holder_raw else None

    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) < 12:
        return redirect(url_for("profile", error="Введите корректный номер карты."))

    expiry, expiry_error = normalize_and_validate_expiry(expiry_input)
    if expiry_error:
        return redirect(url_for("profile", error=expiry_error))
    if holder_raw and not holder:
        return redirect(url_for("profile", error="Используйте только английские буквы в имени держателя карты."))

    brand = "MIR"

    with json_file_lock(users_path):
        users = load_users()
        user_record = next((u for u in users if u.get("id") == user_id), None)
        if not user_record:
            session.clear()
            return redirect(url_for("login", error="Сессия устарела. Войдите снова."))

        cards = user_record.get("cards", [])
        for card in cards:
            card["active"] = False
        cards.append(
            {
                "brand": brand,
                "last4": digits[-4:],
                "active": True,
                "holder": holder,
                "expiry": expiry or None,
                "created_at": current_timestamp_value(),
            }
        )
        user_record["cards"] = cards
        save_users(users)
        g.current_user = user_record
        g.current_user_id = user_id
        g.current_user_loaded = True
    return redirect(url_for("profile", card_added="1"))


def delete_card_route(load_users, save_users, json_file_lock, users_path):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    created_at = (request.form.get("created_at") or "").strip()
    last4 = (request.form.get("last4") or "").strip()
    if not created_at and not last4:
        return redirect(url_for("profile", error="Failed to identify card to delete."))

    with json_file_lock(users_path):
        users = load_users()
        user_record = next((u for u in users if u.get("id") == user_id), None)
        if not user_record:
            session.clear()
            return redirect(url_for("login", error="Сессия устарела. Войдите снова."))

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
        g.current_user = user_record
        g.current_user_id = user_id
        g.current_user_loaded = True
    return redirect(url_for("profile"))
