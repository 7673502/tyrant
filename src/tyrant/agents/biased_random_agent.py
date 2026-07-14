import random

from tyrant.models.action import Action
from tyrant.models.enums import Party
from tyrant.models.game_state import GameState


class BiasedRandomAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        party = next(p.party for p in state.players if p.uid == self.uid)

        party_str = "liberal" if party is Party.LIBERAL else "fascist"
        opposite_party_str = "fascist" if party is Party.LIBERAL else "liberal"

        for action in valid_actions:
            if action.id == f"discard_{opposite_party_str}":
                return action
            elif action.id == f"enact_{party_str}":
                return action
            elif action.id == "vote_ja":
                return action

        return random.choice(valid_actions)
