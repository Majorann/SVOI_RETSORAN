from datetime import datetime
from typing import Any

from config import TABLES
from services.business_logic import current_time_value
from services.order_status import read_effective_status_value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _mask_card(card: dict) -> dict:
    return {
        "brand": card.get("brand") or "MIR",
        "last4": card.get("last4") or "0000",
        "active": bool(card.get("active")),
        "holder": card.get("holder") or "",
        "expiry": card.get("expiry") or "",
    }


def list_bookings(service, filters: dict):
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
    rows = service._fetch_all(
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
        row["state"] = service.booking_state(row, now)
        row["state_label"] = {"active": "Активна", "past": "Прошла"}.get(row["state"], "Активна")
        row["related_orders_count"] = _safe_int(row.get("related_orders_count"))
    state_filter = str(filters.get("state") or "").strip()
    if state_filter:
        rows = [row for row in rows if row["state"] == state_filter]
    return rows


def get_booking_detail(service, booking_id: int):
    row = service._fetch_one(
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
    row["state"] = service.booking_state(row, datetime.now())
    row["related_orders"] = service._fetch_all(
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
        effective_status = service.resolve_effective_order_status(order, now)
        order["status"] = effective_status
        order["status_label"] = service.status_label(effective_status, order.get("order_type"))
        order["order_type_label"] = service.order_type_label(order.get("order_type"))
    row["occupancy"] = service.table_occupancy_for_date(str(row["booking_date"]))
    row["audit_actions"] = service.list_audit_actions(entity_type="booking", entity_id=row["id"], limit=20)
    return row


def list_users(service, search: str = "", *, page: int = 1, per_page: int = 25):
    normalized_page, normalized_per_page = _normalize_pagination(page, per_page)
    params = ()
    where_sql = ""
    if search:
        like = f"%{search}%"
        where_sql = "WHERE u.name ILIKE %s OR u.phone ILIKE %s"
        params = (like, like)
    count_row = service._fetch_one(
        f"""
        SELECT COUNT(*) AS count
        FROM users u
        {where_sql}
        """,
        params,
    ) or {"count": 0}
    pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
    rows = service._fetch_all(
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


def get_user_detail(service, user_id: int):
    user = service._fetch_one(
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
        for card in service._fetch_all(
            """
            SELECT brand, last4, active, holder, expiry, created_at
            FROM user_cards
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (int(user_id),),
        )
    ]
    service._refresh_persisted_order_fields(user_id=int(user_id), active_only=True)
    user["orders"] = service._fetch_all(
        """
        SELECT id, order_type, status, effective_status, is_delivery_overdue, created_at, payable_total
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (int(user_id),),
    )
    for order in user["orders"]:
        effective_status = read_effective_status_value(order)
        order["status"] = effective_status
        order["status_label"] = service.status_label(effective_status, order.get("order_type"))
        order["order_type_label"] = service.order_type_label(order.get("order_type"))
    user["bookings"] = service._fetch_all(
        """
        SELECT id, table_id, booking_date, booking_time, created_at
        FROM bookings
        WHERE user_id = %s
        ORDER BY booking_date DESC, booking_time DESC
        LIMIT 10
        """,
        (int(user_id),),
    )
    user["audit_actions"] = service.list_audit_actions(entity_type="user", entity_id=user["id"], limit=20)
    user["balance_actions"] = [action for action in user["audit_actions"] if action.get("action_type") == "user_bonus_adjusted"]
    return user


def table_occupancy_for_date(service, booking_date: str):
    rows = service._fetch_all(
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
