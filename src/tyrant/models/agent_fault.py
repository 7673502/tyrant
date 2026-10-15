from dataclasses import dataclass

from tyrant.models.enums import GamePhase


@dataclass(frozen=True)
class AgentFault:
    """A failed attempt by an agent to choose an action.

    Attributes:
        uid: UID of the agent that failed.
        phase: Phase the game was in.
        reason: The `repr` of the exception raised.
        fell_back: Whether this failure made the runner play a random legal action.
    """

    uid: int
    phase: GamePhase
    reason: str
    fell_back: bool
