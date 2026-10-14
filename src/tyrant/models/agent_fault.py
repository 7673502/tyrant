from dataclasses import dataclass

from tyrant.models.enums import GamePhase


@dataclass(frozen=True)
class AgentFault:
    uid: int
    phase: GamePhase
    reason: str
    fell_back: bool
