from dataclasses import dataclass, replace

from tyrant.models.action import Action
from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class ReplayStep:
    uid: int
    action: Action


@dataclass(frozen=True)
class Replay:
    initial_state: GameState
    steps: tuple[ReplayStep, ...] = ()


def record_step(replay: Replay, uid: int, action: Action) -> Replay:
    return replace(replay, steps=replay.steps + (ReplayStep(uid=uid, action=action),))
