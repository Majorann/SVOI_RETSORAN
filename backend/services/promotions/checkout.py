from __future__ import annotations

from services.order_totals import calculate_order_totals

from .engine import apply_promotions_to_order


def build_priced_order_preview(
    *,
    items: list[dict],
    service_fee: int = 0,
    points_balance: int = 0,
    use_points: bool = False,
    requested_points: int | None = None,
    user_id: int | None = None,
    load_orders_fn,
    load_promo_application_counts_fn=None,
    promo_items: list[dict],
    menu_items: list[dict],
):
    prior_application_counts = None
    if load_promo_application_counts_fn is not None and user_id:
        prior_application_counts = load_promo_application_counts_fn(user_id=user_id)
    promo_result = apply_promotions_to_order(
        order={"items": items},
        promo_items=promo_items,
        menu_items=menu_items,
        prior_orders=load_orders_fn(),
        prior_application_counts=prior_application_counts,
        user_id=user_id,
    )
    discount_total = int((promo_result.get("best_discount") or {}).get("amount") or 0)
    totals = calculate_order_totals(
        promo_result["items"],
        service_fee=service_fee,
        discount_total=discount_total,
        points_balance=points_balance,
        use_points=use_points,
        requested_points=requested_points,
    )
    return {
        "items": promo_result["items"],
        "totals": totals,
        "discount_total": discount_total,
        "discount": promo_result.get("best_discount"),
        "promo_points": int(promo_result.get("awarded_points") or 0),
        "promo_notifications": list(promo_result.get("notifications") or []),
        "promotions_applied": list(promo_result.get("applied_promotions") or []),
    }
