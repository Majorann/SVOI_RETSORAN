from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class User:
    id: int
    name: str
    phone: str
    password_hash: str
    created_at: str
    balance: int = 0
    cards: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
