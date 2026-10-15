from typing import Protocol

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


class Agent(Protocol):
    """Protocol that every player implementation satisfies.

    Attributes:
        uid: The player's unique ID.
    """

    uid: int

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Chooses one of the offered actions.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            One of `valid_actions`. The agent may fill in `description` and `SpeakAction.message`.
        """
