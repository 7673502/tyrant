from dataclasses import dataclass, replace
from typing import Final
from tyrant.models.enums import Party, PolicyTile, PresidentialPower

HITLER_ZONE_COUNT: Final = 3
LIBERAL_TILES_TO_WIN: Final = 5
FASCIST_TILES_TO_WIN: Final = 6

FASCIST_TRACK_5_6: Final = (
    PresidentialPower.NONE,
    PresidentialPower.NONE,
    PresidentialPower.POLICY_PEEK,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)
FASCIST_TRACK_7_8: Final = (
    PresidentialPower.NONE,
    PresidentialPower.INVESTIGATE_LOYALTY,
    PresidentialPower.CALL_SPECIAL_ELECTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)
FASCIST_TRACK_9_10: Final = (
    PresidentialPower.INVESTIGATE_LOYALTY,
    PresidentialPower.INVESTIGATE_LOYALTY,
    PresidentialPower.CALL_SPECIAL_ELECTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)

FASCIST_TRACKS: Final = frozendict(
    {
        5: FASCIST_TRACK_5_6,
        6: FASCIST_TRACK_5_6,
        7: FASCIST_TRACK_7_8,
        8: FASCIST_TRACK_7_8,
        9: FASCIST_TRACK_9_10,
        10: FASCIST_TRACK_9_10,
    }
)


@dataclass(frozen=True)
class Board:
    player_count: int
    liberal_played: int = 0
    fascist_played: int = 0

    @property
    def winner(self) -> Party | None:
        if self.liberal_played >= LIBERAL_TILES_TO_WIN:
            return Party.LIBERAL
        elif self.fascist_played >= FASCIST_TILES_TO_WIN:
            return Party.FASCIST
        else:
            return None

    @property
    def hitler_zone(self) -> bool:
        return self.fascist_played >= HITLER_ZONE_COUNT


def play_tile(board: Board, tile: PolicyTile) -> tuple[Board, PresidentialPower]:
    match tile:
        case PolicyTile.LIBERAL:
            return replace(
                board, liberal_played=board.liberal_played + 1
            ), PresidentialPower.NONE
        case PolicyTile.FASCIST:
            new_board = replace(board, fascist_played=board.fascist_played + 1)
            track = FASCIST_TRACKS[board.player_count]
            power = track[board.fascist_played]

            return new_board, power
