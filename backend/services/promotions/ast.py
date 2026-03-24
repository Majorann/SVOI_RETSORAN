from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class PromotionDslError(ValueError):
    pass


@dataclass(frozen=True)
class MetricRef:
    target: Literal["item", "all_items", "type", "group", "order"]
    field: Literal["QTY", "SUM"]
    item_id: int | None = None
    item_type: str | None = None
    group_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Comparison:
    metric: MetricRef
    operator: Literal["=", ">", "<", ">=", "<="]
    value: int


@dataclass(frozen=True)
class ConditionGroup:
    operator: Literal["AND", "OR"]
    left: "ConditionNode"
    right: "ConditionNode"


ConditionNode = Comparison | ConditionGroup


@dataclass(frozen=True)
class Reward:
    kind: Literal["POINTS", "DISCOUNT_PERCENT", "DISCOUNT_RUB", "GIFT"]
    amount: int | None = None
    item_id: int | None = None
    qty: int | None = None


@dataclass(frozen=True)
class PromotionDefinition:
    promotion_type: str
    name: str
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
