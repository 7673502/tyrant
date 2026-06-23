from dataclasses import dataclass, replace
from typing import Final, Optional
from tyrant.models.enums import Party, PolicyTile, PresidentialPower

TYRANT_ZONE_COUNT: Final = 3
BLUE_TILES_TO_WIN: Final = 5
RED_TILES_TO_WIN: Final = 6

RED_TRACK_5_6: Final = (
    PresidentialPower.NONE,
    PresidentialPower.NONE,
    PresidentialPower.POLICY_PEEK,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)
RED_TRACK_7_8: Final = (
    PresidentialPower.NONE,
    PresidentialPower.INVESTIGATE,
    PresidentialPower.SPECIAL_ELECTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)
RED_TRACK_9_10: Final = (
    PresidentialPower.INVESTIGATE,
    PresidentialPower.INVESTIGATE,
    PresidentialPower.SPECIAL_ELECTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.EXECUTION,
    PresidentialPower.NONE,
)

RED_TRACKS: Final = frozendict(
    {
        5: RED_TRACK_5_6,
        6: RED_TRACK_5_6,
        7: RED_TRACK_7_8,
        8: RED_TRACK_7_8,
        9: RED_TRACK_9_10,
        10: RED_TRACK_9_10,
    }
)


@dataclass(frozen=True)
class Board:
    player_count: int
    blue_played: int = 0
    red_played: int = 0

    @property
    def winner(self) -> Optional[Party]:
        if self.blue_played >= BLUE_TILES_TO_WIN:
            return Party.BLUE
        elif self.red_played >= RED_TILES_TO_WIN:
            return Party.RED
        else:
            return None

    @property
    def tyrant_zone(self) -> bool:
        return self.red_played >= TYRANT_ZONE_COUNT


def play_tile(board: Board, tile: PolicyTile) -> tuple[Board, PresidentialPower]:
    match tile:
        case PolicyTile.BLUE:
            return replace(
                board, blue_played=board.blue_played + 1
            ), PresidentialPower.NONE
        case PolicyTile.RED:
            new_board = replace(board, red_played=board.red_played + 1)
            track = RED_TRACKS[board.player_count]
            power = track[board.red_played]

            return new_board, power
