from datetime import datetime, timedelta

from flask import jsonify, redirect, render_template, request, session, url_for


def orders_route(load_orders):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть историю заказов."))
    user_orders = [o for o in load_orders() if o.get("user_id") == user_id]
    user_orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return render_template("orders.html", orders=user_orders)


def order_detail_route(order_id, load_orders):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть детали заказа."))
    order = next((o for o in load_orders() if o.get("id") == order_id and o.get("user_id") == user_id), None)
    if order is None:
        return render_template("placeholder.html", title="Заказ не найден"), 404
    return render_template("order-detail.html", order=order)


def checkout_route(
    latest_user_booking_status,
    parse_datetime,
    booking_duration_minutes,
    load_users,
    load_menu_items,
):
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
            custom_time_max = (booking_dt + timedelta(minutes=booking_duration_minutes - 1)).strftime("%H:%M")
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


def payment_route(load_users, latest_user_booking_status, resolve_order_items, parse_serving_option):
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


def payment_confirm_route(
    latest_user_booking_status,
    load_users,
    json_file_lock,
    orders_path,
    load_orders,
    next_order_id,
    save_orders,
    users_path,
    save_users,
):
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

    with json_file_lock(orders_path):
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

    with json_file_lock(users_path):
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
