from dataclasses import dataclass, replace

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class ReplayStep:
    uid: int
    action: Action
    fallback: bool = False


@dataclass(frozen=True)
class Replay:
    initial_state: GameState
    steps: tuple[ReplayStep, ...] = ()


def record_step(
    replay: Replay, uid: int, action: Action, fallback: bool = False
) -> Replay:
    step = ReplayStep(uid=uid, action=action, fallback=fallback)
    return replace(replay, steps=replay.steps + (step,))
