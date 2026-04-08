from flask import g, redirect, render_template, url_for
import secrets
from services.order_totals import summarize_saved_order_totals
from services.url_safety import normalize_public_link


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


def _sanitize_static_filename(value):
    text = str(value or "").strip().lstrip("/")
    if not text:
        return ""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return text


def _sanitize_news_cards(cards):
    sanitized_cards = []
    for card in cards or []:
        item = dict(card or {})
        item["photo"] = _sanitize_static_filename(item.get("photo"))
        item["link"] = normalize_public_link(item.get("link"))
        sanitized_cards.append(item)
    return sanitized_cards


def _sanitize_menu_items(items):
    sanitized_items = []
    for item in items or []:
        entry = dict(item or {})
        entry["photo"] = _sanitize_static_filename(entry.get("photo"))
        sanitized_items.append(entry)
    return sanitized_items


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


def _pick_popular_items_from_analytics(get_popular_analytics, items, limit):
    if not callable(get_popular_analytics):
        return []
    menu_pool = list(items or [])
    if not menu_pool:
        return []
    try:
        analytics = get_popular_analytics({"period": "30d", "mode": "all"}) or {}
    except Exception:
        return []
    ranked_items = analytics.get("top_qty_items") or []
    if not ranked_items:
        return []
    item_index = {}
    for item in menu_pool:
        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id > 0:
            item_index[item_id] = item
    selected = []
    safe_limit = max(1, int(limit or 1))
    for ranked in ranked_items:
        try:
            item_id = int(ranked.get("id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        item = item_index.get(item_id)
        if not item:
            continue
        selected.append(item)
        if len(selected) >= safe_limit:
            break
    if len(selected) >= safe_limit:
        return selected
    selected_ids = {
        int(item.get("id") or 0)
        for item in selected
        if int(item.get("id") or 0) > 0
    }
    remainder = []
    for item in menu_pool:
        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        if item_id > 0 and item_id in selected_ids:
            continue
        remainder.append(item)
    if remainder:
        selected.extend(_pick_random_items(remainder, safe_limit - len(selected)))
    return selected


def _pick_random_items(items, limit):
    pool = list(items or [])
    if not pool:
        return []
    safe_limit = max(1, int(limit or 1))
    if len(pool) <= safe_limit:
        return pool[:safe_limit]
    return _POPULAR_ROTATOR.sample(pool, safe_limit)


def index_route(
    list_user_bookings,
    load_promo_items,
    promo_items_to_news_cards,
    news_cards_fallback,
    load_menu_items,
    get_popular_analytics,
    get_user_preparing_orders,
    list_active_order_statuses,
    *compat_args,
):
    get_user_by_id = None
    popular_menu_limit = 3
    if len(compat_args) == 1:
        popular_menu_limit = compat_args[0]
    elif len(compat_args) >= 2:
        get_user_by_id = compat_args[0]
        popular_menu_limit = compat_args[1]
    user_id = getattr(g, "current_user_id", None)
    bookings = []
    preparing_orders = []
    order_status = None
    order_statuses = []
    points_balance = 0
    promo_items = load_promo_items()
    promo_news = promo_items_to_news_cards(promo_items)
    news_cards = _sanitize_news_cards(promo_news or news_cards_fallback)
    all_menu_items = load_menu_items()
    limit = max(1, int(popular_menu_limit or 3))
    popular_menu = _pick_popular_items_from_analytics(get_popular_analytics, all_menu_items, limit)
    featured_items = [item for item in all_menu_items if item.get("featured")]
    if not popular_menu:
        featured_items.sort(key=lambda item: (-int(item.get("popularity") or 0), int(item.get("id") or 0)))
        popular_menu = _pick_popular_items(featured_items, limit)
    if not popular_menu:
        all_menu_items = sorted(
            all_menu_items,
            key=lambda item: (-int(item.get("popularity") or 0), bool(item.get("featured")) is False, int(item.get("id") or 0)),
        )
        popular_menu = _pick_popular_items(all_menu_items, limit)
    popular_menu = _sanitize_menu_items(popular_menu)
    if user_id:
        bookings = list_user_bookings(user_id)
        preparing_orders = get_user_preparing_orders(user_id)
        order_statuses = list_active_order_statuses(user_id)
        order_status = order_statuses[0] if order_statuses else None
        user = getattr(g, "current_user", None)
        if (not user or user.get("id") != user_id) and callable(get_user_by_id):
            user = get_user_by_id(user_id)
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


def notifications_route(list_user_bookings, get_user_preparing_orders, load_promo_items, booking_duration_minutes):
    user_id = getattr(g, "current_user_id", None)
    bookings = []
    preparing_orders = []
    if user_id:
        bookings = list_user_bookings(user_id)
        preparing_orders = get_user_preparing_orders(user_id)
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
    promo_candidates = []
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
            promo_item["is_highlighted"] = True
        else:
            continue
        promo_candidates.append(promo_item)
    if promo_candidates:
        promo_notifications = _pick_random_items(promo_candidates, 1)

    return render_template(
        "notifications.html",
        bookings=bookings_view,
        preparing_orders=preparing_orders_view,
        promo_notifications=promo_notifications,
        booking_duration_minutes=booking_duration_minutes,
    )


def reviews_route():
    return render_template("placeholder.html", title="Мои отзывы")
