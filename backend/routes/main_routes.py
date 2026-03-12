from flask import redirect, render_template, session, url_for
import hashlib
import secrets


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


_POPULAR_ROTATION_SEED = secrets.token_hex(8)


def _rotation_key(item):
    item_id = str(item.get("id", ""))
    digest = hashlib.sha256(f"{_POPULAR_ROTATION_SEED}:{item_id}".encode("utf-8")).hexdigest()
    return digest


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
    if len(featured_items) > limit:
        featured_items = sorted(featured_items, key=_rotation_key)
    popular_menu = featured_items[:limit]
    if not popular_menu:
        fallback_items = all_menu_items
        if len(fallback_items) > limit:
            fallback_items = sorted(fallback_items, key=_rotation_key)
        popular_menu = fallback_items[:limit]
    if user_id:
        bookings = [b for b in bookings if b.get("user_id") == user_id]
        preparing_orders = get_user_preparing_orders(user_id)
        order_statuses = list_active_order_statuses(user_id)
        order_status = order_statuses[0] if order_statuses else None
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


def notifications_route(load_bookings, get_user_preparing_orders):
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
        item["created_at_display"] = _format_date_ddmmyy(str(item.get("created_at", "")).split("T")[0])
        preparing_orders_view.append(item)

    return render_template(
        "notifications.html",
        bookings=bookings_view,
        preparing_orders=preparing_orders_view,
    )


def reviews_route():
    return render_template("placeholder.html", title="Мои отзывы")
