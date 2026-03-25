import json
import importlib
from collections import OrderedDict
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any

from flask import jsonify, redirect, render_template, session, url_for
from werkzeug.datastructures import FileStorage

from config import MENU_ITEMS_PATH, ORDER_STATUS_STEPS, PROMO_ITEMS_PATH
from services import admin_audit_queries, admin_command_ops, admin_content_management, admin_dashboard_queries, admin_directory_queries, admin_order_queries
from services.business_logic import UTC, build_order_status_timeline_value, current_time_value, parse_iso_datetime_value
from services.order_status import (
    runtime_delivery_overdue_value,
    runtime_effective_status_value,
)


ADMIN_ORDER_STATUSES = ("preparing", "cooking", "ready", "delivering", "served", "cancelled")
ADMIN_DELIVERY_STATUSES = ("cooking", "delivering", "served", "cancelled")
ORDER_STATUS_FILTER_LABELS = {
    "preparing": "Принят",
    "cooking": "Готовится",
    "ready": "Готов",
    "delivering": "Выдача",
    "served": "Завершён",
    "cancelled": "Отменён",
}
DELIVERY_STATUS_FILTER_LABELS = {
    "cooking": "Готовится",
    "delivering": "В пути",
    "served": "Доставлен",
    "cancelled": "Отменён",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_reward_mode(value: Any, *, require_default: bool) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"", "none", "нет"}:
        return "once" if require_default else ""
    if normalized in {"once", "per_match"}:
        return normalized
    return "once" if require_default else ""


def _today_bounds():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)
def _meta_text(payload: OrderedDict) -> str:
    lines = []
    for key, value in payload.items():
        if value in (None, ""):
            continue
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _normalize_db_value(value):
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value
        return normalized.isoformat(timespec="seconds")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dt_time):
        return value.replace(microsecond=0).isoformat()
    return value


def _normalize_pagination(page: int | str | None, per_page: int | str | None, *, default_per_page: int = 25, max_per_page: int = 100):
    try:
        normalized_page = max(1, int(page or 1))
    except (TypeError, ValueError):
        normalized_page = 1
    try:
        normalized_per_page = int(per_page or default_per_page)
    except (TypeError, ValueError):
        normalized_per_page = default_per_page
    normalized_per_page = max(1, min(max_per_page, normalized_per_page))
    return normalized_page, normalized_per_page


def _build_pagination(total: int, page: int, per_page: int):
    total = max(0, int(total or 0))
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(max(1, page), total_pages)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "offset": (page - 1) * per_page,
    }


class AdminService:
    def __init__(self, *, active_storage: str, menu_content):
        self.active_storage = active_storage
        self.menu_content = menu_content
        self._audit_filter_options_cache = None

    @property
    def postgres_ready(self) -> bool:
        return self.active_storage == "postgres"

    def require_admin(self, *, is_api: bool = False):
        user_id = session.get("user_id")
        if not user_id:
            if is_api:
                return jsonify({"ok": False, "error": "Войдите, чтобы открыть админку."}), 401
            return redirect(url_for("login", error="Войдите, чтобы открыть админку."))
        if not self.postgres_ready:
            if is_api:
                return jsonify({"ok": False, "error": "Админка доступна только при работе через Postgres."}), 503
            return render_template("admin/storage_unavailable.html", title="Админка недоступна"), 503
        if not self.is_admin_user(user_id):
            if is_api:
                return jsonify({"ok": False, "error": "Недостаточно прав для доступа к админке."}), 403
            return render_template("admin/access_denied.html", title="Нет доступа"), 403
        return None

    def _run(self, operation):
        if not self.postgres_ready:
            raise RuntimeError("Admin service requires Postgres")
        return self._pg_store()._run_db_operation(operation)

    def _pg_store(self):
        return importlib.import_module("storage.pg_store")

    def _fetch_all(self, query: str, params: tuple = ()):
        def operation():
            pg_store = self._pg_store()
            pg_store._ensure_schema()
            conn = pg_store._get_conn()
            with conn.cursor() as cur:
                cur.execute(query, params)
                columns = [column.name if hasattr(column, "name") else column[0] for column in (cur.description or [])]
                return [dict(zip(columns, [_normalize_db_value(value) for value in row])) for row in cur.fetchall()]

        return self._run(operation)

    def _fetch_one(self, query: str, params: tuple = ()):
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    def _execute(self, query: str, params: tuple = ()):
        def operation():
            pg_store = self._pg_store()
            pg_store._ensure_schema()
            conn = pg_store._get_conn()
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(query, params)

        self._run(operation)

    def _refresh_persisted_order_fields(self, *, order_ids: list[int] | None = None, user_id: int | None = None, active_only: bool = False):
        refresh_method = getattr(self._pg_store(), "refresh_persisted_order_fields", None)
        if not callable(refresh_method):
            return 0
        return refresh_method(order_ids=order_ids, user_id=user_id, active_only=active_only)

    def is_admin_user(self, user_id: int) -> bool:
        row = self._fetch_one("SELECT 1 FROM admin_users WHERE user_id = %s", (int(user_id),))
        return bool(row)

    def log_admin_action(
        self,
        *,
        admin_user_id: int,
        action_type: str,
        entity_type: str,
        entity_id: str | int,
        reason: str,
        payload: dict | None = None,
    ):
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        self._execute(
            """
            INSERT INTO admin_actions (
                admin_user_id, action_type, entity_type, entity_id, reason, payload_json
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(admin_user_id),
                str(action_type),
                str(entity_type),
                str(entity_id),
                str(reason or "").strip(),
                payload_json,
            ),
        )
        self._audit_filter_options_cache = None

    def _build_order_filters(self, filters: dict, *, delivery_only: bool = False):
        return admin_order_queries.build_order_filters(filters, delivery_only=delivery_only)

    def _normalize_order_rows(self, rows: list[dict], *, force_delivery: bool = False):
        return admin_order_queries.normalize_order_rows(self, rows, force_delivery=force_delivery)

    def _query_orders_page(self, filters: dict, *, page: int | None = None, per_page: int | None = None, delivery_only: bool = False):
        return admin_order_queries.query_orders_page(self, filters, page=page, per_page=per_page, delivery_only=delivery_only)

    def list_orders(self, filters: dict):
        orders, _pagination = self._query_orders_page(filters)
        return orders

    def paginate_orders(self, filters: dict, *, page: int = 1, per_page: int = 25):
        return self._query_orders_page(filters, page=page, per_page=per_page)

    def get_order_detail(self, order_id: int):
        return admin_order_queries.get_order_detail(self, order_id)

    def update_order_status(self, *, admin_user_id: int, order_id: int, status: str, reason: str, entity_action: str):
        return admin_command_ops.update_order_status(
            self,
            admin_user_id=admin_user_id,
            order_id=order_id,
            status=status,
            reason=reason,
            entity_action=entity_action,
            allowed_statuses=ADMIN_ORDER_STATUSES,
        )
        normalized = str(status or "").strip().lower()
        if normalized not in ADMIN_ORDER_STATUSES:
            raise ValueError("Недопустимый статус заказа.")
        order = self.get_order_detail(order_id)
        if order is None:
            raise ValueError("Заказ не найден.")
        cancelled_at = datetime.now().isoformat(timespec="seconds") if normalized == "cancelled" else ""
        self._execute(
            "UPDATE orders SET status = %s, cancelled_at = %s WHERE id = %s",
            (normalized, cancelled_at, int(order_id)),
        )
        self._refresh_persisted_order_fields(order_ids=[int(order_id)])
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type=entity_action,
            entity_type="order",
            entity_id=order_id,
            reason=reason,
            payload={"from_status": order.get("status"), "to_status": normalized},
        )

    def cancel_order(self, *, admin_user_id: int, order_id: int, reason: str, action_type: str = "order_cancelled"):
        return admin_command_ops.cancel_order(
            self,
            admin_user_id=admin_user_id,
            order_id=order_id,
            reason=reason,
            action_type=action_type,
            allowed_statuses=ADMIN_ORDER_STATUSES,
        )
        self.update_order_status(
            admin_user_id=admin_user_id,
            order_id=order_id,
            status="cancelled",
            reason=reason,
            entity_action=action_type,
        )

    def list_bookings(self, filters: dict):
        return admin_directory_queries.list_bookings(self, filters)

    def get_booking_detail(self, booking_id: int):
        return admin_directory_queries.get_booking_detail(self, booking_id)

    def cancel_booking(self, *, admin_user_id: int, booking_id: int, reason: str):
        return admin_command_ops.cancel_booking(self, admin_user_id=admin_user_id, booking_id=booking_id, reason=reason)
        booking = self.get_booking_detail(booking_id)
        if booking is None:
            raise ValueError("Бронь не найдена.")
        self._execute("DELETE FROM bookings WHERE id = %s", (int(booking_id),))
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type="booking_cancelled",
            entity_type="booking",
            entity_id=booking_id,
            reason=reason,
            payload={
                "table_id": booking.get("table_id"),
                "booking_date": str(booking.get("booking_date") or ""),
                "booking_time": str(booking.get("booking_time") or ""),
                "user_id": booking.get("user_id"),
            },
        )

    def list_delivery_orders(self, filters: dict):
        delivery_rows, _pagination = self._query_orders_page(filters, delivery_only=True)
        return delivery_rows

    def paginate_delivery_orders(self, filters: dict, *, page: int = 1, per_page: int = 25):
        return self._query_orders_page(filters, page=page, per_page=per_page, delivery_only=True)

    def update_delivery_status(self, *, admin_user_id: int, order_id: int, status: str, reason: str):
        return admin_command_ops.update_delivery_status(
            self,
            admin_user_id=admin_user_id,
            order_id=order_id,
            status=status,
            reason=reason,
            allowed_statuses=ADMIN_DELIVERY_STATUSES,
            order_statuses=ADMIN_ORDER_STATUSES,
        )
        normalized = str(status or "").strip().lower()
        if normalized not in ADMIN_DELIVERY_STATUSES:
            raise ValueError("Недопустимый статус доставки.")
        self.update_order_status(
            admin_user_id=admin_user_id,
            order_id=order_id,
            status=normalized,
            reason=reason,
            entity_action="delivery_status_changed",
        )

    def cancel_delivery(self, *, admin_user_id: int, order_id: int, reason: str):
        return admin_command_ops.cancel_delivery(
            self,
            admin_user_id=admin_user_id,
            order_id=order_id,
            reason=reason,
            order_statuses=ADMIN_ORDER_STATUSES,
        )
        self.cancel_order(
            admin_user_id=admin_user_id,
            order_id=order_id,
            reason=reason,
            action_type="delivery_cancelled",
        )

    def list_users(self, search: str = "", *, page: int = 1, per_page: int = 25):
        return admin_directory_queries.list_users(self, search, page=page, per_page=per_page)

    def get_user_detail(self, user_id: int):
        return admin_directory_queries.get_user_detail(self, user_id)

    def adjust_user_balance(self, *, admin_user_id: int, user_id: int, delta: int, reason: str):
        return admin_command_ops.adjust_user_balance(self, admin_user_id=admin_user_id, user_id=user_id, delta=delta, reason=reason)
        user = self.get_user_detail(user_id)
        if user is None:
            raise ValueError("Пользователь не найден.")
        new_balance = max(0, _safe_int(user.get("balance")) + int(delta))
        self._execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, int(user_id)))
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type="user_bonus_adjusted",
            entity_type="user",
            entity_id=user_id,
            reason=reason,
            payload={"delta": int(delta), "previous_balance": _safe_int(user.get("balance")), "new_balance": new_balance},
        )

    def get_dashboard_data(self):
        return admin_dashboard_queries.get_dashboard_data(self, now=datetime.now())

    def sync_content_from_host(self, *, admin_user_id: int, reason: str):
        return admin_command_ops.sync_content_from_host(self, admin_user_id=admin_user_id, reason=reason)
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValueError("Укажите причину действия.")
        summary = self.menu_content.sync_host_content_to_storage()
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type="content_autosync",
            entity_type="content",
            entity_id="host_sync",
            reason=normalized_reason,
            payload=summary,
        )
        return summary

    def list_audit_actions(self, *, entity_type: str | None = None, entity_id: str | int | None = None, filters: dict | None = None, limit: int = 50, page: int = 1):
        return admin_audit_queries.list_audit_actions(
            self,
            entity_type=entity_type,
            entity_id=entity_id,
            filters=filters,
            limit=limit,
            page=page,
        )

    def audit_filter_options(self):
        return admin_audit_queries.audit_filter_options(self)

    def table_occupancy_for_date(self, booking_date: str):
        return admin_directory_queries.table_occupancy_for_date(self, booking_date)

    def get_analytics(self, filters: dict):
        return admin_dashboard_queries.get_analytics(self, filters, now=datetime.now())

    def list_menu_items(self, filters: dict, items: list[dict] | None = None):
        return admin_content_management.list_menu_items(self, filters, items=items)
        items = list(items) if items is not None else self.menu_content.load_menu_items_admin()
        search = str(filters.get("search") or "").strip().lower()
        category = str(filters.get("category") or "").strip()
        featured = str(filters.get("featured") or "").strip()
        if search:
            items = [item for item in items if search in item.get("name", "").lower()]
        if category:
            items = [item for item in items if item.get("type") == category]
        if featured == "1":
            items = [item for item in items if item.get("featured")]
        return items

    def list_promo_items(self, filters: dict, items: list[dict] | None = None):
        return admin_content_management.list_promo_items(self, filters, items=items)
        items = list(items) if items is not None else self.menu_content.load_promo_items(include_inactive=True)
        item_class = str(filters.get("class_name") or "").strip()
        if item_class:
            items = [item for item in items if item.get("class") == item_class]
        return items

    def get_content_scaffold(self):
        return admin_content_management.get_content_scaffold()
        return {
            "todo_blocks": [
                "Hero banner and homepage text are still hardcoded in Jinja templates.",
                "No separate content store has been introduced in this phase.",
                "Promo-backed homepage blocks are managed in /admin/promo.",
            ]
        }

    def save_menu_item(self, *, form: dict, photo: FileStorage | None, admin_user_id: int):
        return admin_content_management.save_menu_item(
            self,
            form=form,
            photo=photo,
            admin_user_id=admin_user_id,
            menu_items_path=MENU_ITEMS_PATH,
        )
        reason = str(form.get("reason") or "").strip()
        if not reason:
            raise ValueError("Укажите причину изменения.")
        item_id = _safe_int(form.get("id"), 0)
        all_items = self.menu_content.load_menu_items_admin()
        existing = next((item for item in all_items if item["id"] == item_id), None) if item_id else None
        name = str(form.get("name") or "").strip()
        if not name:
            raise ValueError("Название блюда обязательно.")
        folder_name = _normalize_slug(str(form.get("slug") or name))
        target_dir = MENU_ITEMS_PATH / folder_name
        if existing and existing.get("photo"):
            target_dir = MENU_ITEMS_PATH / Path(existing["photo"]).parts[1]
        if not existing:
            item_id = max([item.get("id", 0) for item in all_items] or [0]) + 1
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_photo = self._save_image(target_dir, photo)
        photo_path = str((existing or {}).get("photo") or "").strip()
        if saved_photo and photo is not None and photo.filename:
            extension = Path(photo.filename).suffix.lower()
            photo_path = f"menu_items/{target_dir.name}/photo{extension}"
        menu_payload = {
            "id": item_id,
            "slug": target_dir.name,
            "name": name,
            "type": str(form.get("type") or "").strip(),
            "price": _safe_int(form.get("price"), 0),
            "portion_label": str(form.get("weight") or "").strip(),
            "lore": str(form.get("lore") or "").strip(),
            "featured": _safe_bool(form.get("featured")),
            "popularity": _safe_int(form.get("popularity"), 0),
            "active": _safe_bool(form.get("active"), True),
            "photo_path": photo_path,
            "created_by_admin_user_id": admin_user_id if not existing else None,
            "updated_by_admin_user_id": admin_user_id,
        }
        item_id = self._pg_store().upsert_menu_item(menu_payload)
        if existing:
            action_type = "menu_price_changed" if _safe_int(existing.get("price")) != menu_payload["price"] else "menu_item_updated"
        else:
            action_type = "menu_item_created"
        if existing and not menu_payload["active"]:
            action_type = "menu_item_hidden"
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type=action_type,
            entity_type="menu_item",
            entity_id=item_id,
            reason=reason,
            payload={"name": name, "folder": target_dir.name, "photo_saved": saved_photo},
        )
        self.invalidate_menu_cache()

    def save_promo_item(self, *, form: dict, photo: FileStorage | None, admin_user_id: int):
        return admin_content_management.save_promo_item(
            self,
            form=form,
            photo=photo,
            admin_user_id=admin_user_id,
            promo_items_path=PROMO_ITEMS_PATH,
        )
        reason = str(form.get("reason") or "").strip()
        if not reason:
            raise ValueError("Укажите причину изменения.")
        all_items = self.menu_content.load_promo_items(include_inactive=True)
        item_id = _safe_int(form.get("id"), 0)
        class_name = str(form.get("class_name") or "").strip()
        existing = next((item for item in all_items if item["id"] == item_id and item.get("class") == class_name), None) if item_id else None
        if class_name not in {"akciya", "reklama"}:
            raise ValueError("Недопустимый тип промо.")
        name = str(form.get("name") or form.get("text") or "").strip()
        folder_name = _normalize_slug(str(form.get("slug") or name or f"{class_name}-{item_id or 'new'}"))
        target_dir = PROMO_ITEMS_PATH / class_name / folder_name
        if existing and existing.get("photo"):
            photo_parts = Path(existing["photo"]).parts
            if len(photo_parts) >= 3:
                target_dir = PROMO_ITEMS_PATH / photo_parts[1] / photo_parts[2]
        existing_dir = self._find_promo_dir(class_name=class_name, item_id=item_id) if existing and class_name == "reklama" else None
        if existing_dir is not None:
            target_dir = existing_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_photo = self._save_image(target_dir, photo)

        if class_name == "akciya":
            payload = self.validate_promo_form(form)
            photo_path = None
            current_photo = str((existing or {}).get("photo") or "").strip()
            if saved_photo:
                extension = Path(photo.filename).suffix.lower()
                photo_path = f"promo_items/{class_name}/{target_dir.name}/photo{extension}"
            elif current_photo:
                photo_path = current_photo
            promotion_payload = {
                "id": item_id or None,
                "slug": target_dir.name,
                "name": payload["name"],
                "lore": payload["lore"],
                "active": _safe_bool(form.get("active"), True),
                "priority": _safe_int(form.get("priority"), 100),
                "condition": payload["condition"],
                "reward": payload["reward"],
                "notify": payload["notify"],
                "reward_mode": payload["reward_mode"],
                "limit_per_order": payload["limit_per_order"],
                "limit_per_user_per_day": payload["limit_per_user_per_day"],
                "start_at": payload["start_at"],
                "end_at": payload["end_at"],
                "photo_path": photo_path or "",
                "created_by_admin_user_id": admin_user_id if not existing else None,
                "updated_by_admin_user_id": admin_user_id,
            }
            item_id = self._pg_store().upsert_promotion(promotion_payload)
        else:
            if not existing:
                item_id = max([item.get("id", 0) for item in all_items] or [0]) + 1
            meta_path = target_dir / "item.txt"
            existing_meta = self.menu_content.parse_menu_meta(meta_path) if meta_path.exists() else {}
            payload = OrderedDict()
            payload["id"] = item_id
            payload["class"] = class_name
            payload["text"] = str(form.get("text") or "").strip()
            payload["link"] = str(form.get("link") or "").strip()
            payload["priority"] = _safe_int(form.get("priority"), 100)
            payload["active"] = "true" if _safe_bool(form.get("active"), True) else "false"
            start_at = str(form.get("start_at") or "").strip()
            end_at = str(form.get("end_at") or "").strip()
            if start_at:
                payload["start_at"] = start_at
            if end_at:
                payload["end_at"] = end_at
            for key, value in existing_meta.items():
                if key not in payload:
                    payload[key] = value
            meta_path.write_text(_meta_text(payload), encoding="utf-8")
        action_type = "promo_created" if not existing else "promo_updated"
        is_active = _safe_bool(form.get("active"), True)
        if existing and not is_active:
            action_type = "promo_disabled"
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type=action_type,
            entity_type="promo_item",
            entity_id=item_id,
            reason=reason,
            payload={"class": class_name, "folder": target_dir.name, "photo_saved": saved_photo},
        )
        self.invalidate_menu_cache()

    def validate_promo_form(self, form: dict):
        return admin_content_management.validate_promo_form(self, form)
        promo_payload = {
            "class": "akciya",
            "name": str(form.get("name") or "").strip(),
            "lore": str(form.get("lore") or "").strip(),
            "active": _safe_bool(form.get("active"), True),
            "priority": _safe_int(form.get("priority"), 100),
            "condition": str(form.get("condition") or "").strip(),
            "reward": str(form.get("reward") or "").strip(),
            "notify": str(form.get("notify") or "").strip(),
            "reward_mode": _normalize_reward_mode(
                form.get("reward_mode"),
                require_default=bool(str(form.get("condition") or "").strip() or str(form.get("reward") or "").strip()),
            ),
            "limit_per_order": str(form.get("limit_per_order") or "").strip(),
            "limit_per_user_per_day": str(form.get("limit_per_user_per_day") or "").strip(),
            "start_at": str(form.get("start_at") or "").strip(),
            "end_at": str(form.get("end_at") or "").strip(),
        }
        if not promo_payload["name"]:
            raise ValueError("Укажите название акции.")
        if not promo_payload["lore"]:
            raise ValueError("Укажите описание акции.")
        if promo_payload["condition"] or promo_payload["reward"]:
            try:
                parse_and_validate_promo_source(
                    promo_payload,
                    menu_items=self.menu_content.load_menu_items_admin(),
                )
            except (PromotionDslError, PromotionValidationError) as exc:
                raise ValueError(f"DSL акции невалиден: {exc}") from exc
        return {
            "name": promo_payload["name"],
            "lore": promo_payload["lore"],
            "condition": promo_payload["condition"],
            "reward": promo_payload["reward"],
            "notify": promo_payload["notify"],
            "reward_mode": promo_payload["reward_mode"],
            "limit_per_order": promo_payload["limit_per_order"],
            "limit_per_user_per_day": promo_payload["limit_per_user_per_day"],
            "start_at": promo_payload["start_at"],
            "end_at": promo_payload["end_at"],
        }

    def preview_promo_dsl(self, form: dict):
        return admin_content_management.preview_promo_dsl(self, form)
        payload = self.validate_promo_form(form)
        promo_payload = {
            "class": "akciya",
            "name": payload["name"],
            "active": _safe_bool(form.get("active"), True),
            "priority": _safe_int(form.get("priority"), 100),
            **payload,
        }
        if not promo_payload["condition"] and not promo_payload["reward"]:
            return {
                "ok": True,
                "dsl_text": build_dsl_text_from_promo_item(promo_payload),
                "summary": {
                    "name": promo_payload["name"],
                    "reward_kind": "",
                    "reward_mode": promo_payload["reward_mode"],
                    "priority": promo_payload["priority"],
                    "notify": promo_payload["notify"] or "",
                },
            }
        definition = parse_and_validate_promo_source(
            promo_payload,
            menu_items=self.menu_content.load_menu_items_admin(),
        )
        return {
            "ok": True,
            "dsl_text": build_dsl_text_from_promo_item(promo_payload),
            "summary": {
                "name": definition.name,
                "reward_kind": definition.reward.kind,
                "reward_mode": definition.reward_mode,
                "priority": definition.priority,
                "notify": definition.notify or "",
            },
        }

    def delete_promo_item(self, *, admin_user_id: int, class_name: str, item_id: int, reason: str):
        return admin_content_management.delete_promo_item(
            self,
            admin_user_id=admin_user_id,
            class_name=class_name,
            item_id=item_id,
            reason=reason,
            promo_items_path=PROMO_ITEMS_PATH,
        )
        if not reason:
            raise ValueError("Укажите причину удаления.")
        items = self.menu_content.load_promo_items(include_inactive=True)
        item = next((entry for entry in items if entry.get("class") == class_name and entry.get("id") == int(item_id)), None)
        if item is None:
            raise ValueError("Промо-элемент не найден.")
        target_dir = None
        if item.get("photo"):
            parts = Path(item["photo"]).parts
            if len(parts) >= 3:
                target_dir = PROMO_ITEMS_PATH / parts[1] / parts[2]
        if class_name == "akciya":
            self._pg_store().delete_promotion(int(item_id))
        else:
            if target_dir is None:
                target_dir = self._find_promo_dir(class_name=class_name, item_id=item_id)
            if target_dir is None:
                raise ValueError("Промо-элемент не найден.")
            if target_dir.exists():
                shutil.rmtree(target_dir)
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type="promo_deleted",
            entity_type="promo_item",
            entity_id=item_id,
            reason=reason,
            payload={"class": class_name, "folder": target_dir.name if target_dir is not None else ""},
        )
        self.invalidate_menu_cache()

    def _find_promo_dir(self, *, class_name: str, item_id: int) -> Path | None:
        return admin_content_management.find_promo_dir(
            self,
            class_name=class_name,
            item_id=item_id,
            promo_items_path=PROMO_ITEMS_PATH,
        )
        promo_class_dir = PROMO_ITEMS_PATH / class_name
        if not promo_class_dir.exists():
            return None
        normalized_item_id = int(item_id)
        for meta_path in sorted(promo_class_dir.rglob("item.txt")):
            meta = self.menu_content.parse_menu_meta(meta_path)
            if str(meta.get("class") or "").strip() != class_name:
                continue
            if _safe_int(meta.get("id"), 0) != normalized_item_id:
                continue
            return meta_path.parent
        return None

    def _save_image(self, target_dir: Path, upload: FileStorage | None):
        return admin_content_management.save_image(target_dir, upload)
        if upload is None or not upload.filename:
            return False
        extension = Path(upload.filename).suffix.lower()
        if extension not in IMAGE_EXTENSIONS:
            raise ValueError("Поддерживаются только PNG, JPG и WEBP.")
        for child in target_dir.iterdir():
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                child.unlink()
        upload.save(target_dir / f"photo{extension}")
        return True

    def invalidate_menu_cache(self):
        return admin_content_management.invalidate_menu_cache(self)
        if hasattr(self.menu_content, "invalidate_local_cache"):
            self.menu_content.invalidate_local_cache()
        client = self.menu_content.get_redis_client()
        if client is None:
            return
        try:
            client.delete(self.menu_content.menu_cache_key)
        except Exception:
            return

    def booking_datetime(self, booking: dict):
        date_value = booking.get("booking_date") or booking.get("date")
        time_value = booking.get("booking_time") or booking.get("time")
        if not date_value or not time_value:
            return None
        try:
            return datetime.fromisoformat(f"{str(date_value)}T{str(time_value)[:5]}")
        except ValueError:
            return None

    def booking_state(self, booking: dict, now: datetime):
        booking_dt = self.booking_datetime(booking)
        if booking_dt is None:
            return "active"
        if booking_dt + timedelta(minutes=60) < now:
            return "past"
        return "active"

    def _build_runtime_timeline(self, order: dict, now: datetime | None = None):
        return build_order_status_timeline_value(
            order,
            now or current_time_value(),
            ORDER_STATUS_STEPS,
            parse_iso_datetime_value,
        )

    def resolve_effective_order_status(self, order: dict, now: datetime | None = None):
        return runtime_effective_status_value(order, now)

    def is_delivery_overdue(self, order: dict, now: datetime | None = None):
        return runtime_delivery_overdue_value(order, now)

    def status_label(self, status: str | None, order_type: str | None = None):
        mapping = {
            "preparing": "Готовится",
            "cooking": "Готовится",
            "ready": "Готов",
            "delivering": "В пути",
            "served": "Выдан",
            "cancelled": "Отменён",
        }
        normalized = str(status or "").strip().lower()
        normalized_order_type = str(order_type or "").strip().lower()
        if normalized == "served" and normalized_order_type == "delivery":
            return "Доставлен"
        return mapping.get(normalized, normalized or "—")

    def order_status_filter_label(self, status: str | None, order_type: str | None = None):
        normalized = str(status or "").strip().lower()
        normalized_order_type = str(order_type or "").strip().lower()
        if normalized_order_type == "delivery":
            return DELIVERY_STATUS_FILTER_LABELS.get(normalized, self.status_label(normalized, normalized_order_type))
        return ORDER_STATUS_FILTER_LABELS.get(normalized, self.status_label(normalized, normalized_order_type))

    def order_type_label(self, order_type: str | None):
        mapping = {
            "dine_in": "Зал",
            "delivery": "Доставка",
        }
        normalized = str(order_type or "").strip().lower()
        return mapping.get(normalized, normalized or "—")
