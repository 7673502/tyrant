from dataclasses import dataclass

from frozendict import frozendict

from tyrant.models.claim import Claim
from tyrant.models.enums import (
    DiscussionContext,
    Party,
    PolicyTile,
    Vote,
    WinCondition,
)


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class NominationEvent(Event):
    president_uid: int
    chancellor_uid: int


@dataclass(frozen=True)
class ElectionEvent(Event):
    president_uid: int
    chancellor_uid: int
    votes: frozendict[int, Vote]
    result: Vote


@dataclass(frozen=True)
class PolicyEnactedEvent(Event):
    policy: PolicyTile
    president_uid: int | None
    chancellor_uid: int | None

    @property
    def top_deck(self) -> bool:
        return self.president_uid is None and self.chancellor_uid is None


@dataclass(frozen=True)
class VetoEvent(Event):
    president_uid: int
    chancellor_uid: int
    approved: bool


@dataclass(frozen=True)
class ClaimEvent(Event):
    claim: Claim
    president_uid: int
    chancellor_uid: int | None
    target_uid: int | None


@dataclass(frozen=True)
class InvestigationEvent(Event):
    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class SpecialElectionEvent(Event):
    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class ExecutionEvent(Event):
    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class SpeechEvent(Event):
    uid: int
    text: str | None
    context: DiscussionContext


@dataclass(frozen=True)
class GameOverEvent(Event):
    winner: Party
    condition: WinCondition
