import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace

from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.action import Action, SpeakAction
from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class PendingTurn:
    """A turn waiting for a person's choice.

    Attributes:
        state: The game state, scrubbed for the player.
        valid_actions: The actions the player may take now.
    """

    state: GameState
    valid_actions: tuple[Action, ...]


class HumanAgent:
    """An agent whose choices come from outside code, such as a web server or a UI.

    When asked for an action it publishes the turn on `pending`, calls `on_turn` if set, and waits until `submit` is called. If the runner times out the attempt, the turn is withdrawn and `pending` is cleared. `submit` must be called from the event loop the game runs on.

    Attributes:
        uid: The player's unique ID.
        pending: The turn waiting for a choice, or `None`.
        on_turn: Called with each new turn, or `None`.
    """

    def __init__(self, uid: int, on_turn: Callable[[PendingTurn], None] | None = None):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
            on_turn: Called with each new turn, for example to push it to the player, or `None`.
        """
        self.uid = uid
        self.on_turn = on_turn
        self.pending: PendingTurn | None = None
        self._choice: asyncio.Future[Action] | None = None

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Publishes the turn and waits for `submit`.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            The submitted action.
        """
        self._choice = asyncio.get_running_loop().create_future()
        self.pending = PendingTurn(state=state, valid_actions=valid_actions)
        if self.on_turn is not None:
            self.on_turn(self.pending)
        try:
            return await self._choice
        finally:
            self.pending = None
            self._choice = None

    def submit(self, index: int, message: str = "") -> None:
        """Chooses an action for the pending turn.

        Args:
            index: Index of the chosen action in `pending.valid_actions`.
            message: What the player says, used only when the chosen action is a `SpeakAction`.

        Raises:
            TyrantError: If no turn is pending.
            InvalidMoveError: If `index` is out of range.
        """
        if self.pending is None or self._choice is None or self._choice.done():
            raise TyrantError("No turn is pending")
        valid_actions = self.pending.valid_actions
        if not 0 <= index < len(valid_actions):
            raise InvalidMoveError(
                f"Index {index} is out of range for {len(valid_actions)} actions"
            )
        action = valid_actions[index]
        if isinstance(action, SpeakAction):
            action = replace(action, message=message)
        self._choice.set_result(action)
