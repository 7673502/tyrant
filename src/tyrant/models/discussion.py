from dataclasses import dataclass

from tyrant.models.enums import DiscussionContext, GamePhase


@dataclass(frozen=True)
class Message:
    uid: int
    text: str | None
    context: DiscussionContext


@dataclass(frozen=True)
class Discussion:
    context: DiscussionContext
    resume_phase: GamePhase
    speaker_order: tuple[int, ...]
    rounds: int = 1
    turn: int = 0

    @property
    def current_speaker(self) -> int:
        return self.speaker_order[self.turn % len(self.speaker_order)]

    @property
    def current_round(self) -> int:
        return self.turn // len(self.speaker_order) + 1

    @property
    def is_complete(self) -> bool:
        return self.turn >= self.rounds * len(self.speaker_order)
