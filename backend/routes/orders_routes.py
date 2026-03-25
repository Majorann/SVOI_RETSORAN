import json
from datetime import datetime, timedelta

from flask import g, jsonify, redirect, render_template, request, session, url_for
from services.business_logic import current_timestamp_value
from services.promotions import build_priced_order_preview


def _payment_error_response(message: str, redirect_endpoint: str = "checkout", status_code: int = 400):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": False, "error": message}), status_code
    return redirect(url_for(redirect_endpoint, error=message))


def _resolve_checkout_items_from_preview(preview_items, menu_items: list[dict]) -> list[dict]:
    if not isinstance(preview_items, list):
        return []
    menu_index = {}
    for menu_item in menu_items or []:
        if not isinstance(menu_item, dict):
            continue
        try:
            menu_item_id = int(menu_item.get("id"))
        except (TypeError, ValueError):
            continue
        if menu_item_id > 0:
            menu_index[menu_item_id] = menu_item

    resolved_items = []
    for item in preview_items:
        if not isinstance(item, dict) or bool(item.get("is_gift")):
            continue
        try:
            item_id = int(item.get("id"))
            qty = int(item.get("qty"))
        except (TypeError, ValueError):
            continue
        if item_id <= 0 or qty <= 0:
            continue
        menu_item = menu_index.get(item_id)
        if menu_item is None:
            continue
        resolved_items.append(
            {
                "id": item_id,
                "name": menu_item.get("name", ""),
                "price": int(menu_item.get("price", 0) or 0),
                "qty": qty,
                "type": menu_item.get("type", ""),
                "photo": menu_item.get("photo"),
            }
        )
    return resolved_items


def orders_route(list_user_orders):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть историю заказов."))
    user_orders = list_user_orders(user_id)
    return render_template("orders.html", orders=user_orders)


def order_detail_route(order_id, get_user_order):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы открыть детали заказа."))
    order = get_user_order(user_id, order_id)
    if order is None:
        return render_template("placeholder.html", title="Заказ не найден"), 404
    return render_template("order-detail.html", order=order)


def checkout_route(
    latest_user_booking_status,
    booking_duration_minutes,
    get_user_by_id,
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
        user = get_user_by_id(user_id)
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
    get_user_by_id,
    latest_user_booking_status,
    resolve_order_items,
    parse_serving_option,
    list_user_orders,
    load_promo_application_counts,
    load_promo_items,
    load_menu_items,
    issue_checkout_preview_token,
):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы продолжить оплату."))

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
        user = get_user_by_id(user_id)
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
    pricing = build_priced_order_preview(
        items=items,
        points_balance=user_balance,
        use_points=use_points,
        user_id=user_id,
        load_orders_fn=lambda: list_user_orders(user_id),
        load_promo_application_counts_fn=load_promo_application_counts,
        promo_items=load_promo_items(),
        menu_items=load_menu_items(),
    )
    print(
        "[promo] payment preview user_id={0} items={1} promo_points={2} applied={3}".format(
            user_id,
            [{"id": item.get("id"), "qty": item.get("qty")} for item in pricing["items"]],
            pricing["promo_points"],
            pricing["promotions_applied"],
        )
    )
    totals = pricing["totals"]
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
        "items": pricing["items"],
        "items_total": totals["items_total"],
        "items_count": sum(item["qty"] for item in pricing["items"]),
        "discount_total": pricing["discount_total"],
        "points_applied": totals["points_applied"],
        "payable_total": totals["payable_total"],
        "bonus_earned": totals["bonus_earned"],
        "promo_points": pricing["promo_points"],
        "promo_notifications": pricing["promo_notifications"],
        "promotions_applied": pricing["promotions_applied"],
        "discount": pricing["discount"],
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
    preview_token = issue_checkout_preview_token(preview, user_id=user_id) if can_pay else ""
    session["checkout_preview"] = preview if can_pay else None
    return render_template(
        "payment.html",
        preview=preview,
        preview_token=preview_token,
        can_pay=can_pay,
        payment_error_code=payment_error_code,
        payment_error_text=payment_error_text,
    )


def checkout_promo_preview_route(
    get_user_by_id,
    resolve_order_items,
    list_user_orders,
    load_promo_application_counts,
    load_promo_items,
    load_menu_items,
):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Войдите, чтобы продолжить оформление."}), 401

    payload = request.get_json(silent=True) or {}
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = []

    normalized_source_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id"))
            qty = int(item.get("qty"))
        except (TypeError, ValueError):
            continue
        if item_id <= 0 or qty <= 0:
            continue
        normalized_source_items.append({"id": item_id, "qty": qty})

    resolved_items = resolve_order_items(json.dumps(normalized_source_items, ensure_ascii=False))

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
        user = get_user_by_id(user_id)
    if user is None:
        return jsonify({"ok": False, "error": "Пользователь не найден."}), 404

    use_points = bool(payload.get("use_points"))
    pricing = build_priced_order_preview(
        items=resolved_items,
        points_balance=int((user or {}).get("balance", 0) or 0),
        use_points=use_points,
        user_id=user_id,
        load_orders_fn=lambda: list_user_orders(user_id),
        load_promo_application_counts_fn=load_promo_application_counts,
        promo_items=load_promo_items(),
        menu_items=load_menu_items(),
    )
    return jsonify(
        {
            "ok": True,
            "promo_points": pricing["promo_points"],
            "promo_notifications": pricing["promo_notifications"],
            "promotions_applied": pricing["promotions_applied"],
            "discount_total": pricing["discount_total"],
            "discount": pricing["discount"],
            "totals": pricing["totals"],
        }
    )


def payment_confirm_route(
    latest_user_booking_status,
    get_user_by_id,
    create_order,
    apply_user_balance_delta,
    verify_checkout_preview_token,
    load_promo_application_counts,
    save_promotion_applications,
    load_promo_items,
    load_menu_items,
    list_user_orders,
):
    user_id = session.get("user_id")
    if not user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Войдите, чтобы завершить оплату."}), 401
        return redirect(url_for("login", error="Войдите, чтобы завершить оплату."))

    preview = session.get("checkout_preview")
    if not preview:
        preview_token = (request.form.get("preview_token") or "").strip()
        preview = verify_checkout_preview_token(preview_token, expected_user_id=user_id)
        if preview is None:
            return _payment_error_response("Сессия оплаты истекла. Повторите оформление.", status_code=409)

    booking_status = latest_user_booking_status(user_id)
    booking = booking_status.get("booking")
    if booking_status.get("state") != "active":
        session.pop("checkout_preview", None)
        return _payment_error_response("Ваша бронь больше не активна.", status_code=409)

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
        user = get_user_by_id(user_id)
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

    items = _resolve_checkout_items_from_preview(preview_items, load_menu_items())

    if not items:
        session.pop("checkout_preview", None)
        return _payment_error_response("Часть блюд больше недоступна. Проверьте корзину и повторите оплату.", status_code=409)

    current_balance = int(user.get("balance", 0) or 0)
    requested_points = int(preview.get("points_applied", 0) or 0)
    pricing = build_priced_order_preview(
        items=items,
        points_balance=current_balance,
        requested_points=requested_points,
        user_id=user_id,
        load_orders_fn=lambda: list_user_orders(user_id),
        load_promo_application_counts_fn=load_promo_application_counts,
        promo_items=load_promo_items(),
        menu_items=load_menu_items(),
    )
    print(
        "[promo] payment confirm user_id={0} items={1} promo_points={2} applied={3}".format(
            user_id,
            [{"id": item.get("id"), "qty": item.get("qty")} for item in pricing["items"]],
            pricing["promo_points"],
            pricing["promotions_applied"],
        )
    )
    totals = pricing["totals"]
    priced_items = pricing["items"]

    new_order = create_order(
        {
            "user_id": user_id,
            "status": "preparing",
            "created_at": current_timestamp_value(),
            "items": priced_items,
            "items_total": totals["items_total"],
            "discount_total": pricing["discount_total"],
            "points_applied": totals["points_applied"],
            "payable_total": totals["payable_total"],
            "bonus_earned": totals["bonus_earned"],
            "promo_points": pricing["promo_points"],
            "promo_notifications": list(pricing["promo_notifications"]),
            "promotions_applied": list(pricing["promotions_applied"]),
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
    )
    order_id = int(new_order["id"])
    save_promotion_applications(
        order_id=order_id,
        user_id=user_id,
        applied_promotions=pricing["promotions_applied"],
        applied_at=datetime.fromisoformat(new_order["created_at"]),
    )

    user = apply_user_balance_delta(
        user_id,
        -int(totals["points_applied"] or 0) + int(totals["bonus_earned"] or 0) + int(pricing["promo_points"] or 0),
    )
    if user is not None:
        g.current_user = user
        g.current_user_id = user_id
        g.current_user_loaded = True

    session.pop("checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)
