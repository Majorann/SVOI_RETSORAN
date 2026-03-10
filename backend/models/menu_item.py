from dataclasses import asdict, dataclass


@dataclass
class MenuItem:
    id: int
    name: str
    lore: str
    type: str
    price: int
    photo: str
    popularity: int = 0
    featured: bool = False

    def to_dict(self):
        return asdict(self)
