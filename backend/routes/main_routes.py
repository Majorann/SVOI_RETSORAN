from flask import redirect, render_template, session, url_for


def index_route(
    load_bookings,
    load_promo_items,
    promo_items_to_news_cards,
    news_cards_fallback,
    load_menu_items,
    get_user_preparing_orders,
    list_active_order_statuses,
    load_users,
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
    return render_template(
        "notifications.html",
        bookings=bookings_sorted,
        preparing_orders=preparing_orders,
    )


def reviews_route():
    return render_template("placeholder.html", title="Мои отзывы")
