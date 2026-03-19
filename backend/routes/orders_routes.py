from datetime import datetime, timedelta

from flask import g, jsonify, redirect, render_template, request, session, url_for
from services.business_logic import current_timestamp_value
from services.order_totals import calculate_order_totals


def _payment_error_response(message: str, redirect_endpoint: str = "checkout", status_code: int = 400):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": False, "error": message}), status_code
    return redirect(url_for(redirect_endpoint, error=message))


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
        try:
            booking_local_dt = datetime.fromisoformat(f"{booking.get('date')}T{booking.get('time')}")
        except (TypeError, ValueError):
            booking_local_dt = None
        if booking_local_dt:
            custom_time_max = (booking_local_dt + timedelta(minutes=booking_duration_minutes - 1)).strftime("%H:%M")
    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
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
        booking_duration_minutes=booking_duration_minutes,
        checkout_state=checkout_state,
        custom_time_max=custom_time_max,
        active_card=active_card,
        user_balance=user_balance,
        checkout_error=checkout_error,
        menu_catalog=menu_catalog,
    )

def payment_route(
    load_users,
    latest_user_booking_status,
    resolve_order_items,
    parse_serving_option,
    issue_checkout_preview_token,
):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы продолжить оплату."))

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
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

    use_points = (request.form.get("use_points") or "") == "1"
    totals = calculate_order_totals(
        items,
        points_balance=user_balance,
        use_points=use_points,
    )
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
        "items_total": totals["items_total"],
        "items_count": sum(item["qty"] for item in items),
        "points_applied": totals["points_applied"],
        "payable_total": totals["payable_total"],
        "bonus_earned": totals["bonus_earned"],
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
    preview_token = issue_checkout_preview_token(preview) if can_pay else ""
    session["checkout_preview"] = preview if can_pay else None
    return render_template(
        "payment.html",
        preview=preview,
        preview_token=preview_token,
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
    verify_checkout_preview_token,
):
    user_id = session.get("user_id")
    if not user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Войдите, чтобы завершить оплату."}), 401
        return redirect(url_for("login", error="Войдите, чтобы завершить оплату."))

    preview = session.get("checkout_preview")
    if not preview:
        preview_token = (request.form.get("preview_token") or "").strip()
        preview = verify_checkout_preview_token(preview_token)
        if preview is None:
            return _payment_error_response("Сессия оплаты истекла. Повторите оформление.", status_code=409)

    booking_status = latest_user_booking_status(user_id)
    booking = booking_status.get("booking")
    if booking_status.get("state") != "active":
        session.pop("checkout_preview", None)
        return _payment_error_response("Ваша бронь больше не активна.", status_code=409)

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
        users = load_users()
        user = next((u for u in users if u.get("id") == user_id), None)
    if user is None:
        session.clear()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Пользователь не найден. Войдите снова."}), 401
        return redirect(url_for("login", error="Пользователь не найден. Войдите снова."))

    active_card = next((card for card in user.get("cards", []) if card.get("active")), None)
    if active_card is None:
        session.pop("checkout_preview", None)
        return _payment_error_response("Нет активной карты для оплаты.", status_code=409)

    preview_items = preview.get("items")
    if not isinstance(preview_items, list):
        session.pop("checkout_preview", None)
        return redirect(url_for("checkout", error="Некорректные данные заказа."))

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
        return _payment_error_response("Корзина пуста.", status_code=409)

    current_balance = int(user.get("balance", 0) or 0)
    requested_points = int(preview.get("points_applied", 0) or 0)
    totals = calculate_order_totals(
        items,
        points_balance=current_balance,
        requested_points=requested_points,
    )

    with json_file_lock(orders_path):
        orders = load_orders()
        order_id = next_order_id(orders)
        new_order = {
            "id": order_id,
            "user_id": user_id,
            "status": "preparing",
            "created_at": current_timestamp_value(),
            "items": items,
            "items_total": totals["items_total"],
            "points_applied": totals["points_applied"],
            "payable_total": totals["payable_total"],
            "bonus_earned": totals["bonus_earned"],
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
            user["balance"] = max(0, current_balance - totals["points_applied"]) + totals["bonus_earned"]
            save_users(users)
            g.current_user = user
            g.current_user_id = user_id
            g.current_user_loaded = True

    session.pop("checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)
