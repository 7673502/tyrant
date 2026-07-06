from dataclasses import dataclass
from typing import Protocol

from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class Action:
    id: str
    description: str


class Agent(Protocol):
    player_uid: int

    def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> str: ...
