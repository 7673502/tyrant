from dataclasses import dataclass
from tyrant.models.enums import Party, Role

@dataclass
class Player:
    uid: int
    party: Party
    role: Role
