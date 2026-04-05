from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ast import ConditionGroup, ConditionNot, MetricRef, PromotionDefinition


@dataclass(frozen=True)
class PromotionEvaluationResult:
    matched: bool
    active: bool
    base_count: int
    applied_count: int
    notify: str | None


def evaluate_condition(node, order: dict) -> bool:
    if isinstance(node, ConditionGroup):
        if node.operator == "AND":
            return evaluate_condition(node.left, order) and evaluate_condition(node.right, order)
        return evaluate_condition(node.left, order) or evaluate_condition(node.right, order)
    if isinstance(node, ConditionNot):
        return not evaluate_condition(node.operand, order)

    metric_value = resolve_metric_value(node.metric, order)
    target_value = node.value
    if node.operator == "=":
        return metric_value == target_value
    if node.operator == "==":
        return metric_value == target_value
    if node.operator == "!=":
        return metric_value != target_value
    if node.operator == ">":
        return metric_value > target_value
    if node.operator == "<":
        return metric_value < target_value
    if node.operator == ">=":
        return metric_value >= target_value
    if node.operator == "<=":
        return metric_value <= target_value
    return False


def evaluate_promotion(
    definition: PromotionDefinition,
    order: dict,
    *,
    user_day_applied_count: int = 0,
    at: datetime | None = None,
) -> PromotionEvaluationResult:
    active = is_promotion_active(definition, at=at)
    if not active:
        return PromotionEvaluationResult(False, False, 0, 0, None)

    matched = evaluate_condition(definition.condition, order)
    if not matched:
        return PromotionEvaluationResult(False, True, 0, 0, None)

    base_count = compute_base_count(definition, order)
    applied_count = apply_limits(
        base_count,
        limit_per_order=definition.limit_per_order,
        limit_per_user_per_day=definition.limit_per_user_per_day,
        user_day_applied_count=user_day_applied_count,
    )
    return PromotionEvaluationResult(
        matched=applied_count > 0,
        active=True,
        base_count=base_count,
        applied_count=applied_count,
        notify=definition.notify if applied_count > 0 else None,
    )


def is_promotion_active(definition: PromotionDefinition, *, at: datetime | None = None) -> bool:
    if not definition.active:
        return False
    current = at or datetime.now()
    if definition.start_at and current < definition.start_at:
        return False
    if definition.end_at and current > definition.end_at:
        return False
    return True


def compute_base_count(definition: PromotionDefinition, order: dict) -> int:
    if not evaluate_condition(definition.condition, order):
        return 0
    if definition.reward_mode == "once":
        return 1
    comparison = definition.condition
    metric_value = resolve_metric_value(comparison.metric, order)
    if comparison.value <= 0:
        return 0
    return metric_value // comparison.value


def apply_limits(
    base_count: int,
    *,
    limit_per_order: int | None,
    limit_per_user_per_day: int | None,
    user_day_applied_count: int,
) -> int:
    applied = max(0, int(base_count or 0))
    if limit_per_order is not None:
        applied = min(applied, max(0, int(limit_per_order)))
    if limit_per_user_per_day is not None:
        remaining = max(0, int(limit_per_user_per_day) - max(0, int(user_day_applied_count or 0)))
        applied = min(applied, remaining)
    return max(0, applied)


def resolve_metric_value(metric: MetricRef, order: dict) -> int:
    items = [item for item in (order or {}).get("items", []) if _is_user_item(item)]
    if metric.target == "order":
        return sum(max(0, _safe_int(item.get("price"))) * max(0, _safe_int(item.get("qty"))) for item in items)

    matched_items = []
    if metric.target == "all_items":
        matched_items = items
    elif metric.target == "item":
        matched_items = [item for item in items if _safe_int(item.get("id")) == metric.item_id]
    elif metric.target == "type":
        matched_items = [item for item in items if str(item.get("type") or "").strip() == str(metric.item_type)]
    elif metric.target == "group":
        group_ids = set(metric.group_ids)
        matched_items = [item for item in items if _safe_int(item.get("id")) in group_ids]

    if metric.field == "QTY":
        return sum(max(0, _safe_int(item.get("qty"))) for item in matched_items)
    if metric.field == "UNIQUE_QTY":
        return len({max(0, _safe_int(item.get("id"))) for item in matched_items if max(0, _safe_int(item.get("qty"))) > 0})
    return sum(max(0, _safe_int(item.get("price"))) * max(0, _safe_int(item.get("qty"))) for item in matched_items)


def order_user_items_total(order: dict) -> int:
    return resolve_metric_value(MetricRef(target="order", field="SUBTOTAL"), order)


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_user_item(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    return not bool(item.get("is_gift") or item.get("gift"))
