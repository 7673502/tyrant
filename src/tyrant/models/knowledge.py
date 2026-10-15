from dataclasses import dataclass

from tyrant.models.enums import Party, PolicyTile


@dataclass(frozen=True)
class Knowledge:
    """Base class for what a player learned in secret.

    Attributes:
        uid: UID of the player who learned it.
    """

    uid: int


@dataclass(frozen=True)
class PresidentDrawKnowledge(Knowledge):
    """A president drew three policies after a passed election.

    Attributes:
        chancellor_uid: UID of the chancellor in that government.
        policies: The drawn policies, from the top down.
    """

    chancellor_uid: int
    policies: tuple[PolicyTile, PolicyTile, PolicyTile]


@dataclass(frozen=True)
class ChancellorReceiveKnowledge(Knowledge):
    """A chancellor received two policies from the president.

    Attributes:
        president_uid: UID of the president who passed the policies.
        policies: The received policies.
    """

    president_uid: int
    policies: tuple[PolicyTile, PolicyTile]


@dataclass(frozen=True)
class PeekKnowledge(Knowledge):
    """A president peeked at the top three policies of the deck.

    Attributes:
        policies: The peeked policies, from the top down.
    """

    policies: tuple[PolicyTile, PolicyTile, PolicyTile]


@dataclass(frozen=True)
class InvestigationKnowledge(Knowledge):
    """A president learned an investigated player's party.

    Attributes:
        target_uid: UID of the investigated player.
        party: The investigated player's party.
    """

    target_uid: int
    party: Party
