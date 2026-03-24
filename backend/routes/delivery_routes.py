from datetime import datetime

from flask import g, jsonify, redirect, render_template, request, session, url_for
from services.business_logic import current_timestamp_value
from services.promotions import build_priced_order_preview


DELIVERY_SERVICE_FEE = 42


def _delivery_pricing_promo_items(all_promo_items):
    return [
        promo_item
        for promo_item in (all_promo_items or [])
        if str((promo_item or {}).get("class") or "").strip().lower() != "akciya"
    ]


def _resolve_delivery_items_from_preview(preview_items, menu_items: list[dict]) -> list[dict]:
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


def _collect_delivery_form(form):
    return {
        "delivery_name": (form.get("delivery_name") or "").strip(),
        "delivery_phone": (form.get("delivery_phone") or "").strip(),
        "delivery_street": (form.get("delivery_street") or "").strip(),
        "delivery_house": (form.get("delivery_house") or "").strip(),
        "delivery_apartment": (form.get("delivery_apartment") or "").strip(),
        "delivery_entrance": (form.get("delivery_entrance") or "").strip(),
        "delivery_floor": (form.get("delivery_floor") or "").strip(),
        "delivery_intercom": (form.get("delivery_intercom") or "").strip(),
        "delivery_comment": (form.get("delivery_comment") or "").strip()[:300],
    }


def _build_delivery_address(data):
    lines = [f"ул. {data['delivery_street']}, д. {data['delivery_house']}"]
    extras = []
    if data.get("delivery_apartment"):
        extras.append(f"кв./офис {data['delivery_apartment']}")
    if data.get("delivery_entrance"):
        extras.append(f"подъезд {data['delivery_entrance']}")
    if data.get("delivery_floor"):
        extras.append(f"этаж {data['delivery_floor']}")
    if data.get("delivery_intercom"):
        extras.append(f"домофон {data['delivery_intercom']}")
    if extras:
        lines.append(", ".join(extras))
    return "; ".join(lines)


def delivery_menu_route(load_menu_items):
    return render_template("menu.html", items=load_menu_items(), delivery_mode=True)


def delivery_checkout_route(load_users):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы оформить доставку."))

    user = getattr(g, "current_user", None)
    if not user or user.get("id") != user_id:
        user = next((u for u in load_users() if u.get("id") == user_id), None)
    user = user or {}
    error = request.args.get("error", "")
    return render_template(
        "delivery_checkout.html",
        delivery_error=error,
        prefill_name=user.get("name", ""),
        prefill_phone=user.get("phone", ""),
        delivery_service_fee=DELIVERY_SERVICE_FEE,
    )

def delivery_payment_route(
    resolve_order_items,
    load_orders,
    load_promo_application_counts,
    load_promo_items,
    load_menu_items,
    issue_checkout_preview_token,
):
    user_id = session.get("user_id")
    if not user_id:
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Войдите в аккаунт, чтобы перейти к оплате доставки.",
            payment_action_url=url_for("login"),
            payment_action_label="Войти",
        )

    items = resolve_order_items(request.form.get("items_json"))
    if not items:
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Корзина доставки пуста.",
            payment_action_url=url_for("delivery"),
            payment_action_label="В меню доставки",
        )

    data = _collect_delivery_form(request.form)
    required_fields = (
        data["delivery_name"],
        data["delivery_phone"],
        data["delivery_street"],
        data["delivery_house"],
    )
    if not all(required_fields):
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Заполните обязательные поля доставки.",
            payment_action_url=url_for("delivery_checkout"),
            payment_action_label="Вернуться к форме доставки",
        )

    phone_digits = "".join(ch for ch in data["delivery_phone"] if ch.isdigit())
    if len(phone_digits) < 10:
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Укажите корректный телефон получателя.",
            payment_action_url=url_for("delivery_checkout"),
            payment_action_label="Вернуться к форме доставки",
        )

    pricing = build_priced_order_preview(
        items=items,
        service_fee=DELIVERY_SERVICE_FEE,
        user_id=user_id,
        load_orders_fn=load_orders,
        load_promo_application_counts_fn=load_promo_application_counts,
        promo_items=_delivery_pricing_promo_items(load_promo_items()),
        menu_items=load_menu_items(),
    )
    totals = pricing["totals"]
    preview = {
        "items": pricing["items"],
        "items_total": totals["items_total"],
        "service_fee": totals["service_fee"],
        "discount_total": pricing["discount_total"],
        "payable_total": totals["payable_total"],
        "bonus_earned": totals["bonus_earned"],
        "promo_points": pricing["promo_points"],
        "promo_notifications": pricing["promo_notifications"],
        "promotions_applied": pricing["promotions_applied"],
        "discount": pricing["discount"],
        "delivery_name": data["delivery_name"],
        "delivery_phone": data["delivery_phone"],
        "delivery_street": data["delivery_street"],
        "delivery_house": data["delivery_house"],
        "delivery_apartment": data["delivery_apartment"],
        "delivery_entrance": data["delivery_entrance"],
        "delivery_floor": data["delivery_floor"],
        "delivery_intercom": data["delivery_intercom"],
        "delivery_comment": data["delivery_comment"],
        "delivery_address": _build_delivery_address(data),
        "delivery_eta_minutes": 20,
    }
    preview_token = issue_checkout_preview_token(preview, user_id=user_id)
    session["delivery_checkout_preview"] = preview
    return redirect(url_for("delivery_payment_page", preview_token=preview_token))


def delivery_payment_page_route(verify_checkout_preview_token):
    user_id = session.get("user_id")
    if not user_id:
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Войдите в аккаунт, чтобы перейти к оплате доставки.",
            payment_action_url=url_for("login"),
            payment_action_label="Войти",
        )

    preview = session.get("delivery_checkout_preview")
    if not isinstance(preview, dict):
        preview_token = (request.args.get("preview_token") or "").strip()
        preview = verify_checkout_preview_token(preview_token, expected_user_id=user_id)
    if not isinstance(preview, dict):
        return render_template(
            "delivery_payment.html",
            preview={},
            payment_error="Сначала заполните данные доставки и подтвердите заказ.",
            payment_action_url=url_for("delivery_checkout"),
            payment_action_label="Вернуться к форме доставки",
        )
    return render_template(
        "delivery_payment.html",
        preview=preview,
        preview_token=(request.args.get("preview_token") or "").strip(),
        payment_error="",
        payment_action_url=url_for("delivery_checkout"),
        payment_action_label="Вернуться к форме доставки",
    )


def delivery_confirm_route(
    json_file_lock,
    orders_path,
    load_orders,
    next_order_id,
    save_orders,
    users_path,
    load_users,
    save_users,
    verify_checkout_preview_token,
    load_promo_application_counts,
    save_promotion_applications,
    load_promo_items,
    load_menu_items,
):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы оформить доставку."))

    preview = session.get("delivery_checkout_preview")
    if not isinstance(preview, dict):
        preview_token = (request.form.get("preview_token") or "").strip()
        preview = verify_checkout_preview_token(preview_token, expected_user_id=user_id)
    if not isinstance(preview, dict):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Сессия оформления истекла. Повторите заказ."}), 409
        return redirect(url_for("delivery_checkout", error="Сессия оформления истекла. Повторите заказ."))

    preview_items = preview.get("items")
    if not isinstance(preview_items, list) or not preview_items:
        session.pop("delivery_checkout_preview", None)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Корзина доставки пуста."}), 409
        return redirect(url_for("delivery_checkout", error="Корзина доставки пуста."))

    items = _resolve_delivery_items_from_preview(preview_items, load_menu_items())
    if not items:
        session.pop("delivery_checkout_preview", None)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Часть блюд больше недоступна. Повторите заказ."}), 409
        return redirect(url_for("delivery_checkout", error="Часть блюд больше недоступна. Повторите заказ."))

    pricing = build_priced_order_preview(
        items=items,
        service_fee=DELIVERY_SERVICE_FEE,
        user_id=user_id,
        load_orders_fn=load_orders,
        load_promo_application_counts_fn=load_promo_application_counts,
        promo_items=_delivery_pricing_promo_items(load_promo_items()),
        menu_items=load_menu_items(),
    )
    totals = pricing["totals"]
    priced_items = pricing["items"]
    eta_minutes = int(preview.get("delivery_eta_minutes", 20) or 20)

    with json_file_lock(orders_path):
        orders = load_orders()
        order_id = next_order_id(orders)
        new_order = {
            "id": order_id,
            "user_id": user_id,
            "order_type": "delivery",
            "status": "cooking",
            "created_at": current_timestamp_value(),
            "items": priced_items,
            "items_total": totals["items_total"],
            "service_fee": totals["service_fee"],
            "discount_total": pricing["discount_total"],
            "points_applied": 0,
            "payable_total": totals["payable_total"],
            "bonus_earned": totals["bonus_earned"],
            "promo_points": pricing["promo_points"],
            "promo_notifications": list(pricing["promo_notifications"]),
            "promotions_applied": list(pricing["promotions_applied"]),
            "comment": "",
            "serving": {},
            "booking": {},
            "payment_card": {},
            "delivery_name": preview.get("delivery_name", ""),
            "delivery_phone": preview.get("delivery_phone", ""),
            "delivery_street": preview.get("delivery_street", ""),
            "delivery_house": preview.get("delivery_house", ""),
            "delivery_apartment": preview.get("delivery_apartment", ""),
            "delivery_entrance": preview.get("delivery_entrance", ""),
            "delivery_floor": preview.get("delivery_floor", ""),
            "delivery_intercom": preview.get("delivery_intercom", ""),
            "delivery_comment": preview.get("delivery_comment", ""),
            "delivery_address": preview.get("delivery_address", ""),
            "delivery_eta_minutes": eta_minutes,
        }
        orders.append(new_order)
        save_orders(orders)
        save_promotion_applications(
            order_id=order_id,
            user_id=user_id,
            applied_promotions=pricing["promotions_applied"],
            applied_at=datetime.fromisoformat(new_order["created_at"]),
        )

    with json_file_lock(users_path):
        users = load_users()
        user = next((entry for entry in users if int(entry.get("id", 0) or 0) == int(user_id)), None)
        if user is not None:
            user["balance"] = int(user.get("balance", 0) or 0) + totals["bonus_earned"] + pricing["promo_points"]
            save_users(users)
            g.current_user = user
            g.current_user_id = user_id
            g.current_user_loaded = True

    session.pop("delivery_checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1", delivery="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)
