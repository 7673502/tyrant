from dataclasses import dataclass
from tyrant.models.enums import Party, Role


@dataclass(frozen=True)
class Player:
    uid: int
    party: Party | None
    role: Role | None
    is_alive: bool = True
