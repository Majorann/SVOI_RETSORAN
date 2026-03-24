from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class PromoItem:
    id: int
    class_name: str
    priority: int
    active: bool
    photo: Optional[str] = None
    text: str = ""
    link: str = ""
    name: str = ""
    lore: str = ""
    condition: str = ""
    reward: str = ""
    notify: str = ""
    reward_mode: str = "once"
    limit_per_order: str = ""
    limit_per_user_per_day: str = ""
    start_at: str = ""
    end_at: str = ""
    dsl_valid: bool = True
    dsl_error: str = ""

    def to_dict(self):
        data = asdict(self)
        data["class"] = data.pop("class_name")
        if data["class"] == "reklama":
            return {
                "id": data["id"],
                "class": data["class"],
                "text": data["text"],
                "link": data["link"],
                "priority": data["priority"],
                "active": data["active"],
                "photo": data["photo"],
                "start_at": data["start_at"],
                "end_at": data["end_at"],
            }
        return {
            "id": data["id"],
            "class": data["class"],
            "name": data["name"],
            "lore": data["lore"],
            "priority": data["priority"],
            "active": data["active"],
            "photo": data["photo"],
            "condition": data["condition"],
            "reward": data["reward"],
            "notify": data["notify"],
            "reward_mode": data["reward_mode"],
            "limit_per_order": data["limit_per_order"],
            "limit_per_user_per_day": data["limit_per_user_per_day"],
            "start_at": data["start_at"],
            "end_at": data["end_at"],
            "dsl_valid": data["dsl_valid"],
            "dsl_error": data["dsl_error"],
        }
