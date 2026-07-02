from dataclasses import dataclass
from tyrant.models.enums import Party, Role, HIDDEN


@dataclass(frozen=True)
class Player:
    uid: int
    party: Party | HIDDEN
    role: Role | HIDDEN
    is_alive: bool = True
