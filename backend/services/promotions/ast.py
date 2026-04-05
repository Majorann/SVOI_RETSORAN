from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class PromotionDslError(ValueError):
    pass


@dataclass(frozen=True)
class MetricRef:
    target: Literal["item", "all_items", "type", "group", "order"]
    field: Literal["QTY", "SUM", "UNIQUE_QTY", "SUBTOTAL"]
    item_id: int | None = None
    item_type: str | None = None
    group_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Comparison:
    metric: MetricRef
    operator: Literal["=", "==", "!=", ">", "<", ">=", "<="]
    value: int


@dataclass(frozen=True)
class ConditionGroup:
    operator: Literal["AND", "OR"]
    left: "ConditionNode"
    right: "ConditionNode"


@dataclass(frozen=True)
class ConditionNot:
    operand: "ConditionNode"


ConditionNode = Comparison | ConditionGroup | ConditionNot


@dataclass(frozen=True)
class Reward:
    kind: Literal["POINTS", "DISCOUNT_PERCENT", "DISCOUNT_RUB", "GIFT", "CHEAPEST_FREE_FROM_GROUP"]
    amount: int | None = None
    item_id: int | None = None
    qty: int | None = None
    target_kind: Literal["ORDER", "GROUP"] | None = None
    target_group_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class PromotionDefinition:
    promotion_type: str
    name: str
    dsl_version: Literal[1, 2]
    active: bool
    priority: int
    condition: ConditionNode
    reward: Reward
    notify: str | None
    reward_mode: Literal["once", "per_match"]
    limit_per_order: int | None
    limit_per_user_per_day: int | None
    start_at: datetime | None
    end_at: datetime | None
