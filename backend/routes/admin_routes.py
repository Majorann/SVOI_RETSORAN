from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from services.admin_service import ADMIN_DELIVERY_STATUSES, ADMIN_ORDER_STATUSES


def create_admin_blueprint(admin_service):
    admin = Blueprint("admin", __name__, url_prefix="/admin")

    def query_page(default: int = 1) -> int:
        try:
            return max(1, int(request.args.get("page", default)))
        except (TypeError, ValueError):
            return default

    def query_per_page(default: int = 25) -> int:
        try:
            return max(1, int(request.args.get("per_page", default)))
        except (TypeError, ValueError):
            return default

    def current_query_params():
        params = request.args.to_dict(flat=True)
        params.pop("page", None)
        return params

    def guard(is_api: bool = False):
        response = admin_service.require_admin(is_api=is_api)
        if response is not None:
            return response
        return None

    def required_reason():
        json_payload = request.get_json(silent=True) or {}
        reason = str(
            request.form.get("reason")
            or json_payload.get("reason")
            or request.args.get("reason")
            or ""
        ).strip()
        if not reason:
            raise ValueError("Укажите причину действия.")
        return reason

    @admin.get("/")
    def root():
        blocked = guard()
        if blocked is not None:
            return blocked
        return redirect(url_for("admin.dashboard"))

    @admin.get("/dashboard")
    def dashboard():
        blocked = guard()
        if blocked is not None:
            return blocked
        return render_template(
            "admin/dashboard.html",
            title="Панель",
            admin_section="dashboard",
            dashboard=admin_service.get_dashboard_data(),
        )

    @admin.post("/api/content/autosync")
    def api_content_autosync():
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            summary = admin_service.sync_content_from_host(
                admin_user_id=int(session["user_id"]),
                reason=required_reason(),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        toast = (
            "Автосогласование завершено: меню {0} (отключено {1}), акции {2} (отключено {3}), реклама {4}".format(
                summary.get("menu_items_synced", 0),
                summary.get("menu_items_disabled", 0),
                summary.get("promotions_synced", 0),
                summary.get("promotions_disabled", 0),
                summary.get("reklama_found", 0),
            )
        )
        return jsonify({"ok": True, "toast": toast, "summary": summary})

    @admin.get("/orders")
    def orders():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {
            "order_id": request.args.get("order_id", ""),
            "name": request.args.get("name", ""),
            "phone": request.args.get("phone", ""),
            "table_id": request.args.get("table_id", ""),
            "created_at": request.args.get("created_at", ""),
            "status": request.args.get("status", ""),
            "order_type": request.args.get("order_type", ""),
            "preset": request.args.get("preset", ""),
            "per_page": request.args.get("per_page", "25"),
        }
        orders, pagination = admin_service.paginate_orders(filters, page=query_page(), per_page=query_per_page())
        return render_template(
            "admin/orders.html",
            title="Заказы",
            admin_section="orders",
            orders=orders,
            filters=filters,
            pagination=pagination,
            query_params=current_query_params(),
            statuses=ADMIN_ORDER_STATUSES,
            status_options=[{"value": status, "label": admin_service.order_status_filter_label(status)} for status in ADMIN_ORDER_STATUSES],
        )

    @admin.get("/orders/<int:order_id>")
    def order_detail(order_id: int):
        blocked = guard()
        if blocked is not None:
            return blocked
        order = admin_service.get_order_detail(order_id)
        if order is None:
            return render_template("placeholder.html", title="Заказ не найден"), 404
        return render_template(
            "admin/order_detail.html",
            title=f"Заказ #{order_id}",
            admin_section="orders",
            order=order,
            statuses=ADMIN_ORDER_STATUSES,
            status_options=[{"value": status, "label": admin_service.order_status_filter_label(status, order.get("order_type"))} for status in ADMIN_ORDER_STATUSES],
        )

    @admin.get("/bookings")
    def bookings():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {
            "booking_date": request.args.get("booking_date", ""),
            "name": request.args.get("name", ""),
            "phone": request.args.get("phone", ""),
            "table_id": request.args.get("table_id", ""),
            "state": request.args.get("state", ""),
        }
        return render_template(
            "admin/bookings.html",
            title="Брони",
            admin_section="bookings",
            bookings=admin_service.list_bookings(filters),
            filters=filters,
        )

    @admin.get("/bookings/<int:booking_id>")
    def booking_detail(booking_id: int):
        blocked = guard()
        if blocked is not None:
            return blocked
        booking = admin_service.get_booking_detail(booking_id)
        if booking is None:
            return render_template("placeholder.html", title="Бронь не найдена"), 404
        return render_template(
            "admin/booking_detail.html",
            title=f"Бронь #{booking_id}",
            admin_section="bookings",
            booking=booking,
        )

    @admin.get("/delivery")
    def delivery():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {
            "delivery_name": request.args.get("delivery_name", ""),
            "delivery_phone": request.args.get("delivery_phone", ""),
            "delivery_address": request.args.get("delivery_address", ""),
            "status": request.args.get("status", ""),
            "preset": request.args.get("preset", ""),
            "per_page": request.args.get("per_page", "25"),
        }
        delivery_orders, pagination = admin_service.paginate_delivery_orders(filters, page=query_page(), per_page=query_per_page())
        return render_template(
            "admin/delivery.html",
            title="Доставка",
            admin_section="delivery",
            delivery_orders=delivery_orders,
            filters=filters,
            pagination=pagination,
            query_params=current_query_params(),
            statuses=ADMIN_DELIVERY_STATUSES,
            status_options=[{"value": status, "label": admin_service.order_status_filter_label(status, "delivery")} for status in ADMIN_DELIVERY_STATUSES],
        )

    @admin.get("/menu")
    def menu():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {
            "category": request.args.get("category", ""),
            "featured": request.args.get("featured", ""),
        }
        all_menu_items = admin_service.menu_content.load_menu_items_admin()
        items = admin_service.list_menu_items(filters, items=all_menu_items)
        categories = sorted({item.get("type") for item in all_menu_items if item.get("type")})
        next_menu_item_id = max([item.get("id", 0) for item in all_menu_items] or [0]) + 1
        return render_template(
            "admin/menu.html",
            title="Меню",
            admin_section="menu",
            menu_items=items,
            categories=categories,
            filters=filters,
            next_menu_item_id=next_menu_item_id,
        )

    @admin.get("/promo")
    def promo():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {"class_name": request.args.get("class_name", "")}
        all_promo_items = admin_service.menu_content.load_promo_items(include_inactive=True)
        menu_items = admin_service.menu_content.load_menu_items_admin()
        promo_builder_types = sorted({str(item.get("type") or "").strip() for item in menu_items if str(item.get("type") or "").strip()})
        promo_builder_ids = sorted(
            {
                int(item.get("id"))
                for item in menu_items
                if str(item.get("id") or "").strip().isdigit()
            }
        )[:50]
        return render_template(
            "admin/promo.html",
            title="Акции и реклама",
            admin_section="promo",
            promo_items=admin_service.list_promo_items(filters, items=all_promo_items),
            filters=filters,
            promo_builder_types=promo_builder_types,
            promo_builder_ids=promo_builder_ids,
        )

    @admin.get("/analytics")
    def analytics():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {"period": request.args.get("period", "7d"), "mode": request.args.get("mode", "all")}
        return render_template(
            "admin/analytics.html",
            title="Аналитика",
            admin_section="analytics",
            analytics=admin_service.get_analytics(filters),
            filters=filters,
        )

    @admin.get("/users")
    def users():
        blocked = guard()
        if blocked is not None:
            return blocked
        search = request.args.get("search", "")
        per_page = request.args.get("per_page", "25")
        users, pagination = admin_service.list_users(search, page=query_page(), per_page=query_per_page())
        return render_template(
            "admin/users.html",
            title="Пользователи",
            admin_section="users",
            users=users,
            pagination=pagination,
            query_params=current_query_params(),
            search=search,
            per_page=per_page,
        )

    @admin.get("/users/<int:user_id>")
    def user_detail(user_id: int):
        blocked = guard()
        if blocked is not None:
            return blocked
        user = admin_service.get_user_detail(user_id)
        if user is None:
            return render_template("placeholder.html", title="Пользователь не найден"), 404
        return render_template(
            "admin/user_detail.html",
            title=f"Пользователь #{user_id}",
            admin_section="users",
            user=user,
        )

    @admin.get("/content")
    def content():
        blocked = guard()
        if blocked is not None:
            return blocked
        return render_template(
            "admin/content.html",
            title="Контент",
            admin_section="content",
            content=admin_service.get_content_scaffold(),
        )

    @admin.get("/audit-log")
    def audit_log():
        blocked = guard()
        if blocked is not None:
            return blocked
        filters = {
            "admin_user_id": request.args.get("admin_user_id", ""),
            "action_type": request.args.get("action_type", ""),
            "entity_type": request.args.get("entity_type", ""),
            "date_from": request.args.get("date_from", ""),
            "date_to": request.args.get("date_to", ""),
            "per_page": request.args.get("per_page", "25"),
        }
        actions, pagination = admin_service.list_audit_actions(filters=filters, limit=query_per_page(), page=query_page())
        return render_template(
            "admin/audit_log.html",
            title="Журнал действий",
            admin_section="audit-log",
            actions=actions,
            options=admin_service.audit_filter_options(),
            filters=filters,
            pagination=pagination,
            query_params=current_query_params(),
        )

    @admin.post("/api/orders/<int:order_id>/status")
    def api_order_status(order_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            admin_service.update_order_status(
                admin_user_id=int(session["user_id"]),
                order_id=order_id,
                status=(request.get_json(silent=True) or {}).get("status", ""),
                reason=required_reason(),
                entity_action="order_status_changed",
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Статус заказа обновлён."})

    @admin.post("/api/orders/<int:order_id>/cancel")
    def api_order_cancel(order_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            admin_service.cancel_order(admin_user_id=int(session["user_id"]), order_id=order_id, reason=required_reason())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Заказ отменён."})

    @admin.post("/api/bookings/<int:booking_id>/cancel")
    def api_booking_cancel(booking_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            admin_service.cancel_booking(admin_user_id=int(session["user_id"]), booking_id=booking_id, reason=required_reason())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Бронь отменена."})

    @admin.post("/api/delivery/<int:order_id>/status")
    def api_delivery_status(order_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            admin_service.update_delivery_status(
                admin_user_id=int(session["user_id"]),
                order_id=order_id,
                status=(request.get_json(silent=True) or {}).get("status", ""),
                reason=required_reason(),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Статус доставки обновлён."})

    @admin.post("/api/delivery/<int:order_id>/cancel")
    def api_delivery_cancel(order_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        try:
            admin_service.cancel_delivery(admin_user_id=int(session["user_id"]), order_id=order_id, reason=required_reason())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Доставка отменена."})

    @admin.post("/api/users/<int:user_id>/balance")
    def api_user_balance(user_id: int):
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        delta = int((request.get_json(silent=True) or {}).get("delta") or 0)
        try:
            admin_service.adjust_user_balance(
                admin_user_id=int(session["user_id"]),
                user_id=user_id,
                delta=delta,
                reason=required_reason(),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "toast": "Баланс пользователя обновлён."})

    @admin.post("/menu/save")
    def menu_save():
        blocked = guard()
        if blocked is not None:
            return blocked
        try:
            admin_service.save_menu_item(form=request.form, photo=request.files.get("photo"), admin_user_id=int(session["user_id"]))
        except ValueError as exc:
            return redirect(url_for("admin.menu", toast=str(exc)))
        return redirect(url_for("admin.menu", toast="Блюдо сохранено."))

    @admin.post("/promo/save")
    def promo_save():
        blocked = guard()
        if blocked is not None:
            return blocked
        try:
            admin_service.save_promo_item(form=request.form, photo=request.files.get("photo"), admin_user_id=int(session["user_id"]))
        except ValueError as exc:
            return redirect(url_for("admin.promo", toast=str(exc)))
        return redirect(url_for("admin.promo", toast="Промо сохранено."))

    @admin.post("/api/promo/validate")
    def api_promo_validate():
        blocked = guard(is_api=True)
        if blocked is not None:
            return blocked
        payload = request.get_json(silent=True) or {}
        try:
            preview = admin_service.preview_promo_dsl(payload)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify(preview)

    @admin.post("/promo/<class_name>/<int:item_id>/delete")
    def promo_delete(class_name: str, item_id: int):
        blocked = guard()
        if blocked is not None:
            return blocked
        try:
            admin_service.delete_promo_item(
                admin_user_id=int(session["user_id"]),
                class_name=class_name,
                item_id=item_id,
                reason=request.form.get("reason", "").strip(),
            )
        except ValueError as exc:
            return redirect(url_for("admin.promo", toast=str(exc)))
        return redirect(url_for("admin.promo", toast="Промо удалено."))

    return admin
