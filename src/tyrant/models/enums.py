from enum import StrEnum, auto


class _HiddenMeta(type):
    """Metaclass that makes `HIDDEN` print as its name."""

    def __repr__(cls):
        return "HIDDEN"


class HIDDEN(metaclass=_HiddenMeta):
    """Sentinel for a value the viewer is not allowed to see.

    `scrub_state` puts the class itself, not an instance, in place of each hidden value.
    """

    pass


class Party(StrEnum):
    """A player's team."""

    FASCIST = auto()
    LIBERAL = auto()


class Role(StrEnum):
    """A player's secret role; Hitler belongs to the fascist party."""

    FASCIST = auto()
    LIBERAL = auto()
    HITLER = auto()


class PolicyTile(StrEnum):
    """A policy card."""

    FASCIST = auto()
    LIBERAL = auto()


class PresidentialPower(StrEnum):
    """A power that an enacted fascist policy grants the president.

    Attributes:
        NONE: No power.
        INVESTIGATE_LOYALTY: The president learns another player's party.
        CALL_SPECIAL_ELECTION: The president picks the next president.
        POLICY_PEEK: The president sees the top three policies of the deck.
        EXECUTION: The president kills a player.
    """

    NONE = auto()
    INVESTIGATE_LOYALTY = auto()
    CALL_SPECIAL_ELECTION = auto()
    POLICY_PEEK = auto()
    EXECUTION = auto()


class Vote(StrEnum):
    """A ballot in an election."""

    JA = auto()
    NEIN = auto()


class GamePhase(StrEnum):
    """The step of the game that decides who acts next.

    Attributes:
        SETUP: Not used by the engine; games start in `NOMINATION`.
        NOMINATION: The president nominates a chancellor.
        DISCUSSION: Living players take turns to speak.
        VOTING: Every living player votes on the proposed government.
        PRESIDENT_DISCARD: The president discards one of three drawn policies.
        CHANCELLOR_ENACT: The chancellor enacts one of two policies or proposes a veto.
        CLAIM_POLICIES: The president and chancellor claim the policies they saw.
        PRESIDENTIAL_POWER: The president uses the active power.
        CLAIM_POLICY_PEEK: The president claims what the policy peek showed.
        CLAIM_INVESTIGATION: The president claims the investigated player's party.
        PRESIDENT_VETO_RESPONSE: The president answers the chancellor's veto proposal.
        GAME_OVER: The game has ended.
    """

    SETUP = auto()
    NOMINATION = auto()
    DISCUSSION = auto()
    VOTING = auto()
    PRESIDENT_DISCARD = auto()
    CHANCELLOR_ENACT = auto()
    CLAIM_POLICIES = auto()
    PRESIDENTIAL_POWER = auto()
    CLAIM_POLICY_PEEK = auto()
    CLAIM_INVESTIGATION = auto()
    PRESIDENT_VETO_RESPONSE = auto()
    GAME_OVER = auto()


class DiscussionContext(StrEnum):
    """The public event that triggered a discussion.

    Attributes:
        AFTER_NOMINATION: The president nominated a chancellor.
        AFTER_FAILED_ELECTION: An election failed.
        AFTER_POLICY_CLAIMS: The government claimed its policies and no power needs a choice next.
        BEFORE_INVESTIGATION: The government claimed its policies and the president will investigate next.
        BEFORE_SPECIAL_ELECTION: The government claimed its policies and the president will call a special election next.
        BEFORE_EXECUTION: The government claimed its policies and the president will execute a player next.
        AFTER_INVESTIGATION_CLAIM: The president claimed an investigation result.
        AFTER_PEEK_CLAIM: The president claimed what a policy peek showed.
        AFTER_SPECIAL_ELECTION: The president called a special election.
        AFTER_EXECUTION: The president executed a player.
    """

    AFTER_NOMINATION = auto()
    AFTER_FAILED_ELECTION = auto()
    AFTER_POLICY_CLAIMS = auto()
    BEFORE_INVESTIGATION = auto()
    BEFORE_SPECIAL_ELECTION = auto()
    BEFORE_EXECUTION = auto()
    AFTER_INVESTIGATION_CLAIM = auto()
    AFTER_PEEK_CLAIM = auto()
    AFTER_SPECIAL_ELECTION = auto()
    AFTER_EXECUTION = auto()


class WinCondition(StrEnum):
    """How a game was won.

    Attributes:
        LIBERAL_POLICIES: Five liberal policies were enacted.
        FASCIST_POLICIES: Six fascist policies were enacted.
        HITLER_ELECTED: Hitler was elected chancellor after three fascist policies were enacted.
        HITLER_EXECUTED: Hitler was executed.
    """

    LIBERAL_POLICIES = auto()
    FASCIST_POLICIES = auto()
    HITLER_ELECTED = auto()
    HITLER_EXECUTED = auto()
