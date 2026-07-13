from dataclasses import dataclass

from tyrant.models.enums import Party, PolicyTile


@dataclass(frozen=True)
class Claim:
    uid: int


@dataclass(frozen=True)
class PresidentEnactClaim(Claim):
    policies: tuple[PolicyTile, PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class ChancellorEnactClaim(Claim):
    policies: tuple[PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class PeekClaim(Claim):
    policies: tuple[PolicyTile, PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class InvestigationClaim(Claim):
    party: Party | None
