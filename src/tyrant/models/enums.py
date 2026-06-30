from enum import StrEnum, auto


class Party(StrEnum):
    FASCIST = auto()
    LIBERAL = auto()


class Role(StrEnum):
    FASCIST = auto()
    LIBERAL = auto()
    HITLER = auto()


class PolicyTile(StrEnum):
    FASCIST = auto()
    LIBERAL = auto()


class PresidentialPower(StrEnum):
    NONE = auto()
    INVESTIGATE_LOYALTY = auto()
    CALL_SPECIAL_ELECTION = auto()
    POLICY_PEEK = auto()
    EXECUTION = auto()


class Vote(StrEnum):
    JA = auto()
    NEIN = auto()


class GamePhase(StrEnum):
    SETUP = auto()
    NOMINATION = auto()
    VOTING = auto()
    PRESIDENT_DISCARD = auto()
    CHANCELLOR_ENACT = auto()
    PRESIDENTIAL_POWER = auto()
    POLICY_PEEK = auto()
    PRESIDENT_VETO_RESPONSE = auto()
    GAME_OVER = auto()
