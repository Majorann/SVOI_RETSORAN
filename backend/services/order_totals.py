def calculate_items_total(items):
    total = 0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            price = int(item.get("price", 0) or 0)
            qty = int(item.get("qty", 0) or 0)
        except (TypeError, ValueError):
            continue
        if price < 0 or qty <= 0:
            continue
        total += price * qty
    return total


def calculate_order_totals(
    items,
    *,
    service_fee=0,
    points_balance=0,
    use_points=False,
    requested_points=None,
):
    items_total = calculate_items_total(items)
    service_fee = max(0, int(service_fee or 0))
    gross_total = items_total + service_fee
    points_balance = max(0, int(points_balance or 0))

    if requested_points is None:
        requested_points = gross_total if use_points else 0
    requested_points = max(0, int(requested_points or 0))

    points_applied = min(requested_points, points_balance, gross_total)
    payable_total = max(0, gross_total - points_applied)
    bonus_earned = int(payable_total * 0.05) if payable_total > 0 else 0
    return {
        "items_total": items_total,
        "service_fee": service_fee,
        "gross_total": gross_total,
        "points_applied": points_applied,
        "payable_total": payable_total,
        "bonus_earned": bonus_earned,
    }


def summarize_saved_order_totals(order, *, default_service_fee=0, recompute_zero_bonus=False):
    order = order if isinstance(order, dict) else {}
    items_total_raw = order.get("items_total")
    items_total = (
        calculate_items_total(order.get("items"))
        if items_total_raw in (None, "")
        else max(0, int(items_total_raw or 0))
    )

    order_type = str(order.get("order_type") or "").strip().lower()
    service_fee_raw = order.get("service_fee")
    if service_fee_raw in (None, ""):
        if order_type == "delivery":
            payable_total_raw = order.get("payable_total")
            if payable_total_raw in (None, ""):
                service_fee = max(0, int(default_service_fee or 0))
            else:
                service_fee = max(0, int(payable_total_raw or 0) - items_total)
        else:
            service_fee = max(0, int(default_service_fee or 0))
    else:
        service_fee = max(0, int(service_fee_raw or 0))

    points_applied = max(0, int(order.get("points_applied", 0) or 0))
    gross_total = items_total + service_fee
    payable_total_raw = order.get("payable_total")
    payable_total = (
        max(0, gross_total - points_applied)
        if payable_total_raw in (None, "")
        else max(0, int(payable_total_raw or 0))
    )

    bonus_raw = order.get("bonus_earned")
    bonus_missing = bonus_raw in (None, "")
    bonus_earned = 0 if bonus_missing else max(0, int(bonus_raw or 0))
    if bonus_missing or (
        recompute_zero_bonus and bonus_earned <= 0 and payable_total > 0 and points_applied <= 0
    ):
        bonus_earned = int(payable_total * 0.05)

    return {
        "items_total": items_total,
        "service_fee": service_fee,
        "gross_total": gross_total,
        "points_applied": points_applied,
        "payable_total": payable_total,
        "bonus_earned": bonus_earned,
    }
