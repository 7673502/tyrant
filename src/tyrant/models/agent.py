from typing import Protocol

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


class Agent(Protocol):
    uid: int

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action: ...
