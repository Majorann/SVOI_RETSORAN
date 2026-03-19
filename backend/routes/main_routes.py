from flask import g, redirect, render_template, session, url_for
import secrets
from services.order_totals import summarize_saved_order_totals


def _format_date_ddmmyy(value):
    if not value:
        return "—"
    parts = str(value).split("-")
    if len(parts) != 3:
        return str(value)
    year, month, day = parts
    if len(year) != 4:
        return str(value)
    return f"{day.zfill(2)}.{month.zfill(2)}.{year[-2:]}"

def _format_time_hhmm(value):
    if not value:
        return "—"
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[1]
    if len(text) >= 5 and text[2] == ":":
        return text[:5]
    return "—"


_POPULAR_ROTATOR = secrets.SystemRandom()


def _pick_popular_items(items, limit):
    pool = list(items or [])
    if not pool:
        return []
    safe_limit = max(1, int(limit or 1))
    if len(pool) <= safe_limit:
        return pool[:safe_limit]
    if len(pool) <= 10:
        return pool[:safe_limit]
    return _POPULAR_ROTATOR.sample(pool, safe_limit)


def _pick_random_items(items, limit):
    pool = list(items or [])
    if not pool:
        return []
    safe_limit = max(1, int(limit or 1))
    if len(pool) <= safe_limit:
        return pool[:safe_limit]
    return _POPULAR_ROTATOR.sample(pool, safe_limit)


def index_route(
    load_bookings,
    load_promo_items,
    promo_items_to_news_cards,
    news_cards_fallback,
    load_menu_items,
    get_user_preparing_orders,
    list_active_order_statuses,
    load_users,
    popular_menu_limit,
):
    user_id = session.get("user_id")
    bookings = load_bookings()
    preparing_orders = []
    order_status = None
    order_statuses = []
    points_balance = 0
    promo_items = load_promo_items()
    promo_news = promo_items_to_news_cards(promo_items)
    news_cards = promo_news or news_cards_fallback
    all_menu_items = load_menu_items()
    limit = max(1, int(popular_menu_limit or 3))
    featured_items = [item for item in all_menu_items if item.get("featured")]
    popular_menu = _pick_popular_items(featured_items, limit)
    if not popular_menu:
        popular_menu = _pick_popular_items(all_menu_items, limit)
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
        preparing_orders = get_user_preparing_orders(user_id)
        order_statuses = list_active_order_statuses(user_id)
        order_status = order_statuses[0] if order_statuses else None
        user = getattr(g, "current_user", None)
        if not user or user.get("id") != user_id:
            user = next((u for u in load_users() if u.get("id") == user_id), None)
        points_balance = int((user or {}).get("balance", 0) or 0)
    else:
        bookings = []
    bookings_view = []
    for booking in bookings:
        item = dict(booking)
        item["date_display"] = _format_date_ddmmyy(booking.get("date"))
        bookings_view.append(item)
    points_balance_formatted = f"{points_balance:,}".replace(",", " ")
    return render_template(
        "index.html",
        news=news_cards,
        menu=popular_menu,
        bookings=bookings_view,
        preparing_orders=preparing_orders,
        order_status=order_status,
        order_statuses=order_statuses,
        points_balance=points_balance,
        points_balance_formatted=points_balance_formatted,
    )


def points_route():
    return redirect(url_for("index"))


def delivery_route():
    return render_template("placeholder.html", title="Доставка")


def notifications_route(load_bookings, get_user_preparing_orders, load_promo_items, booking_duration_minutes):
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
    bookings_view = []
    for booking in bookings_sorted:
        item = dict(booking)
        item["date_display"] = _format_date_ddmmyy(booking.get("date"))
        bookings_view.append(item)

    preparing_orders_view = []
    for order in preparing_orders:
        item = dict(order)
        booking = dict(item.get("booking") or {})
        booking["date_display"] = _format_date_ddmmyy(booking.get("date"))
        item["booking"] = booking
        created_at_raw = str(item.get("created_at", "") or "")
        created_date_raw = created_at_raw.split("T", 1)[0] if created_at_raw else ""
        created_date_display = _format_date_ddmmyy(created_date_raw)
        created_time_display = _format_time_hhmm(created_at_raw)
        is_delivery = str(item.get("order_type") or "").strip().lower() == "delivery"

        if is_delivery:
            item["notice_place"] = "Доставка"
            item["notice_date_display"] = created_date_display
            item["notice_time_display"] = created_time_display
        else:
            item["notice_place"] = f"Стол №{booking.get('table_id') or '—'}"
            item["notice_date_display"] = booking.get("date_display") or created_date_display
            item["notice_time_display"] = booking.get("time") or created_time_display

        totals = summarize_saved_order_totals(item, recompute_zero_bonus=True)
        item["display_total"] = totals["payable_total"]
        item["bonus_earned"] = totals["bonus_earned"]
        item["created_at_display"] = created_date_display
        preparing_orders_view.append(item)

    promo_notifications = []
    for promo in load_promo_items() or []:
        promo_item = dict(promo)
        promo_class = str(promo_item.get("class") or "").strip().lower()
        if promo_class == "reklama":
            promo_item["badge"] = "Реклама"
            promo_item["title"] = "Реклама"
            promo_item["text"] = promo_item.get("text") or "Актуальное предложение."
        elif promo_class == "akciya":
            promo_item["badge"] = "Акция"
            promo_item["title"] = promo_item.get("name") or "Акция"
            promo_item["text"] = promo_item.get("lore") or ""
        else:
            continue
        promo_notifications.append(promo_item)

    return render_template(
        "notifications.html",
        bookings=bookings_view,
        preparing_orders=preparing_orders_view,
        promo_notifications=_pick_random_items(promo_notifications, 1),
        booking_duration_minutes=booking_duration_minutes,
    )


def reviews_route():
    return render_template("placeholder.html", title="Мои отзывы")
