from dataclasses import dataclass
from typing import Final

from tyrant.models.enums import Party, PolicyTile, Vote

AGENT_FILLED_FIELDS: Final = frozenset({"description", "message"})


@dataclass(frozen=True)
class Action:
    """Base class for every move a player can make.

    Attributes:
        description: Human-readable text shown to agents when the action is offered.
    """

    description: str


@dataclass(frozen=True)
class NominateAction(Action):
    """The president nominates a chancellor.

    Attributes:
        target_uid: UID of the nominated player.
    """

    target_uid: int


@dataclass(frozen=True)
class VoteAction(Action):
    """A player votes on the proposed government.

    Attributes:
        vote: The vote cast.
    """

    vote: Vote


@dataclass(frozen=True)
class PresidentDiscardAction(Action):
    """The president discards one of the three drawn policies.

    Attributes:
        target_index: Index of the policy to discard in `GameState.drawn_policies`.
    """

    target_index: int


@dataclass(frozen=True)
class ChancellorEnactAction(Action):
    """The chancellor enacts one of the two received policies.

    Attributes:
        target_index: Index of the policy to enact in `GameState.drawn_policies`.
    """

    target_index: int


@dataclass(frozen=True)
class ChancellorVetoAction(Action):
    """The chancellor proposes to veto both received policies."""

    pass


@dataclass(frozen=True)
class PresidentVetoResponseAction(Action):
    """The president answers the chancellor's veto proposal.

    Attributes:
        approve: Whether the president agrees to the veto.
    """

    approve: bool


@dataclass(frozen=True)
class InvestigateLoyaltyAction(Action):
    """The president investigates another player's party.

    Attributes:
        target_uid: UID of the player to investigate.
    """

    target_uid: int


@dataclass(frozen=True)
class CallSpecialElectionAction(Action):
    """The president picks the next president.

    Attributes:
        target_uid: UID of the player who becomes the next president.
    """

    target_uid: int


@dataclass(frozen=True)
class ExecutionAction(Action):
    """The president executes a player.

    Attributes:
        target_uid: UID of the player to execute.
    """

    target_uid: int


@dataclass(frozen=True)
class PolicyPeekAction(Action):
    """The president looks at the top three policies of the draw pile."""

    pass


@dataclass(frozen=True)
class ClaimPolicyPeekAction(Action):
    """The president claims what the policy peek showed.

    Attributes:
        claim_policies: The claimed policies from the top down, or `None` to decline.
    """

    claim_policies: tuple[PolicyTile, ...] | None


@dataclass(frozen=True)
class ClaimPresidentEnactAction(Action):
    """The president claims which three policies they drew and which one they discarded.

    Attributes:
        claim_policies: The claimed policies, or `None` to decline.
        claim_discarded: The claimed discarded policy, or `None` to decline.
    """

    claim_policies: tuple[PolicyTile, ...] | None
    claim_discarded: PolicyTile | None = None


@dataclass(frozen=True)
class ClaimChancellorEnactAction(Action):
    """The chancellor claims which two policies they received.

    Attributes:
        claim_policies: The claimed policies, or `None` to decline.
    """

    claim_policies: tuple[PolicyTile, ...] | None


@dataclass(frozen=True)
class ClaimInvestigationAction(Action):
    """The president claims the investigated player's party.

    Attributes:
        claim_party: The claimed party, or `None` to decline.
    """

    claim_party: Party | None


@dataclass(frozen=True)
class SpeakAction(Action):
    """A player says something during discussion.

    Attributes:
        message: What the player says, filled in by the agent.
    """

    message: str = ""


@dataclass(frozen=True)
class PassAction(Action):
    """A player stays silent during discussion."""

    pass
