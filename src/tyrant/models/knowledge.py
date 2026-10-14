from dataclasses import dataclass

from tyrant.models.enums import Party, PolicyTile


@dataclass(frozen=True)
class Knowledge:
    uid: int


@dataclass(frozen=True)
class PresidentDrawKnowledge(Knowledge):
    chancellor_uid: int
    policies: tuple[PolicyTile, PolicyTile, PolicyTile]


@dataclass(frozen=True)
class ChancellorReceiveKnowledge(Knowledge):
    president_uid: int
    policies: tuple[PolicyTile, PolicyTile]


@dataclass(frozen=True)
class PeekKnowledge(Knowledge):
    policies: tuple[PolicyTile, PolicyTile, PolicyTile]


@dataclass(frozen=True)
class InvestigationKnowledge(Knowledge):
    target_uid: int
    party: Party
