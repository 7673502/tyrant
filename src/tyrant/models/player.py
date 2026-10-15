from dataclasses import dataclass
from tyrant.models.enums import Party, Role, HIDDEN


@dataclass(frozen=True)
class Player:
    """A player at the table.

    Attributes:
        uid: The player's unique ID.
        party: The player's party, or `HIDDEN` in a scrubbed state.
        role: The player's role, or `HIDDEN` in a scrubbed state.
        is_alive: Whether the player has not been executed.
    """

    uid: int
    party: Party | HIDDEN
    role: Role | HIDDEN
    is_alive: bool = True
