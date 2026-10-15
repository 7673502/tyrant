from dataclasses import dataclass, replace

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class ReplayStep:
    """One applied action.

    Attributes:
        uid: UID of the player who acted.
        action: The action applied.
        fallback: Whether the runner played the action at random after the agent failed.
    """

    uid: int
    action: Action
    fallback: bool = False


@dataclass(frozen=True)
class Replay:
    """Every action applied in a game, enough to rebuild each state.

    Attributes:
        initial_state: The unscrubbed state the game started from.
        steps: The applied actions, in order.
    """

    initial_state: GameState
    steps: tuple[ReplayStep, ...] = ()


def record_step(
    replay: Replay, uid: int, action: Action, fallback: bool = False
) -> Replay:
    """Appends an applied action to a replay.

    Args:
        replay: The current replay.
        uid: UID of the player who acted.
        action: The action applied.
        fallback: Whether the runner played the action at random after the agent failed.

    Returns:
        A new replay with the step added.
    """
    step = ReplayStep(uid=uid, action=action, fallback=fallback)
    return replace(replay, steps=replay.steps + (step,))
