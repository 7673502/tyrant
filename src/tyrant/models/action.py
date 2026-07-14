from dataclasses import dataclass
from tyrant.models.enums import Party, PolicyTile, Vote


@dataclass(frozen=True)
class Action:
    description: str


@dataclass(frozen=True)
class NominateAction(Action):
    target_uid: int


@dataclass(frozen=True)
class VoteAction(Action):
    vote: Vote


@dataclass(frozen=True)
class PresidentDiscardAction(Action):
    target_index: int


@dataclass(frozen=True)
class ChancellorEnactAction(Action):
    target_index: int


@dataclass(frozen=True)
class ChancellorVetoAction(Action):
    pass


@dataclass(frozen=True)
class PresidentVetoResponseAction(Action):
    approve: bool


@dataclass(frozen=True)
class InvestigateLoyaltyAction(Action):
    target_uid: int


@dataclass(frozen=True)
class CallSpecialElectionAction(Action):
    target_uid: int


@dataclass(frozen=True)
class ExecutionAction(Action):
    target_uid: int


@dataclass(frozen=True)
class PolicyPeekAction(Action):
    pass


@dataclass(frozen=True)
class ClaimPolicyPeekAction(Action):
    claim_policies: tuple[PolicyTile, ...] | None


@dataclass(frozen=True)
class ClaimPresidentEnactAction(Action):
    claim_policies: tuple[PolicyTile, ...] | None


@dataclass(frozen=True)
class ClaimChancellorEnactAction(Action):
    claim_policies: tuple[PolicyTile, ...] | None


@dataclass(frozen=True)
class ClaimInvestigationAction(Action):
    claim_party: Party | None
