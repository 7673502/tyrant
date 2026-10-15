import random

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


class RandomAgent:
    """An agent that chooses uniformly at random from the offered actions.

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
        """Returns a random offered action.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            One of `valid_actions`.
        """
        return random.choice(valid_actions)
