from dataclasses import dataclass

from tyrant.models.enums import Party, PolicyTile


@dataclass(frozen=True)
class Claim:
    """Base class for what a player says they saw.

    Attributes:
        uid: UID of the player making the claim.
    """

    uid: int


@dataclass(frozen=True)
class PresidentEnactClaim(Claim):
    """The president's claim about the three policies they drew.

    Attributes:
        policies: The claimed policies, or `None` if the president declined.
    """

    policies: tuple[PolicyTile, PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class ChancellorEnactClaim(Claim):
    """The chancellor's claim about the two policies they received.

    Attributes:
        policies: The claimed policies, or `None` if the chancellor declined.
    """

    policies: tuple[PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class PeekClaim(Claim):
    """The president's claim about the top three policies of the deck.

    Attributes:
        policies: The claimed policies from the top down, or `None` if the president declined.
    """

    policies: tuple[PolicyTile, PolicyTile, PolicyTile] | None


@dataclass(frozen=True)
class InvestigationClaim(Claim):
    """The president's claim about the investigated player's party.

    Attributes:
        party: The claimed party, or `None` if the president declined.
    """

    party: Party | None
