import random

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


class RandomAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        return random.choice(valid_actions)
