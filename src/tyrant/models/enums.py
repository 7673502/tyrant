from enum import Enum

class Party(Enum):
    RED = "RED"
    BLUE = "BLUE"

class Role(Enum):
    RED = "RED"
    BLUE = "BLUE"
    TYRANT = "TYRANT"

class PolicyTile(Enum):
    RED = "RED"
    BLUE = "BLUE"

class PresidentialPower(Enum):
    NONE = "NO POWER"
    INVESTIGATE = "INVESTIGATE LOYALTY"
    SPECIAL_ELECTION = "CALL SPECIAL ELECTION"
    POLICY_PEEK = "POLICY PEEK"
    EXECUTION = "EXECUTION"

class Vote(Enum):
    JA = "JA"
    NEIN = "NEIN"

class GamePhase(Enum):
    SETUP = "SETUP"
    VOTING = "VOTING"
    PRESIDENT_DISCARD = "PRESIDENT DISCARD"
    CHANCELLOR_DISCARD = "CHANCELLOR DISCARD"
    PRESIDENTIAL_POWER = "PRESIDENTIAL POWER"
    GAME_OVER = "GAME OVER"

