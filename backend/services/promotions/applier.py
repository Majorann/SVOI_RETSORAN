from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from .ast import MetricRef, PromotionDefinition
from .evaluator import order_user_items_total, resolve_metric_value


@dataclass
class PromotionApplicationState:
    order: dict
    awarded_points: int = 0
    notifications: list[str] = field(default_factory=list)
    best_discount: dict | None = None


def apply_reward(
    definition: PromotionDefinition,
    order: dict,
    *,
    applied_count: int,
    state: PromotionApplicationState | None = None,
) -> PromotionApplicationState:
    if state is None:
        state = PromotionApplicationState(order=deepcopy(order if isinstance(order, dict) else {"items": []}))
    if applied_count <= 0:
        return state

    reward = definition.reward
    if reward.kind == "POINTS":
        state.awarded_points += int(reward.amount or 0) * applied_count
    elif reward.kind == "GIFT":
        _apply_gift(definition, state.order, reward.item_id, reward.qty, applied_count)
    elif reward.kind in {"DISCOUNT_PERCENT", "DISCOUNT_RUB", "CHEAPEST_FREE_FROM_GROUP"}:
        candidate = _build_discount_candidate(definition, state.order, applied_count)
        if candidate is not None and (
            state.best_discount is None or candidate["priority"] > state.best_discount["priority"]
        ):
            state.best_discount = candidate

    if definition.notify:
        state.notifications.append(definition.notify)
    return state


def _apply_gift(definition: PromotionDefinition, order: dict, item_id: int | None, qty: int | None, applied_count: int):
    if item_id is None or qty is None:
        return
    items = order.setdefault("items", [])
    items.append(
        {
            "id": int(item_id),
            "qty": int(qty) * applied_count,
            "price": 0,
            "is_gift": True,
            "promo_source": definition.name or definition.promotion_type,
        }
    )


def _build_discount_candidate(definition: PromotionDefinition, order: dict, applied_count: int) -> dict | None:
    reward = definition.reward
    target_kind = (reward.target_kind or "ORDER").upper()
    target_group_ids = tuple(int(item_id) for item_id in (reward.target_group_ids or ()) if int(item_id) > 0)
    target_sum = _resolve_discount_target_sum(order, target_kind=target_kind, target_group_ids=target_group_ids)
    if target_sum <= 0:
        return None

    if reward.kind == "DISCOUNT_RUB":
        amount = min(target_sum, int(reward.amount or 0) * applied_count)
    elif reward.kind == "DISCOUNT_PERCENT":
        total_percent = min(100, int(reward.amount or 0) * applied_count)
        amount = min(target_sum, target_sum * total_percent // 100)
    elif reward.kind == "CHEAPEST_FREE_FROM_GROUP":
        unit_price = _resolve_cheapest_group_unit_price(order, target_group_ids=target_group_ids)
        if unit_price <= 0:
            return None
        amount = min(target_sum, unit_price * applied_count)
    else:
        return None

    return {
        "kind": reward.kind,
        "amount": amount,
        "priority": definition.priority,
        "promotion_name": definition.name,
        "applied_count": applied_count,
        "target_kind": target_kind,
        "target_group_ids": list(target_group_ids),
    }


def _resolve_discount_target_sum(order: dict, *, target_kind: str, target_group_ids: tuple[int, ...]) -> int:
    if target_kind == "GROUP":
        if not target_group_ids:
            return 0
        return resolve_metric_value(
            MetricRef(target="group", field="SUM", group_ids=target_group_ids),
            order,
        )
    return order_user_items_total(order)


def _resolve_cheapest_group_unit_price(order: dict, *, target_group_ids: tuple[int, ...]) -> int:
    if not target_group_ids:
        return 0
    group_ids = set(target_group_ids)
    candidates: list[tuple[int, int]] = []
    for item in (order or {}).get("items", []) or []:
        if not isinstance(item, dict):
            continue
        if bool(item.get("is_gift") or item.get("gift")):
            continue
        item_id = _safe_int(item.get("id"))
        qty = max(0, _safe_int(item.get("qty")))
        price = max(0, _safe_int(item.get("price")))
        if item_id not in group_ids or qty <= 0 or price <= 0:
            continue
        candidates.append((price, item_id))
    if not candidates:
        return 0
    candidates.sort(key=lambda pair: (pair[0], pair[1]))
    return candidates[0][0]


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
