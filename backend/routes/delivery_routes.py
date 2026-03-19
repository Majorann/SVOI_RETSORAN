from flask import g, jsonify, redirect, render_template, request, session, url_for
from services.business_logic import current_timestamp_value
from services.order_totals import calculate_order_totals


DELIVERY_SERVICE_FEE = 42


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

def delivery_payment_route(resolve_order_items, issue_checkout_preview_token):
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

    totals = calculate_order_totals(items, service_fee=DELIVERY_SERVICE_FEE)
    preview = {
        "items": items,
        "items_total": totals["items_total"],
        "service_fee": totals["service_fee"],
        "payable_total": totals["payable_total"],
        "bonus_earned": totals["bonus_earned"],
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
    preview_token = issue_checkout_preview_token(preview)
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
        preview = verify_checkout_preview_token(preview_token)
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
    verify_checkout_preview_token,
):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", error="Войдите, чтобы оформить доставку."))

    preview = session.get("delivery_checkout_preview")
    if not isinstance(preview, dict):
        preview_token = (request.form.get("preview_token") or "").strip()
        preview = verify_checkout_preview_token(preview_token)
    if not isinstance(preview, dict):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Сессия оформления истекла. Повторите заказ."}), 409
        return redirect(url_for("delivery_checkout", error="Сессия оформления истекла. Повторите заказ."))

    items = preview.get("items")
    if not isinstance(items, list) or not items:
        session.pop("delivery_checkout_preview", None)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "Корзина доставки пуста."}), 409
        return redirect(url_for("delivery_checkout", error="Корзина доставки пуста."))

    totals = calculate_order_totals(
        items,
        service_fee=int(preview.get("service_fee", DELIVERY_SERVICE_FEE) or DELIVERY_SERVICE_FEE),
    )
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
            "items": items,
            "items_total": totals["items_total"],
            "service_fee": totals["service_fee"],
            "points_applied": 0,
            "payable_total": totals["payable_total"],
            "bonus_earned": totals["bonus_earned"],
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

    session.pop("delivery_checkout_preview", None)
    order_url = url_for("order_detail", order_id=order_id, paid="1", delivery="1")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "order_url": order_url})
    return redirect(order_url)
