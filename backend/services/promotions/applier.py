from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from .ast import PromotionDefinition
from .evaluator import order_user_items_total


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
    elif reward.kind in {"DISCOUNT_PERCENT", "DISCOUNT_RUB"}:
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
    order_sum = order_user_items_total(order)
    if order_sum <= 0:
        return None

    if reward.kind == "DISCOUNT_RUB":
        amount = min(order_sum, int(reward.amount or 0) * applied_count)
    else:
        total_percent = min(100, int(reward.amount or 0) * applied_count)
        amount = min(order_sum, order_sum * total_percent // 100)

    return {
        "kind": reward.kind,
        "amount": amount,
        "priority": definition.priority,
        "promotion_name": definition.name,
        "applied_count": applied_count,
    }
