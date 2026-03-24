from __future__ import annotations

from dataclasses import dataclass

from .ast import Comparison, ConditionGroup, PromotionDefinition, PromotionDslError
from .parser import parse_promotion


class PromotionValidationError(PromotionDslError):
    pass


@dataclass(frozen=True)
class PromotionValidationContext:
    known_item_ids: set[int]
    active_item_ids: set[int]
    known_types: set[str]


def validate_promotion(
    promotion: PromotionDefinition | str,
    *,
    known_item_ids: set[int] | None = None,
    active_item_ids: set[int] | None = None,
    known_types: set[str] | None = None,
) -> PromotionDefinition:
    definition = parse_promotion(promotion) if isinstance(promotion, str) else promotion
    context = PromotionValidationContext(
        known_item_ids=set(known_item_ids or set()),
        active_item_ids=set(active_item_ids or set()),
        known_types=set(known_types or set()),
    )

    if definition.promotion_type != "akciya":
        raise PromotionValidationError("Field type must be akciya")
    if definition.start_at and definition.end_at and definition.start_at > definition.end_at:
        raise PromotionValidationError("start_at must be earlier than or equal to end_at")

    _validate_condition_refs(definition.condition, context)
    _validate_reward(definition, context)
    _validate_per_match(definition)
    return definition


def _validate_condition_refs(node, context: PromotionValidationContext):
    if isinstance(node, ConditionGroup):
        _validate_condition_refs(node.left, context)
        _validate_condition_refs(node.right, context)
        return

    metric = node.metric
    if metric.target == "item":
        if context.known_item_ids and metric.item_id not in context.known_item_ids:
            raise PromotionValidationError(f"Unknown menu item id in condition: {metric.item_id}")
        return
    if metric.target == "group":
        if context.known_item_ids:
            missing = [item_id for item_id in metric.group_ids if item_id not in context.known_item_ids]
            if missing:
                raise PromotionValidationError(f"Unknown menu item ids in GROUP: {missing}")
        return
    if metric.target == "type":
        if context.known_types and metric.item_type not in context.known_types:
            raise PromotionValidationError(f"Unknown menu item type in condition: {metric.item_type}")


def _validate_reward(definition: PromotionDefinition, context: PromotionValidationContext):
    reward = definition.reward
    if reward.kind == "POINTS":
        if reward.amount is None or reward.amount <= 0:
            raise PromotionValidationError("POINTS reward must be greater than zero")
        return
    if reward.kind == "DISCOUNT_PERCENT":
        if reward.amount is None or reward.amount < 1 or reward.amount > 100:
            raise PromotionValidationError("DISCOUNT_PERCENT reward must be between 1 and 100")
        return
    if reward.kind == "DISCOUNT_RUB":
        if reward.amount is None or reward.amount <= 0:
            raise PromotionValidationError("DISCOUNT_RUB reward must be greater than zero")
        return
    if reward.kind == "GIFT":
        if reward.item_id is None or reward.qty is None or reward.qty <= 0:
            raise PromotionValidationError("GIFT reward must reference a valid item and qty")
        if context.known_item_ids and reward.item_id not in context.known_item_ids:
            raise PromotionValidationError(f"Unknown gift item id: {reward.item_id}")
        if context.active_item_ids and reward.item_id not in context.active_item_ids:
            raise PromotionValidationError(f"Gift item is not active: {reward.item_id}")


def _validate_per_match(definition: PromotionDefinition):
    if definition.reward_mode != "per_match":
        return
    node = definition.condition
    if not isinstance(node, Comparison):
        raise PromotionValidationError("reward_mode=per_match supports only a single comparison")
    if node.operator != ">=":
        raise PromotionValidationError("reward_mode=per_match requires operator >=")
    if node.value <= 0:
        raise PromotionValidationError("reward_mode=per_match requires a positive integer threshold")
