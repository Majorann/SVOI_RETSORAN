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
            }
        return {
            "id": data["id"],
            "class": data["class"],
            "name": data["name"],
            "lore": data["lore"],
            "priority": data["priority"],
            "active": data["active"],
            "photo": data["photo"],
        }
