from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Order:
    id: int
    user_id: int
    status: str
    created_at: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    items_total: int = 0
    points_applied: int = 0
    payable_total: int = 0
    bonus_earned: int = 0
    comment: str = ""
    serving: Dict[str, Any] = field(default_factory=dict)
    booking: Dict[str, Any] = field(default_factory=dict)
    payment_card: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
