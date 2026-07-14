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

        party_str = "Liberal" if party is Party.LIBERAL else "Fascist"
        opposite_party_str = "Fascist" if party is Party.LIBERAL else "Liberal"

        for action in valid_actions:
            if action.description == f"Discard {opposite_party_str}":
                return action
            elif action.description == f"Enact {party_str}":
                return action
            elif action.id == "vote_ja":
                return action

        return random.choice(valid_actions)
