from datetime import datetime, timedelta
from typing import Any

from services.order_status import read_delivery_overdue_value, read_effective_status_value
from services.order_totals import summarize_saved_order_totals


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _today_bounds():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


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


def build_order_filters(filters: dict, *, delivery_only: bool = False):
    conditions = []
    params = []
    if delivery_only:
        conditions.append("LOWER(COALESCE(o.order_type, 'dine_in')) = 'delivery'")
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
        conditions.append("LOWER(COALESCE(o.effective_status, o.status, '')) = %s")
        params.append(status.lower())
    order_type = str(filters.get("order_type") or "").strip()
    if order_type and not delivery_only:
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
        conditions.append("LOWER(COALESCE(o.effective_status, o.status, '')) NOT IN ('served', 'cancelled')")
    elif preset == "cancelled":
        conditions.append("LOWER(COALESCE(o.effective_status, o.status, '')) = 'cancelled'")
    elif preset == "served" and delivery_only:
        conditions.append("LOWER(COALESCE(o.effective_status, o.status, '')) = 'served'")
    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where_sql, tuple(params)


def normalize_order_rows(service, rows: list[dict], *, force_delivery: bool = False):
    normalized_rows = []
    for row in rows:
        totals = summarize_saved_order_totals(row, recompute_zero_bonus=True)
        effective_status = read_effective_status_value(row)
        row["status"] = effective_status
        row["totals"] = totals
        row["is_delivery"] = force_delivery or (row.get("order_type") or "").lower() == "delivery"
        row["order_type_label"] = service.order_type_label(row.get("order_type"))
        row["table_label"] = "—" if row["is_delivery"] else (f"Стол №{row.get('booking_table_id')}" if row.get("booking_table_id") else "—")
        row["status_label"] = service.status_label(effective_status, row.get("order_type"))
        row["delivery_overdue"] = read_delivery_overdue_value(row)
        normalized_rows.append(row)
    return normalized_rows


def query_orders_page(service, filters: dict, *, page: int | None = None, per_page: int | None = None, delivery_only: bool = False):
    service._refresh_persisted_order_fields(active_only=True)
    where_sql, params = build_order_filters(filters, delivery_only=delivery_only)
    pagination = None
    limit_sql = ""
    if page is not None and per_page is not None:
        normalized_page, normalized_per_page = _normalize_pagination(page, per_page)
        count_row = service._fetch_one(
            f"""
            SELECT COUNT(DISTINCT o.id) AS count
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            {where_sql}
            """,
            params,
        ) or {"count": 0}
        pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
        limit_sql = f"LIMIT {pagination['per_page']} OFFSET {pagination['offset']}"
    rows = service._fetch_all(
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
        {limit_sql}
        """,
        params,
    )
    return normalize_order_rows(service, rows, force_delivery=delivery_only), pagination


def get_order_detail(service, order_id: int):
    service._refresh_persisted_order_fields(order_ids=[int(order_id)])
    row = service._fetch_one(
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
    effective_status = read_effective_status_value(row)
    row["status"] = effective_status
    row["order_type_label"] = service.order_type_label(row.get("order_type"))
    row["items"] = service._fetch_all(
        """
        SELECT position, item_id, name, price, qty, photo
        FROM order_items
        WHERE order_id = %s
        ORDER BY position
        """,
        (int(order_id),),
    )
    row["totals"] = summarize_saved_order_totals(row, recompute_zero_bonus=True)
    row["status_label"] = service.status_label(effective_status, row.get("order_type"))
    row["delivery_overdue"] = read_delivery_overdue_value(row)
    row["related_booking"] = None
    if row.get("booking_date") and row.get("booking_time"):
        row["related_booking"] = service._fetch_one(
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
    row["audit_actions"] = service.list_audit_actions(entity_type="order", entity_id=row["id"], limit=20)
    return row
