from dataclasses import asdict, dataclass


@dataclass
class MenuItem:
    id: int
    name: str
    lore: str
    type: str
    price: int
    photo: str
    portion_label: str = ""
    portion_tone_rgb: str = ""
    popularity: int = 0
    featured: bool = False
    active: bool = True

    def to_dict(self):
        return asdict(self)
