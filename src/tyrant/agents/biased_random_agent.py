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
    """An agent that favors its own party where it can and otherwise plays at random.

    It discards a policy of the other party, enacts a policy of its own party and always votes ja. Every other choice is random.

    Attributes:
        uid: The player's unique ID.
    """

    def __init__(self, uid: int):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
        """
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Returns the first offered action that favors the agent's party, or a random one.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            One of `valid_actions`.
        """
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
