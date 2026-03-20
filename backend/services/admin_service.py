import json
import importlib
import re
import shutil
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import jsonify, redirect, render_template, session, url_for
from werkzeug.datastructures import FileStorage

from config import MENU_ITEMS_PATH, ORDER_STATUS_STEPS, PROMO_ITEMS_PATH, TABLES
from services.business_logic import build_order_status_timeline_value, current_time_value, parse_iso_datetime_value
from services.order_totals import summarize_saved_order_totals


ADMIN_ORDER_STATUSES = ("preparing", "cooking", "ready", "delivering", "served", "cancelled")
ADMIN_DELIVERY_STATUSES = ("cooking", "delivering", "served", "cancelled")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
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


def _parse_iso_datetime(value: str | None):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _today_bounds():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


def _normalize_slug(value: str) -> str:
    slug = re.sub(r'[<>:"/\\|?*]+', "_", str(value or "").strip())
    slug = re.sub(r"\s+", " ", slug).strip(" .")
    return slug or "item"


def _mask_card(card: dict) -> dict:
    return {
        "brand": card.get("brand") or "MIR",
        "last4": card.get("last4") or "0000",
        "active": bool(card.get("active")),
        "holder": card.get("holder") or "",
        "expiry": card.get("expiry") or "",
    }


def _meta_text(payload: OrderedDict) -> str:
    lines = []
    for key, value in payload.items():
        if value in (None, ""):
            continue
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


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
                return [dict(zip(columns, row)) for row in cur.fetchall()]

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

    def _build_order_filters(self, filters: dict):
        conditions = []
        params = []
        order_id = str(filters.get("order_id") or "").strip()
        if order_id:
            conditions.append("CAST(o.id AS TEXT) ILIKE %s")
            params.append(f"%{order_id}%")
        name = str(filters.get("name") or "").strip()
        if name:
            like = f"%{name}%"
            conditions.append("(COALESCE(u.name, '') ILIKE %s OR COALESCE(o.delivery_name, '') ILIKE %s)")
            params.extend([like, like])
        phone = str(filters.get("phone") or "").strip()
        if phone:
            like = f"%{phone}%"
            conditions.append("(COALESCE(u.phone, '') ILIKE %s OR COALESCE(o.delivery_phone, '') ILIKE %s)")
            params.extend([like, like])
        table_id = str(filters.get("table_id") or "").strip()
        if table_id:
            conditions.append("CAST(COALESCE(o.booking_table_id, 0) AS TEXT) ILIKE %s")
            params.append(f"%{table_id}%")
        created_at = str(filters.get("created_at") or "").strip()
        if created_at:
            conditions.append("COALESCE(o.created_at, '') ILIKE %s")
            params.append(f"%{created_at}%")
        status = str(filters.get("status") or "").strip()
        if status:
            conditions.append("o.status = %s")
            params.append(status)
        order_type = str(filters.get("order_type") or "").strip()
        if order_type:
            conditions.append("o.order_type = %s")
            params.append(order_type)
        preset = str(filters.get("preset") or "").strip()
        start, end = _today_bounds()
        if preset == "today":
            conditions.append("o.created_at >= %s AND o.created_at < %s")
            params.extend([start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")])
        elif preset == "last_hour":
            conditions.append("o.created_at >= %s")
            params.append((datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds"))
        elif preset == "active":
            conditions.append("LOWER(o.status) NOT IN ('served', 'cancelled')")
        elif preset == "cancelled":
            conditions.append("LOWER(o.status) = 'cancelled'")
        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        return where_sql, tuple(params)

    def list_orders(self, filters: dict):
        where_sql, params = self._build_order_filters(filters)
        status_filter = str(filters.get("status") or "").strip().lower()
        preset = str(filters.get("preset") or "").strip().lower()
        rows = self._fetch_all(
            f"""
            SELECT
                o.*,
                u.name AS user_name,
                u.phone AS user_phone,
                COUNT(oi.order_id) AS items_count
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            {where_sql}
            GROUP BY o.id, u.id
            ORDER BY o.created_at DESC, o.id DESC
            """,
            params,
        )
        orders = []
        now = current_time_value()
        for row in rows:
            totals = summarize_saved_order_totals(row, recompute_zero_bonus=True)
            effective_status = self.resolve_effective_order_status(row, now)
            row["status"] = effective_status
            row["totals"] = totals
            row["is_delivery"] = (row.get("order_type") or "").lower() == "delivery"
            row["order_type_label"] = self.order_type_label(row.get("order_type"))
            row["table_label"] = f"Стол №{row.get('booking_table_id')}" if row.get("booking_table_id") else "—"
            row["status_label"] = self.status_label(effective_status, row.get("order_type"))
            row["delivery_overdue"] = self.is_delivery_overdue(row, now)
            orders.append(row)
        if status_filter:
            orders = [order for order in orders if str(order.get("status") or "").lower() == status_filter]
        if preset == "active":
            orders = [order for order in orders if str(order.get("status") or "").lower() not in {"served", "cancelled"}]
        elif preset == "cancelled":
            orders = [order for order in orders if str(order.get("status") or "").lower() == "cancelled"]
        return orders

    def paginate_orders(self, filters: dict, *, page: int = 1, per_page: int = 25):
        normalized_page, normalized_per_page = _normalize_pagination(page, per_page)
        orders = self.list_orders(filters)
        pagination = _build_pagination(len(orders), normalized_page, normalized_per_page)
        start = pagination["offset"]
        end = start + normalized_per_page
        return orders[start:end], pagination

    def get_order_detail(self, order_id: int):
        row = self._fetch_one(
            """
            SELECT o.*, u.name AS user_name, u.phone AS user_phone, u.balance AS user_balance
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.id = %s
            """,
            (int(order_id),),
        )
        if row is None:
            return None
        now = current_time_value()
        effective_status = self.resolve_effective_order_status(row, now)
        row["status"] = effective_status
        row["order_type_label"] = self.order_type_label(row.get("order_type"))
        row["items"] = self._fetch_all(
            """
            SELECT position, item_id, name, price, qty, photo
            FROM order_items
            WHERE order_id = %s
            ORDER BY position
            """,
            (int(order_id),),
        )
        row["totals"] = summarize_saved_order_totals(row, recompute_zero_bonus=True)
        row["status_label"] = self.status_label(effective_status, row.get("order_type"))
        row["related_booking"] = None
        if row.get("booking_date") and row.get("booking_time"):
            row["related_booking"] = self._fetch_one(
                """
                SELECT id, table_id, booking_date, booking_time, name
                FROM bookings
                WHERE user_id = %s
                  AND table_id = COALESCE(%s, table_id)
                  AND booking_date = %s
                  AND booking_time = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    int(row["user_id"]),
                    row.get("booking_table_id"),
                    row.get("booking_date"),
                    row.get("booking_time"),
                ),
            )
        row["audit_actions"] = self.list_audit_actions(entity_type="order", entity_id=row["id"], limit=20)
        return row

    def update_order_status(self, *, admin_user_id: int, order_id: int, status: str, reason: str, entity_action: str):
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
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type=entity_action,
            entity_type="order",
            entity_id=order_id,
            reason=reason,
            payload={"from_status": order.get("status"), "to_status": normalized},
        )

    def cancel_order(self, *, admin_user_id: int, order_id: int, reason: str, action_type: str = "order_cancelled"):
        self.update_order_status(
            admin_user_id=admin_user_id,
            order_id=order_id,
            status="cancelled",
            reason=reason,
            entity_action=action_type,
        )

    def list_bookings(self, filters: dict):
        conditions = []
        params = []
        booking_date = str(filters.get("booking_date") or "").strip()
        if booking_date:
            conditions.append("CAST(b.booking_date AS TEXT) = %s")
            params.append(booking_date)
        name = str(filters.get("name") or "").strip()
        if name:
            like = f"%{name}%"
            conditions.append("(COALESCE(b.name, '') ILIKE %s OR COALESCE(u.name, '') ILIKE %s)")
            params.extend([like, like])
        phone = str(filters.get("phone") or "").strip()
        if phone:
            conditions.append("COALESCE(u.phone, '') ILIKE %s")
            params.append(f"%{phone}%")
        table_id = str(filters.get("table_id") or "").strip()
        if table_id:
            conditions.append("CAST(b.table_id AS TEXT) = %s")
            params.append(table_id)
        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._fetch_all(
            f"""
            SELECT
                b.id,
                b.user_id,
                b.table_id,
                b.booking_date,
                b.booking_time,
                b.name,
                b.created_at,
                u.name AS user_name,
                u.phone AS user_phone,
                COUNT(o.id) AS related_orders_count
            FROM bookings b
            LEFT JOIN users u ON u.id = b.user_id
            LEFT JOIN orders o
              ON o.user_id = b.user_id
             AND o.booking_table_id = b.table_id
             AND o.booking_date = b.booking_date
             AND o.booking_time = b.booking_time
            {where_sql}
            GROUP BY b.id, u.id
            ORDER BY b.booking_date DESC, b.booking_time DESC, b.id DESC
            """,
            tuple(params),
        )
        now = datetime.now()
        for row in rows:
            row["state"] = self.booking_state(row, now)
            row["state_label"] = {"active": "Активна", "past": "Прошла"}.get(row["state"], "Активна")
            row["related_orders_count"] = _safe_int(row.get("related_orders_count"))
        state_filter = str(filters.get("state") or "").strip()
        if state_filter:
            rows = [row for row in rows if row["state"] == state_filter]
        return rows

    def get_booking_detail(self, booking_id: int):
        row = self._fetch_one(
            """
            SELECT
                b.id,
                b.user_id,
                b.table_id,
                b.booking_date,
                b.booking_time,
                b.name,
                b.created_at,
                u.name AS user_name,
                u.phone AS user_phone
            FROM bookings b
            LEFT JOIN users u ON u.id = b.user_id
            WHERE b.id = %s
            """,
            (int(booking_id),),
        )
        if row is None:
            return None
        row["state"] = self.booking_state(row, datetime.now())
        row["related_orders"] = self._fetch_all(
            """
            SELECT id, status, order_type, created_at, payable_total
            FROM orders
            WHERE user_id = %s
              AND booking_table_id = %s
              AND booking_date = %s
              AND booking_time = %s
            ORDER BY created_at DESC
            """,
            (row["user_id"], row["table_id"], row["booking_date"], row["booking_time"]),
        )
        now = current_time_value()
        for order in row["related_orders"]:
            effective_status = self.resolve_effective_order_status(order, now)
            order["status"] = effective_status
            order["status_label"] = self.status_label(effective_status, order.get("order_type"))
            order["order_type_label"] = self.order_type_label(order.get("order_type"))
        row["occupancy"] = self.table_occupancy_for_date(str(row["booking_date"]))
        row["audit_actions"] = self.list_audit_actions(entity_type="booking", entity_id=row["id"], limit=20)
        return row

    def cancel_booking(self, *, admin_user_id: int, booking_id: int, reason: str):
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
        conditions = ["o.order_type = 'delivery'"]
        params = []
        status_filter = str(filters.get("status") or "").strip().lower()
        delivery_name = str(filters.get("delivery_name") or "").strip()
        if delivery_name:
            conditions.append("COALESCE(o.delivery_name, '') ILIKE %s")
            params.append(f"%{delivery_name}%")
        delivery_phone = str(filters.get("delivery_phone") or "").strip()
        if delivery_phone:
            conditions.append("COALESCE(o.delivery_phone, '') ILIKE %s")
            params.append(f"%{delivery_phone}%")
        delivery_address = str(filters.get("delivery_address") or "").strip()
        if delivery_address:
            conditions.append("COALESCE(o.delivery_address, '') ILIKE %s")
            params.append(f"%{delivery_address}%")
        preset = str(filters.get("preset") or "").strip()
        start, end = _today_bounds()
        if preset == "today":
            conditions.append("o.created_at >= %s AND o.created_at < %s")
            params.extend([start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")])
        elif preset == "last_hour":
            conditions.append("o.created_at >= %s")
            params.append((datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds"))
        elif preset == "active":
            conditions.append("LOWER(o.status) NOT IN ('served', 'cancelled')")
        elif preset == "served":
            conditions.append("LOWER(o.status) = 'served'")
        rows = self._fetch_all(
            f"""
            SELECT
                o.*,
                u.name AS user_name,
                u.phone AS user_phone,
                COUNT(oi.order_id) AS items_count
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE {' AND '.join(conditions)}
            GROUP BY o.id, u.id
            ORDER BY o.created_at DESC, o.id DESC
            """,
            tuple(params),
        )
        normalized_rows = []
        now = current_time_value()
        for row in rows:
            totals = summarize_saved_order_totals(row, recompute_zero_bonus=True)
            effective_status = self.resolve_effective_order_status(row, now)
            row["status"] = effective_status
            row["totals"] = totals
            row["is_delivery"] = True
            row["order_type_label"] = self.order_type_label(row.get("order_type"))
            row["table_label"] = "—"
            row["status_label"] = self.status_label(effective_status, row.get("order_type"))
            row["delivery_overdue"] = self.is_delivery_overdue(row, now)
            normalized_rows.append(row)
        preset = str(filters.get("preset") or "").strip().lower()
        if status_filter:
            normalized_rows = [row for row in normalized_rows if str(row.get("status") or "").lower() == status_filter]
        if preset == "active":
            normalized_rows = [row for row in normalized_rows if str(row.get("status") or "").lower() not in {"served", "cancelled"}]
        elif preset == "served":
            normalized_rows = [row for row in normalized_rows if str(row.get("status") or "").lower() == "served"]
        return normalized_rows

    def update_delivery_status(self, *, admin_user_id: int, order_id: int, status: str, reason: str):
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
        self.cancel_order(
            admin_user_id=admin_user_id,
            order_id=order_id,
            reason=reason,
            action_type="delivery_cancelled",
        )

    def list_users(self, search: str = "", *, page: int = 1, per_page: int = 25):
        normalized_page, normalized_per_page = _normalize_pagination(page, per_page)
        params = ()
        where_sql = ""
        if search:
            like = f"%{search}%"
            where_sql = "WHERE u.name ILIKE %s OR u.phone ILIKE %s"
            params = (like, like)
        count_row = self._fetch_one(
            f"""
            SELECT COUNT(*) AS count
            FROM users u
            {where_sql}
            """,
            params,
        ) or {"count": 0}
        pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
        rows = self._fetch_all(
            f"""
            SELECT
                u.id,
                u.name,
                u.phone,
                u.balance,
                u.created_at,
                COUNT(DISTINCT o.id) AS orders_count,
                COUNT(DISTINCT b.id) AS bookings_count,
                EXISTS (SELECT 1 FROM admin_users au WHERE au.user_id = u.id) AS is_admin
            FROM users u
            LEFT JOIN orders o ON o.user_id = u.id
            LEFT JOIN bookings b ON b.user_id = u.id
            {where_sql}
            GROUP BY u.id
            ORDER BY u.created_at DESC, u.id DESC
            LIMIT {pagination["per_page"]} OFFSET {pagination["offset"]}
            """,
            params,
        )
        return rows, pagination

    def get_user_detail(self, user_id: int):
        user = self._fetch_one(
            """
            SELECT
                u.id,
                u.name,
                u.phone,
                u.balance,
                u.created_at,
                EXISTS (SELECT 1 FROM admin_users au WHERE au.user_id = u.id) AS is_admin
            FROM users u
            WHERE u.id = %s
            """,
            (int(user_id),),
        )
        if user is None:
            return None
        user["cards"] = [
            _mask_card(card)
            for card in self._fetch_all(
                """
                SELECT brand, last4, active, holder, expiry, created_at
                FROM user_cards
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (int(user_id),),
            )
        ]
        user["orders"] = self._fetch_all(
            """
            SELECT id, order_type, status, created_at, payable_total
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (int(user_id),),
        )
        now = current_time_value()
        for order in user["orders"]:
            effective_status = self.resolve_effective_order_status(order, now)
            order["status"] = effective_status
            order["status_label"] = self.status_label(effective_status, order.get("order_type"))
            order["order_type_label"] = self.order_type_label(order.get("order_type"))
        user["bookings"] = self._fetch_all(
            """
            SELECT id, table_id, booking_date, booking_time, created_at
            FROM bookings
            WHERE user_id = %s
            ORDER BY booking_date DESC, booking_time DESC
            LIMIT 10
            """,
            (int(user_id),),
        )
        user["audit_actions"] = self.list_audit_actions(entity_type="user", entity_id=user["id"], limit=20)
        user["balance_actions"] = [action for action in user["audit_actions"] if action.get("action_type") == "user_bonus_adjusted"]
        return user

    def adjust_user_balance(self, *, admin_user_id: int, user_id: int, delta: int, reason: str):
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
        start, end = _today_bounds()
        today_orders = self._fetch_all(
            """
            SELECT * FROM orders
            WHERE created_at >= %s AND created_at < %s
            ORDER BY created_at DESC
            """,
            (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
        )
        all_orders = self._fetch_all("SELECT * FROM orders ORDER BY created_at DESC LIMIT 200")
        all_bookings = self._fetch_all(
            """
            SELECT b.id, b.user_id, b.table_id, b.booking_date, b.booking_time, b.name, b.created_at, u.phone AS user_phone
            FROM bookings b
            LEFT JOIN users u ON u.id = b.user_id
            ORDER BY b.booking_date, b.booking_time
            """
        )
        latest_actions = self.list_audit_actions(limit=8)
        now = current_time_value()
        active_order_count = 0
        delivery_in_work = 0
        today_revenue = 0
        today_cancellations = 0
        overdue_deliveries = 0
        attention = []
        for order in all_orders:
            totals = summarize_saved_order_totals(order, recompute_zero_bonus=True)
            effective_status = self.resolve_effective_order_status(order, now)
            order["status"] = effective_status
            order["order_type_label"] = self.order_type_label(order.get("order_type"))
            is_cancelled = effective_status == "cancelled"
            is_active = effective_status not in {"served", "cancelled"}
            order["status_label"] = self.status_label(effective_status, order.get("order_type"))
            if is_active:
                active_order_count += 1
            if (order.get("order_type") or "").lower() == "delivery" and is_active:
                delivery_in_work += 1
                if self.is_delivery_overdue(order, now):
                    overdue_deliveries += 1
                    attention.append({"title": f"Просрочена доставка #{order['id']}", "href": url_for("admin.delivery")})
            if is_cancelled and start.isoformat(timespec="seconds") <= str(order.get("cancelled_at") or "") < end.isoformat(timespec="seconds"):
                today_cancellations += 1
            if start.isoformat(timespec="seconds") <= str(order.get("created_at") or "") < end.isoformat(timespec="seconds") and not is_cancelled:
                today_revenue += totals["payable_total"]
        nearest_bookings = []
        active_bookings = 0
        for booking in all_bookings:
            state = self.booking_state(booking, now)
            booking["state_label"] = "Активна" if state == "active" else "Прошла"
            if state == "active":
                active_bookings += 1
            booking_dt = self.booking_datetime(booking)
            if booking_dt and now <= booking_dt <= now + timedelta(hours=2):
                nearest_bookings.append(booking)
        return {
            "kpis": {
                "active_orders": active_order_count,
                "active_bookings": active_bookings,
                "delivery_in_work": delivery_in_work,
                "today_revenue": today_revenue,
                "today_cancellations": today_cancellations,
                "overdue_deliveries": overdue_deliveries,
            },
            "attention": attention[:5],
            "nearest_bookings": nearest_bookings[:8],
            "latest_actions": latest_actions,
            "today_orders": today_orders[:8],
        }

    def list_audit_actions(self, *, entity_type: str | None = None, entity_id: str | int | None = None, filters: dict | None = None, limit: int = 50, page: int = 1):
        filters = filters or {}
        normalized_page, normalized_per_page = _normalize_pagination(page, limit, default_per_page=limit, max_per_page=100)
        conditions = []
        params = []
        if entity_type:
            conditions.append("a.entity_type = %s")
            params.append(entity_type)
        if entity_id is not None:
            conditions.append("a.entity_id = %s")
            params.append(str(entity_id))
        admin_user_id = str(filters.get("admin_user_id") or "").strip()
        if admin_user_id:
            conditions.append("CAST(a.admin_user_id AS TEXT) = %s")
            params.append(admin_user_id)
        action_type = str(filters.get("action_type") or "").strip()
        if action_type:
            conditions.append("a.action_type = %s")
            params.append(action_type)
        entity_type_filter = str(filters.get("entity_type") or "").strip()
        if entity_type_filter:
            conditions.append("a.entity_type = %s")
            params.append(entity_type_filter)
        date_from = str(filters.get("date_from") or "").strip()
        if date_from:
            conditions.append("a.created_at::date >= %s::date")
            params.append(date_from)
        date_to = str(filters.get("date_to") or "").strip()
        if date_to:
            conditions.append("a.created_at::date <= %s::date")
            params.append(date_to)
        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        count_row = self._fetch_one(
            f"""
            SELECT COUNT(*) AS count
            FROM admin_actions a
            {where_sql}
            """,
            tuple(params),
        ) or {"count": 0}
        pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
        rows = self._fetch_all(
            f"""
            SELECT a.*, u.name AS admin_name
            FROM admin_actions a
            LEFT JOIN users u ON u.id = a.admin_user_id
            {where_sql}
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT {pagination["per_page"]} OFFSET {pagination["offset"]}
            """,
            tuple(params),
        )
        for row in rows:
            payload_text = row.get("payload_json") or "{}"
            try:
                row["payload"] = json.loads(payload_text)
            except json.JSONDecodeError:
                row["payload"] = {"raw": payload_text}
        if entity_type is not None or entity_id is not None:
            return rows
        return rows, pagination

    def audit_filter_options(self):
        if self._audit_filter_options_cache is not None:
            return self._audit_filter_options_cache
        admins = self._fetch_all(
            """
            SELECT DISTINCT u.id, u.name
            FROM admin_actions a
            LEFT JOIN users u ON u.id = a.admin_user_id
            WHERE a.admin_user_id IS NOT NULL
            ORDER BY u.name NULLS LAST, u.id
            """
        )
        actions = self._fetch_all("SELECT DISTINCT action_type FROM admin_actions ORDER BY action_type")
        entities = self._fetch_all("SELECT DISTINCT entity_type FROM admin_actions ORDER BY entity_type")
        self._audit_filter_options_cache = {"admins": admins, "actions": actions, "entities": entities}
        return self._audit_filter_options_cache

    def table_occupancy_for_date(self, booking_date: str):
        rows = self._fetch_all(
            """
            SELECT id, table_id, booking_time, name
            FROM bookings
            WHERE booking_date = %s::date
            ORDER BY booking_time
            """,
            (booking_date,),
        )
        occupancy = {table["id"]: [] for table in TABLES}
        for row in rows:
            occupancy.setdefault(row["table_id"], []).append(row)
        return occupancy

    def get_analytics(self, filters: dict):
        period = str(filters.get("period") or "7d")
        mode = str(filters.get("mode") or "all")
        days = {"today": 1, "7d": 7, "30d": 30, "month": 30}.get(period, 7)
        start = (datetime.now() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        params = [start.isoformat(timespec="seconds")]
        mode_sql = ""
        if mode in {"dine_in", "delivery"}:
            mode_sql = "AND order_type = %s"
            params.append(mode)
        payable_total_sql = """
            GREATEST(
                COALESCE(payable_total, COALESCE(items_total, 0) - COALESCE(points_applied, 0)),
                0
            )
        """
        bonus_earned_sql = f"""
            CASE
                WHEN bonus_earned IS NULL
                    OR (
                        COALESCE(bonus_earned, 0) <= 0
                        AND COALESCE(points_applied, 0) <= 0
                        AND {payable_total_sql} > 0
                    )
                THEN FLOOR({payable_total_sql} * 0.05)
                ELSE GREATEST(COALESCE(bonus_earned, 0), 0)
            END
        """
        aggregate_row = self._fetch_one(
            f"""
            SELECT
                COUNT(*) AS orders_count,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancellations,
                COALESCE(SUM(GREATEST(COALESCE(points_applied, 0), 0)), 0) AS points_applied,
                COALESCE(SUM({bonus_earned_sql}), 0) AS bonus_earned,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN {payable_total_sql} ELSE 0 END), 0) AS revenue,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'dine_in' THEN {payable_total_sql} ELSE 0 END), 0) AS dine_in_revenue,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' THEN {payable_total_sql} ELSE 0 END), 0) AS delivery_revenue
            FROM orders
            WHERE created_at >= %s
            {mode_sql}
            """,
            tuple(params),
        ) or {}
        daily_rows = self._fetch_all(
            f"""
            SELECT
                created_at::date::text AS label,
                COUNT(*) AS orders_count,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancellations,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN {payable_total_sql} ELSE 0 END), 0) AS revenue,
                COALESCE(SUM(CASE WHEN LOWER(COALESCE(order_type, 'dine_in')) = 'dine_in' THEN 1 ELSE 0 END), 0) AS dine_in_orders,
                COALESCE(SUM(CASE WHEN LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' THEN 1 ELSE 0 END), 0) AS delivery_orders
            FROM orders
            WHERE created_at >= %s
            {mode_sql}
            GROUP BY created_at::date
            ORDER BY created_at::date ASC
            """,
            tuple(params),
        )
        metrics = {
            "revenue": _safe_int(aggregate_row.get("revenue")),
            "orders_count": _safe_int(aggregate_row.get("orders_count")),
            "dine_in_revenue": _safe_int(aggregate_row.get("dine_in_revenue")),
            "delivery_revenue": _safe_int(aggregate_row.get("delivery_revenue")),
            "bookings_count": _safe_int(
                self._fetch_one("SELECT COUNT(*) AS count FROM bookings WHERE booking_date >= %s::date", (start.date().isoformat(),))["count"]
            ),
            "cancellations": _safe_int(aggregate_row.get("cancellations")),
            "points_applied": _safe_int(aggregate_row.get("points_applied")),
            "bonus_earned": _safe_int(aggregate_row.get("bonus_earned")),
        }
        revenue_by_day = OrderedDict()
        orders_by_day = OrderedDict()
        cancels_by_day = OrderedDict()
        channels_by_day = OrderedDict()
        split = {"dine_in": 0, "delivery": 0}
        for offset in range(days):
            label = (start + timedelta(days=offset)).date().isoformat()
            revenue_by_day[label] = 0
            orders_by_day[label] = 0
            cancels_by_day[label] = 0
            channels_by_day[label] = {"dine_in": 0, "delivery": 0}
        for row in daily_rows:
            label = str(row.get("label") or "").strip()
            if label not in revenue_by_day:
                continue
            orders_by_day[label] = _safe_int(row.get("orders_count"))
            cancels_by_day[label] = _safe_int(row.get("cancellations"))
            revenue_by_day[label] = _safe_int(row.get("revenue"))
            dine_in_orders = _safe_int(row.get("dine_in_orders"))
            delivery_orders = _safe_int(row.get("delivery_orders"))
            channels_by_day[label] = {"dine_in": dine_in_orders, "delivery": delivery_orders}
            split["dine_in"] += dine_in_orders
            split["delivery"] += delivery_orders
        metrics["average_check"] = int(metrics["revenue"] / metrics["orders_count"]) if metrics["orders_count"] else 0
        top_items = self._fetch_all(
            f"""
            SELECT
                oi.item_id,
                oi.name,
                SUM(oi.qty) AS qty_total,
                SUM(oi.qty * oi.price) AS revenue_total
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.created_at >= %s
              {mode_sql.replace('order_type', 'o.order_type')}
              AND LOWER(o.status) <> 'cancelled'
            GROUP BY oi.item_id, oi.name
            ORDER BY qty_total DESC, revenue_total DESC
            """,
            tuple(params),
        )
        menu_items = self.menu_content.load_menu_items_admin()
        sold_ids = {item["item_id"] for item in top_items}
        no_sales_items = [item for item in menu_items if item["id"] not in sold_ids][:8]
        return {
            "metrics": metrics,
            "period": period,
            "mode": mode,
            "charts": {
                "revenue_by_day": [{"label": key, "value": value} for key, value in revenue_by_day.items()],
                "orders_by_day": [{"label": key, "value": value} for key, value in orders_by_day.items()],
                "cancels_by_day": [{"label": key, "value": value} for key, value in cancels_by_day.items()],
                "channels_by_day": [
                    {"label": key, "dine_in": value.get("dine_in", 0), "delivery": value.get("delivery", 0)}
                    for key, value in channels_by_day.items()
                ],
                "split": [
                    {"label": "Зал", "value": split.get("dine_in", 0)},
                    {"label": "Доставка", "value": split.get("delivery", 0)},
                ],
                "top_qty": [{"label": item["name"], "value": _safe_int(item["qty_total"])} for item in top_items[:12]],
                "top_revenue": [{"label": item["name"], "value": _safe_int(item["revenue_total"])} for item in top_items[:12]],
            },
            "top_items": top_items,
            "no_sales_items": no_sales_items,
        }

    def list_menu_items(self, filters: dict, items: list[dict] | None = None):
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
        items = list(items) if items is not None else self.menu_content.load_promo_items(include_inactive=True)
        item_class = str(filters.get("class_name") or "").strip()
        if item_class:
            items = [item for item in items if item.get("class") == item_class]
        return items

    def get_content_scaffold(self):
        return {
            "todo_blocks": [
                "Hero banner and homepage text are still hardcoded in Jinja templates.",
                "No separate content store has been introduced in this phase.",
                "Promo-backed homepage blocks are managed in /admin/promo.",
            ]
        }

    def save_menu_item(self, *, form: dict, photo: FileStorage | None, admin_user_id: int):
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
        meta_path = target_dir / "item.txt"
        existing_meta = self.menu_content.parse_menu_meta(meta_path) if meta_path.exists() else {}
        payload = OrderedDict()
        payload["id"] = item_id
        payload["name"] = name
        payload["type"] = str(form.get("type") or "").strip()
        payload["price"] = _safe_int(form.get("price"), 0)
        payload["weight"] = str(form.get("weight") or "").strip()
        payload["lore"] = str(form.get("lore") or "").strip()
        payload["featured"] = "true" if _safe_bool(form.get("featured")) else "false"
        payload["popularity"] = _safe_int(form.get("popularity"), 0)
        payload["active"] = "true" if _safe_bool(form.get("active"), True) else "false"
        for key, value in existing_meta.items():
            if key not in payload:
                payload[key] = value
        meta_path.write_text(_meta_text(payload), encoding="utf-8")
        saved_photo = self._save_image(target_dir, photo)
        if existing:
            action_type = "menu_price_changed" if _safe_int(existing.get("price")) != payload["price"] else "menu_item_updated"
        else:
            action_type = "menu_item_created"
        if existing and payload["active"] == "false":
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
            parts = Path(existing["photo"]).parts
            target_dir = PROMO_ITEMS_PATH / parts[1] / parts[2]
        target_dir.mkdir(parents=True, exist_ok=True)
        if not existing:
            item_id = max([item.get("id", 0) for item in all_items] or [0]) + 1
        meta_path = target_dir / "item.txt"
        existing_meta = self.menu_content.parse_menu_meta(meta_path) if meta_path.exists() else {}
        payload = OrderedDict()
        payload["id"] = item_id
        payload["class"] = class_name
        if class_name == "akciya":
            payload["name"] = str(form.get("name") or "").strip()
            payload["lore"] = str(form.get("lore") or "").strip()
        else:
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
        saved_photo = self._save_image(target_dir, photo)
        action_type = "promo_created" if not existing else "promo_updated"
        if existing and payload["active"] == "false":
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

    def delete_promo_item(self, *, admin_user_id: int, class_name: str, item_id: int, reason: str):
        if not reason:
            raise ValueError("Укажите причину удаления.")
        items = self.menu_content.load_promo_items(include_inactive=True)
        item = next((entry for entry in items if entry.get("class") == class_name and entry.get("id") == int(item_id)), None)
        if item is None or not item.get("photo"):
            raise ValueError("Промо-элемент не найден.")
        parts = Path(item["photo"]).parts
        target_dir = PROMO_ITEMS_PATH / parts[1] / parts[2]
        if target_dir.exists():
            shutil.rmtree(target_dir)
        self.log_admin_action(
            admin_user_id=admin_user_id,
            action_type="promo_deleted",
            entity_type="promo_item",
            entity_id=item_id,
            reason=reason,
            payload={"class": class_name, "folder": target_dir.name},
        )
        self.invalidate_menu_cache()

    def _save_image(self, target_dir: Path, upload: FileStorage | None):
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
        stored_status = str((order or {}).get("status") or "").strip().lower()
        if stored_status == "cancelled":
            return "cancelled"

        order_type = str((order or {}).get("order_type") or "").strip().lower()
        timeline = self._build_runtime_timeline(order, now)

        if order_type == "delivery":
            rank_to_status = {1: "cooking", 2: "delivering", 3: "served"}
            status_to_rank = {
                "preparing": 1,
                "cooking": 1,
                "ready": 2,
                "delivering": 2,
                "served": 3,
            }
            timeline_to_rank = {
                "cooking": 1,
                "courier_sent": 2,
                "delivering": 2,
                "delivered": 3,
            }
            completed_rank = 3
        else:
            rank_to_status = {1: "preparing", 2: "cooking", 3: "ready", 4: "delivering", 5: "served"}
            status_to_rank = {
                "preparing": 1,
                "cooking": 2,
                "ready": 3,
                "delivering": 4,
                "served": 5,
            }
            timeline_to_rank = {
                "waiting": 1,
                "preparing": 2,
                "delivering": 4,
                "served": 5,
            }
            completed_rank = 5

        stored_rank = status_to_rank.get(stored_status, 0)
        derived_rank = completed_rank if timeline is None else timeline_to_rank.get(str(timeline.get("phase") or "").strip().lower(), 0)
        effective_rank = max(stored_rank, derived_rank)
        return rank_to_status.get(effective_rank, stored_status or rank_to_status[completed_rank])

    def is_delivery_overdue(self, order: dict, now: datetime | None = None):
        if (order.get("order_type") or "").lower() != "delivery":
            return False
        effective_status = self.resolve_effective_order_status(order, now)
        if effective_status in {"served", "cancelled"}:
            return False
        created_at = _parse_iso_datetime(order.get("created_at"))
        if created_at is None:
            return False
        eta_minutes = _safe_int(order.get("delivery_eta_minutes"), 20)
        return created_at + timedelta(minutes=eta_minutes) < (now or current_time_value())

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
