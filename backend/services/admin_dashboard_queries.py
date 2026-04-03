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
    def build_bounds(now_value: datetime, selected_period: str):
        selected_days = {"today": 1, "7d": 7, "30d": 30, "month": 30}.get(selected_period, 7)
        period_start = (now_value - timedelta(days=selected_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now_value
        previous_period_end = period_start
        previous_period_start = previous_period_end - (period_end - period_start)
        return selected_days, period_start, period_end, previous_period_start, previous_period_end

    def format_int(value: int) -> str:
        return f"{_safe_int(value):,}".replace(",", " ")

    def format_currency(value: int) -> str:
        return f"{format_int(value)} ₽"

    def format_percent(value: float | int, digits: int = 0) -> str:
        if digits <= 0:
            normalized = int(round(float(value or 0)))
            return f"{normalized}%"
        return f"{float(value or 0):.{digits}f}%".replace(".", ",")

    def short_date(value: datetime) -> str:
        return value.strftime("%d.%m")

    def long_date(value: datetime) -> str:
        return value.strftime("%d.%m.%Y")

    def make_period_label(range_start: datetime, range_end: datetime) -> str:
        if range_start.date() == range_end.date():
            return long_date(range_end)
        return f"{short_date(range_start)} - {long_date(range_end)}"

    def comparison_payload(current: int, previous: int, *, inverse: bool = False):
        current_value = _safe_int(current)
        previous_value = _safe_int(previous)
        delta = current_value - previous_value
        if previous_value > 0:
            delta_pct = round((delta / previous_value) * 100)
            text = f"{delta_pct:+d}% к предыдущему периоду"
        elif current_value == 0:
            delta_pct = 0
            text = "Без изменений к предыдущему периоду"
        else:
            delta_pct = None
            text = "Нет базы для сравнения"
        direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
        tone = "warning" if inverse and direction == "up" else "success" if direction == "up" else "danger" if direction == "down" else "neutral"
        if inverse and direction == "down":
            tone = "success"
        return {
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "delta_pct": delta_pct,
            "direction": direction,
            "tone": tone,
            "text": text,
        }

    def aggregate_orders(range_start: datetime, range_end: datetime):
        params = [range_start.isoformat(timespec="seconds"), range_end.isoformat(timespec="seconds")]
        mode_sql = ""
        if mode in {"dine_in", "delivery"}:
            mode_sql = "AND order_type = %s"
            params.append(mode)
        aggregate = service._fetch_one(
            f"""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN 1 ELSE 0 END), 0) AS orders_count,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancellations,
                COALESCE(SUM(GREATEST(COALESCE(points_applied, 0), 0)), 0) AS points_applied,
                COALESCE(SUM({bonus_earned_sql}), 0) AS bonus_earned,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN {payable_total_sql} ELSE 0 END), 0) AS revenue,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'dine_in' THEN 1 ELSE 0 END), 0) AS dine_in_orders,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' THEN 1 ELSE 0 END), 0) AS delivery_orders,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'dine_in' THEN {payable_total_sql} ELSE 0 END), 0) AS dine_in_revenue,
                COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' THEN {payable_total_sql} ELSE 0 END), 0) AS delivery_revenue
            FROM orders
            WHERE created_at >= %s
              AND created_at < %s
              {mode_sql}
            """,
            tuple(params),
        ) or {}
        return {key: _safe_int(value) for key, value in aggregate.items()}

    def booking_count(range_start: datetime, range_end: datetime) -> int:
        row = service._fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE booking_date >= %s::date
              AND booking_date <= %s::date
            """,
            (range_start.date().isoformat(), range_end.date().isoformat()),
        ) or {"count": 0}
        return _safe_int(row.get("count"))

    def build_kpi(key: str, label: str, current_value: int, previous_value: int, *, formatter, inverse: bool = False, hint: str = "", accent: str = "default"):
        comparison = comparison_payload(current_value, previous_value, inverse=inverse)
        return {
            "key": key,
            "label": label,
            "value": _safe_int(current_value),
            "display_value": formatter(current_value),
            "comparison": comparison,
            "hint": hint,
            "accent": accent,
        }

    def build_ranked_items(items: list[dict], value_key: str, *, suffix: str, max_items: int = 6):
        sliced = items[:max_items]
        max_value = max([_safe_int(item.get(value_key)) for item in sliced] or [1])
        ranked = []
        for index, item in enumerate(sliced, start=1):
            value = _safe_int(item.get(value_key))
            ranked.append(
                {
                    "id": _safe_int(item.get("id")),
                    "rank": index,
                    "name": item.get("name") or "Без названия",
                    "category": item.get("category") or "Без категории",
                    "value": value,
                    "display_value": f"{format_int(value)}{suffix}",
                    "bar": max(12, round((value / max_value) * 100)) if max_value else 12,
                    "meta": item.get("meta") or "",
                }
            )
        return ranked

    def build_insights(current_metrics: dict, previous_metrics: dict, channel_cards: list[dict], unsold_count: int, weak_count: int):
        insights = []
        revenue_compare = comparison_payload(current_metrics["revenue"], previous_metrics["revenue"])
        insights.append(
            {
                "tone": revenue_compare["tone"],
                "title": "Выручка",
                "text": revenue_compare["text"] if revenue_compare["delta_pct"] is not None else "Недостаточно истории для процентного сравнения",
                "meta": f"Сейчас {format_currency(current_metrics['revenue'])}",
            }
        )
        best_channel = max(channel_cards, key=lambda item: item["revenue"], default=None)
        if best_channel and best_channel["revenue"] > 0:
            insights.append(
                {
                    "tone": "neutral",
                    "title": "Основной канал",
                    "text": f"{best_channel['label']} даёт {format_percent(best_channel['revenue_share'], 0)} выручки периода.",
                    "meta": f"{best_channel['display_revenue']} · {best_channel['display_orders']}",
                }
            )
        if len(channel_cards) >= 2 and channel_cards[0]["orders"] > 0 and channel_cards[1]["orders"] > 0:
            higher = max(channel_cards, key=lambda item: item["average_check"])
            lower = min(channel_cards, key=lambda item: item["average_check"])
            if higher["average_check"] != lower["average_check"]:
                insights.append(
                    {
                        "tone": "neutral",
                        "title": "Средний чек",
                        "text": f"{lower['label']} отстаёт от {higher['label']} по среднему чеку.",
                        "meta": f"{lower['display_average_check']} против {higher['display_average_check']}",
                    }
                )
        cancel_rate = (current_metrics["cancellations"] / current_metrics["total_orders"] * 100) if current_metrics["total_orders"] else 0
        previous_cancel_rate = (previous_metrics["cancellations"] / previous_metrics["total_orders"] * 100) if previous_metrics["total_orders"] else 0
        cancel_tone = "warning" if cancel_rate > previous_cancel_rate or cancel_rate >= 5 else "success"
        insights.append(
            {
                "tone": cancel_tone,
                "title": "Отмены",
                "text": f"{current_metrics['cancellations']} за период, доля {format_percent(cancel_rate, 1)}.",
                "meta": f"Прошлый период: {previous_metrics['cancellations']} · {format_percent(previous_cancel_rate, 1)}",
            }
        )
        insights.append(
            {
                "tone": "warning" if unsold_count else "success",
                "title": "Ассортимент",
                "text": f"{unsold_count} блюд без продаж и {weak_count} слабых позиций по выручке.",
                "meta": "Используйте блок проблемных позиций ниже для ревизии меню.",
            }
        )
        return insights

    now = now or datetime.now()
    period = str(filters.get("period") or "7d")
    mode = str(filters.get("mode") or "all")
    days, start, end, previous_start, previous_end = build_bounds(now, period)
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
    current_order_metrics = aggregate_orders(start, end)
    previous_order_metrics = aggregate_orders(previous_start, previous_end)
    current_booking_count = booking_count(start, end)
    previous_booking_count = booking_count(previous_start, previous_end)
    current_metrics = {
        "revenue": current_order_metrics["revenue"],
        "orders_count": current_order_metrics["orders_count"],
        "total_orders": current_order_metrics["total_orders"],
        "bookings_count": current_booking_count,
        "cancellations": current_order_metrics["cancellations"],
        "points_applied": current_order_metrics["points_applied"],
        "bonus_earned": current_order_metrics["bonus_earned"],
        "average_check": int(current_order_metrics["revenue"] / current_order_metrics["orders_count"]) if current_order_metrics["orders_count"] else 0,
        "dine_in_orders": current_order_metrics["dine_in_orders"],
        "delivery_orders": current_order_metrics["delivery_orders"],
        "dine_in_revenue": current_order_metrics["dine_in_revenue"],
        "delivery_revenue": current_order_metrics["delivery_revenue"],
    }
    previous_metrics = {
        "revenue": previous_order_metrics["revenue"],
        "orders_count": previous_order_metrics["orders_count"],
        "total_orders": previous_order_metrics["total_orders"],
        "bookings_count": previous_booking_count,
        "cancellations": previous_order_metrics["cancellations"],
        "points_applied": previous_order_metrics["points_applied"],
        "bonus_earned": previous_order_metrics["bonus_earned"],
        "average_check": int(previous_order_metrics["revenue"] / previous_order_metrics["orders_count"]) if previous_order_metrics["orders_count"] else 0,
        "dine_in_orders": previous_order_metrics["dine_in_orders"],
        "delivery_orders": previous_order_metrics["delivery_orders"],
        "dine_in_revenue": previous_order_metrics["dine_in_revenue"],
        "delivery_revenue": previous_order_metrics["delivery_revenue"],
    }
    daily_params = [start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")]
    mode_sql = ""
    aliased_mode_sql = ""
    if mode in {"dine_in", "delivery"}:
        mode_sql = "AND order_type = %s"
        aliased_mode_sql = "AND o.order_type = %s"
        daily_params.append(mode)
    daily_rows = service._fetch_all(
        f"""
        SELECT
            created_at::date::text AS label,
            COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN 1 ELSE 0 END), 0) AS orders_count,
            COALESCE(SUM(CASE WHEN LOWER(status) = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancellations,
            COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' THEN {payable_total_sql} ELSE 0 END), 0) AS revenue,
            COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'dine_in' THEN 1 ELSE 0 END), 0) AS dine_in_orders,
            COALESCE(SUM(CASE WHEN LOWER(status) <> 'cancelled' AND LOWER(COALESCE(order_type, 'dine_in')) = 'delivery' THEN 1 ELSE 0 END), 0) AS delivery_orders
        FROM orders
        WHERE created_at >= %s
          AND created_at < %s
          {mode_sql}
        GROUP BY created_at::date
        ORDER BY created_at::date ASC
        """,
        tuple(daily_params),
    )
    revenue_by_day = OrderedDict()
    orders_by_day = OrderedDict()
    average_check_by_day = OrderedDict()
    cancels_by_day = OrderedDict()
    channels_by_day = OrderedDict()
    split = {"dine_in": 0, "delivery": 0}
    for offset in range(days):
        label = (start + timedelta(days=offset)).date().isoformat()
        revenue_by_day[label] = 0
        orders_by_day[label] = 0
        average_check_by_day[label] = 0
        cancels_by_day[label] = 0
        channels_by_day[label] = {"dine_in": 0, "delivery": 0}
    for row in daily_rows:
        label = str(row.get("label") or "").strip()
        if label not in revenue_by_day:
            continue
        revenue_value = _safe_int(row.get("revenue"))
        orders_value = _safe_int(row.get("orders_count"))
        dine_in_orders = _safe_int(row.get("dine_in_orders"))
        delivery_orders = _safe_int(row.get("delivery_orders"))
        revenue_by_day[label] = revenue_value
        orders_by_day[label] = orders_value
        average_check_by_day[label] = int(revenue_value / orders_value) if orders_value else 0
        cancels_by_day[label] = _safe_int(row.get("cancellations"))
        channels_by_day[label] = {"dine_in": dine_in_orders, "delivery": delivery_orders}
        split["dine_in"] += dine_in_orders
        split["delivery"] += delivery_orders
    product_params = [start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")]
    if mode in {"dine_in", "delivery"}:
        product_params.append(mode)
    sold_rows = service._fetch_all(
        f"""
        SELECT
            oi.item_id,
            MAX(oi.name) AS name,
            COALESCE(SUM(oi.qty), 0) AS qty_total,
            COALESCE(SUM(oi.qty * oi.price), 0) AS revenue_total,
            COALESCE(ROUND(AVG(oi.price)), 0) AS average_price,
            MAX(o.created_at) AS last_sold_at
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.created_at >= %s
          AND o.created_at < %s
          {aliased_mode_sql}
          AND LOWER(o.status) <> 'cancelled'
        GROUP BY oi.item_id
        ORDER BY revenue_total DESC, qty_total DESC, name ASC
        """,
        tuple(product_params),
    )
    last_sale_params = []
    if mode in {"dine_in", "delivery"}:
        last_sale_params.append(mode)
    last_sale_rows = service._fetch_all(
        f"""
        SELECT
            oi.item_id,
            MAX(o.created_at) AS last_sold_at
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE LOWER(o.status) <> 'cancelled'
          {aliased_mode_sql}
        GROUP BY oi.item_id
        """,
        tuple(last_sale_params),
    )
    last_sale_map = {int(row["item_id"]): row.get("last_sold_at") for row in last_sale_rows if row.get("item_id") is not None}
    menu_items = service.menu_content.load_menu_items_admin()
    menu_index = {int(item["id"]): item for item in menu_items if item.get("id") is not None}
    sales_index = {}
    for row in sold_rows:
        item_id = _safe_int(row.get("item_id"))
        menu_item = menu_index.get(item_id, {})
        sales_index[item_id] = {
            "id": item_id,
            "name": row.get("name") or menu_item.get("name") or "Без названия",
            "category": menu_item.get("type") or "Без категории",
            "qty_total": _safe_int(row.get("qty_total")),
            "revenue_total": _safe_int(row.get("revenue_total")),
            "average_price": _safe_int(row.get("average_price")) or _safe_int(menu_item.get("price")),
            "last_sold_at": row.get("last_sold_at"),
        }
    full_items = []
    total_revenue = max(current_metrics["revenue"], 1)
    for menu_item in menu_items:
        item_id = _safe_int(menu_item.get("id"))
        sold_item = sales_index.get(item_id)
        qty_total = _safe_int(sold_item.get("qty_total") if sold_item else 0)
        revenue_total = _safe_int(sold_item.get("revenue_total") if sold_item else 0)
        average_price = _safe_int(sold_item.get("average_price") if sold_item else menu_item.get("price"))
        last_sold_at = last_sale_map.get(item_id)
        full_items.append(
            {
                "id": item_id,
                "name": menu_item.get("name") or "Без названия",
                "category": menu_item.get("type") or "Без категории",
                "qty_total": qty_total,
                "revenue_total": revenue_total,
                "average_price": average_price,
                "share_revenue": round((revenue_total / total_revenue) * 100, 1) if current_metrics["revenue"] else 0,
                "last_sold_at": last_sold_at,
                "last_sold_label": long_date(last_sold_at) if isinstance(last_sold_at, datetime) else "Нет данных",
                "price": _safe_int(menu_item.get("price")),
                "active": bool(menu_item.get("active", True)),
            }
        )
    full_items.sort(key=lambda item: (-item["revenue_total"], -item["qty_total"], item["name"]))
    no_sales_items = [item for item in full_items if item["qty_total"] == 0]
    weak_items = [item for item in sorted(full_items, key=lambda item: (item["qty_total"] == 0, item["revenue_total"], item["qty_total"], item["name"])) if item["qty_total"] > 0][:5]
    top_qty_items = [item for item in sorted(full_items, key=lambda item: (-item["qty_total"], -item["revenue_total"], item["name"])) if item["qty_total"] > 0]
    top_revenue_items = [item for item in sorted(full_items, key=lambda item: (-item["revenue_total"], -item["qty_total"], item["name"])) if item["revenue_total"] > 0]
    channel_cards = []
    total_channel_orders = max(current_metrics["dine_in_orders"] + current_metrics["delivery_orders"], 1)
    total_channel_revenue = max(current_metrics["dine_in_revenue"] + current_metrics["delivery_revenue"], 1)
    for channel_key, channel_label in (("dine_in", "Зал"), ("delivery", "Доставка")):
        orders_value = current_metrics[f"{channel_key}_orders"]
        revenue_value = current_metrics[f"{channel_key}_revenue"]
        average_check = int(revenue_value / orders_value) if orders_value else 0
        channel_cards.append(
            {
                "key": channel_key,
                "label": channel_label,
                "orders": orders_value,
                "revenue": revenue_value,
                "average_check": average_check,
                "orders_share": round((orders_value / total_channel_orders) * 100, 1) if total_channel_orders else 0,
                "revenue_share": round((revenue_value / total_channel_revenue) * 100, 1) if total_channel_revenue else 0,
                "display_orders": f"{format_int(orders_value)} заказов",
                "display_revenue": format_currency(revenue_value),
                "display_average_check": format_currency(average_check),
            }
        )
    insights = build_insights(current_metrics, previous_metrics, channel_cards, len(no_sales_items), len(weak_items))
    cancellation_rate = (current_metrics["cancellations"] / current_metrics["total_orders"] * 100) if current_metrics["total_orders"] else 0
    previous_cancellation_rate = (previous_metrics["cancellations"] / previous_metrics["total_orders"] * 100) if previous_metrics["total_orders"] else 0
    kpis = [
        build_kpi("revenue", "Выручка", current_metrics["revenue"], previous_metrics["revenue"], formatter=format_currency, hint="Без отменённых заказов", accent="primary"),
        build_kpi("orders", "Заказы", current_metrics["orders_count"], previous_metrics["orders_count"], formatter=format_int, hint="Только неотменённые", accent="secondary"),
        build_kpi("average_check", "Средний чек", current_metrics["average_check"], previous_metrics["average_check"], formatter=format_currency, hint="Выручка / оплаченные заказы", accent="secondary"),
        build_kpi("cancellations", "Отмены", current_metrics["cancellations"], previous_metrics["cancellations"], formatter=format_int, inverse=True, hint=f"Доля {format_percent(cancellation_rate, 1)}", accent="warning"),
        build_kpi("bookings", "Брони", current_metrics["bookings_count"], previous_metrics["bookings_count"], formatter=format_int, hint="По дате бронирования", accent="secondary"),
        {
            "key": "loyalty",
            "label": "Баллы / бонусы",
            "value": current_metrics["points_applied"] + current_metrics["bonus_earned"],
            "display_value": f"{format_int(current_metrics['points_applied'])} / {format_int(current_metrics['bonus_earned'])}",
            "comparison": comparison_payload(
                current_metrics["points_applied"] + current_metrics["bonus_earned"],
                previous_metrics["points_applied"] + previous_metrics["bonus_earned"],
            ),
            "hint": "Списано / начислено за период",
            "accent": "secondary",
        },
    ]
    return {
        "metrics": current_metrics,
        "period": period,
        "mode": mode,
        "range_label": make_period_label(start, end),
        "previous_range_label": make_period_label(previous_start, previous_end),
        "kpis": kpis,
        "insights": insights,
        "cancellation_summary": {
            "count": current_metrics["cancellations"],
            "previous_count": previous_metrics["cancellations"],
            "rate": round(cancellation_rate, 1),
            "previous_rate": round(previous_cancellation_rate, 1),
            "comparison": comparison_payload(current_metrics["cancellations"], previous_metrics["cancellations"], inverse=True),
        },
        "charts": {
            "trend": {
                "revenue": [{"label": key, "value": value} for key, value in revenue_by_day.items()],
                "orders": [{"label": key, "value": value} for key, value in orders_by_day.items()],
                "average_check": [{"label": key, "value": value} for key, value in average_check_by_day.items()],
            },
            "cancels_by_day": [{"label": key, "value": value} for key, value in cancels_by_day.items()],
            "channels_by_day": [
                {"label": key, "dine_in": value.get("dine_in", 0), "delivery": value.get("delivery", 0)}
                for key, value in channels_by_day.items()
            ],
            "split": [
                {"label": "Зал", "value": split.get("dine_in", 0)},
                {"label": "Доставка", "value": split.get("delivery", 0)},
            ],
        },
        "channel_cards": channel_cards,
        "top_qty_items": build_ranked_items(top_qty_items, "qty_total", suffix=" шт."),
        "top_revenue_items": build_ranked_items(top_revenue_items, "revenue_total", suffix=" ₽"),
        "weak_items": weak_items,
        "full_items": full_items,
        "no_sales_items": no_sales_items[:8],
    }
