from dataclasses import dataclass

from tyrant.models.enums import GamePhase


@dataclass(frozen=True)
class AgentFault:
    """A failed attempt by an agent to choose an action.

    Attributes:
        uid: UID of the agent that failed.
        phase: Phase the game was in.
        reason: The `repr` of the exception raised.
        fell_back: Whether this failure made the runner play a fallback action: a pass when one is offered, otherwise a random legal action.
        step: Index of the replay step the agent's action becomes; the fault happens before that step is recorded.
        reply: The agent's raw rejected reply, from `InvalidMoveError.reply`, or `None`.
    """

    uid: int
    phase: GamePhase
    reason: str
    fell_back: bool
    step: int
    reply: str | None = None
