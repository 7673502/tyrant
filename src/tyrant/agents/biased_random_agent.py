import random

from tyrant.models.action import (
    Action,
    ChancellorEnactAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.enums import Party, PolicyTile, Vote
from tyrant.models.game_state import GameState


class BiasedRandomAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        party = next(p.party for p in state.players if p.uid == self.uid)

        target_enact = (
            PolicyTile.LIBERAL if party is Party.LIBERAL else PolicyTile.FASCIST
        )
        target_discard = (
            PolicyTile.FASCIST if party is Party.LIBERAL else PolicyTile.LIBERAL
        )

        for action in valid_actions:
            match action:
                case PresidentDiscardAction(target_index=idx):
                    if state.drawn_policies[idx] == target_discard:
                        return action
                case ChancellorEnactAction(target_index=idx):
                    if state.drawn_policies[idx] == target_enact:
                        return action
                case VoteAction(vote=Vote.JA):
                    return action
                case _:
                    pass

        return random.choice(valid_actions)
