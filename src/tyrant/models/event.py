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
    """Base class for the public events recorded in `GameState.events`."""

    pass


@dataclass(frozen=True)
class NominationEvent(Event):
    """The president nominated a chancellor.

    Attributes:
        president_uid: UID of the president.
        chancellor_uid: UID of the nominee.
    """

    president_uid: int
    chancellor_uid: int


@dataclass(frozen=True)
class ElectionEvent(Event):
    """An election resolved.

    Attributes:
        president_uid: UID of the president.
        chancellor_uid: UID of the nominated chancellor.
        votes: Each voter's UID mapped to their vote.
        result: `Vote.JA` if the government was elected, otherwise `Vote.NEIN`.
    """

    president_uid: int
    chancellor_uid: int
    votes: frozendict[int, Vote]
    result: Vote


@dataclass(frozen=True)
class PolicyEnactedEvent(Event):
    """A policy was enacted.

    Attributes:
        policy: The enacted policy.
        president_uid: UID of the president, or `None` for a top-deck.
        chancellor_uid: UID of the chancellor, or `None` for a top-deck.
    """

    policy: PolicyTile
    president_uid: int | None
    chancellor_uid: int | None

    @property
    def top_deck(self) -> bool:
        """Whether the election tracker enacted the policy from the top of the deck."""
        return self.president_uid is None and self.chancellor_uid is None


@dataclass(frozen=True)
class VetoEvent(Event):
    """The president answered the chancellor's veto proposal.

    Attributes:
        president_uid: UID of the president.
        chancellor_uid: UID of the chancellor who proposed the veto.
        approved: Whether the president agreed to the veto.
    """

    president_uid: int
    chancellor_uid: int
    approved: bool


@dataclass(frozen=True)
class ClaimEvent(Event):
    """A player made a claim.

    Attributes:
        claim: The claim made.
        president_uid: UID of the president of the government or power the claim is about.
        chancellor_uid: UID of the chancellor for a policy claim, otherwise `None`.
        target_uid: UID of the investigated player for an investigation claim, otherwise `None`.
        correction: Whether the claim replaces the player's earlier claim about the same government.
    """

    claim: Claim
    president_uid: int
    chancellor_uid: int | None
    target_uid: int | None
    correction: bool = False


@dataclass(frozen=True)
class InvestigationEvent(Event):
    """The president investigated a player.

    Attributes:
        president_uid: UID of the president.
        target_uid: UID of the investigated player.
    """

    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class SpecialElectionEvent(Event):
    """The president called a special election.

    Attributes:
        president_uid: UID of the president.
        target_uid: UID of the player who becomes the next president.
    """

    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class ExecutionEvent(Event):
    """The president executed a player.

    Attributes:
        president_uid: UID of the president.
        target_uid: UID of the executed player.
    """

    president_uid: int
    target_uid: int


@dataclass(frozen=True)
class SpeechEvent(Event):
    """A player spoke or passed during discussion.

    Attributes:
        uid: UID of the speaker.
        text: What the player said, or `None` if they passed.
        context: What triggered the discussion.
    """

    uid: int
    text: str | None
    context: DiscussionContext


@dataclass(frozen=True)
class GameOverEvent(Event):
    """The game ended.

    Attributes:
        winner: The winning party.
        condition: How the game was won.
    """

    winner: Party
    condition: WinCondition
