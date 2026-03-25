from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from flask import url_for

from services.order_status import read_delivery_overdue_value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _today_bounds(now: datetime | None = None):
    now = now or datetime.now()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


def get_dashboard_data(service, *, now: datetime | None = None):
    service._refresh_persisted_order_fields(active_only=True)
    now = now or datetime.now()
    start, end = _today_bounds(now)
    booking_now = now
    payable_total_sql = """
        GREATEST(
            COALESCE(payable_total, COALESCE(items_total, 0) - COALESCE(points_applied, 0)),
            0
        )
    """
    aggregate_row = service._fetch_one(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN LOWER(COALESCE(effective_status, status, '')) NOT IN ('served', 'cancelled') THEN 1 ELSE 0 END), 0) AS active_orders,
            COALESCE(SUM(CASE WHEN LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' AND LOWER(COALESCE(effective_status, status, '')) NOT IN ('served', 'cancelled') THEN 1 ELSE 0 END), 0) AS delivery_in_work,
            COALESCE(SUM(CASE WHEN created_at >= %s AND created_at < %s AND LOWER(COALESCE(effective_status, status, '')) <> 'cancelled' THEN {payable_total_sql} ELSE 0 END), 0) AS today_revenue,
            COALESCE(SUM(CASE WHEN cancelled_at >= %s AND cancelled_at < %s THEN 1 ELSE 0 END), 0) AS today_cancellations
        FROM orders
        """,
        (
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
        ),
    ) or {}
    active_bookings_row = service._fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM bookings
        WHERE (booking_date + booking_time) >= %s
        """,
        (booking_now,),
    ) or {"count": 0}
    overdue_rows = service._fetch_all(
        """
        SELECT id, created_at, delivery_eta_minutes, order_type, status, effective_status, is_delivery_overdue
        FROM orders
        WHERE LOWER(COALESCE(order_type, 'dine_in')) = 'delivery'
          AND LOWER(COALESCE(effective_status, status, '')) NOT IN ('served', 'cancelled')
        ORDER BY created_at ASC, id ASC
        LIMIT 100
        """
    )
    today_orders = service._fetch_all(
        """
        SELECT *
        FROM orders
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at DESC, id DESC
        LIMIT 8
        """,
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
    )
    nearest_bookings = service._fetch_all(
        """
        SELECT b.id, b.user_id, b.table_id, b.booking_date, b.booking_time, b.name, b.created_at, u.phone AS user_phone
        FROM bookings b
        LEFT JOIN users u ON u.id = b.user_id
        WHERE (b.booking_date + b.booking_time) >= %s
          AND (b.booking_date + b.booking_time) <= %s
        ORDER BY b.booking_date ASC, b.booking_time ASC, b.id ASC
        LIMIT 8
        """,
        (booking_now, booking_now + timedelta(hours=2)),
    )
    latest_actions = service.list_audit_actions(limit=8)
    attention = []
    overdue_deliveries = 0
    for order in overdue_rows:
        if read_delivery_overdue_value(order):
            overdue_deliveries += 1
            if len(attention) < 5:
                attention.append({"title": f"Просрочена доставка #{order['id']}", "href": url_for("admin.delivery")})
    for booking in nearest_bookings:
        booking["state_label"] = "Активна" if service.booking_state(booking, booking_now) == "active" else "Прошла"
    today_orders = service._normalize_order_rows(today_orders)
    return {
        "kpis": {
            "active_orders": _safe_int(aggregate_row.get("active_orders")),
            "active_bookings": _safe_int(active_bookings_row.get("count")),
            "delivery_in_work": _safe_int(aggregate_row.get("delivery_in_work")),
            "today_revenue": _safe_int(aggregate_row.get("today_revenue")),
            "today_cancellations": _safe_int(aggregate_row.get("today_cancellations")),
            "overdue_deliveries": overdue_deliveries,
        },
        "attention": attention,
        "nearest_bookings": nearest_bookings,
        "latest_actions": latest_actions,
        "today_orders": today_orders,
    }


def get_analytics(service, filters: dict, *, now: datetime | None = None):
    now = now or datetime.now()
    period = str(filters.get("period") or "7d")
    mode = str(filters.get("mode") or "all")
    days = {"today": 1, "7d": 7, "30d": 30, "month": 30}.get(period, 7)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
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
    aggregate_row = service._fetch_one(
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
    daily_rows = service._fetch_all(
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
            service._fetch_one("SELECT COUNT(*) AS count FROM bookings WHERE booking_date >= %s::date", (start.date().isoformat(),))["count"]
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
    top_items = service._fetch_all(
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
    menu_items = service.menu_content.load_menu_items_admin()
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
