from dataclasses import dataclass
from typing import Final

from tyrant.models.enums import DiscussionContext, GamePhase

MAX_SPEECH_LENGTH: Final = 500
"""Maximum number of characters kept from a speech."""


@dataclass(frozen=True)
class Discussion:
    """A discussion in progress, where living players take turns to speak.

    Attributes:
        context: What triggered the discussion.
        resume_phase: Phase the game returns to when the discussion ends.
        speaker_order: UIDs of the speakers, in turn order.
        rounds: How many times the table goes around.
        turn: Number of turns taken so far.
    """

    context: DiscussionContext
    resume_phase: GamePhase
    speaker_order: tuple[int, ...]
    rounds: int = 1
    turn: int = 0

    @property
    def current_speaker(self) -> int:
        """UID of the player whose turn it is to speak."""
        return self.speaker_order[self.turn % len(self.speaker_order)]

    @property
    def current_round(self) -> int:
        """The current round, starting at 1."""
        return self.turn // len(self.speaker_order) + 1

    @property
    def is_complete(self) -> bool:
        """Whether every speaker has taken all their turns."""
        return self.turn >= self.rounds * len(self.speaker_order)
