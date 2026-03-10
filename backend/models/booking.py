from dataclasses import asdict, dataclass


@dataclass
class Booking:
    table_id: int
    date: str
    time: str
    name: str
    user_id: int
    created_at: str

    def to_dict(self):
        return asdict(self)
