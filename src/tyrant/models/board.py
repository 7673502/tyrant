from typing import Final, Optional
from tyrant.models.enums import Party, PolicyTile, PresidentialPower

TYRANT_ZONE_COUNT: Final = 3
BLUE_TILES_TO_WIN: Final = 5
RED_TILES_TO_WIN: Final = 6

class Board:
    RED_TRACK_5_6: Final = (
        PresidentialPower.NONE,
        PresidentialPower.NONE,
        PresidentialPower.POLICY_PEEK,
        PresidentialPower.EXECUTION,
        PresidentialPower.EXECUTION,
        PresidentialPower.NONE
    )
    RED_TRACK_7_8: Final = (
        PresidentialPower.NONE,
        PresidentialPower.INVESTIGATE,
        PresidentialPower.SPECIAL_ELECTION,
        PresidentialPower.EXECUTION,
        PresidentialPower.EXECUTION,
        PresidentialPower.NONE
    )
    RED_TRACK_9_10: Final = (
        PresidentialPower.INVESTIGATE,
        PresidentialPower.INVESTIGATE,
        PresidentialPower.SPECIAL_ELECTION,
        PresidentialPower.EXECUTION,
        PresidentialPower.EXECUTION,
        PresidentialPower.NONE
    )

    def __init__(self, player_count: int):
        if player_count < 5 or player_count > 10:
            raise ValueError(f"Player count must be between 5 and 10 inclusive. Board received {player_count} for player count.") 

        if 5 <= player_count <= 6:
            self.RED_TRACK = Board.RED_TRACK_5_6
        elif 7 <= player_count <= 8:
            self.RED_TRACK = Board.RED_TRACK_7_8
        else:
            self.RED_TRACK = Board.RED_TRACK_9_10

        self.blue_played = 0
        self.red_played = 0

    def play_tile(self, tile: PolicyTile) -> PresidentialPower:
        match tile:
            case PolicyTile.BLUE:
                self.blue_played += 1
                return PresidentialPower.NONE
            case PolicyTile.RED:
                self.red_played += 1
                return self.RED_TRACK[self.red_played - 1]

    def check_win(self) -> Optional[Party]:
        if self.blue_played >= BLUE_TILES_TO_WIN:
            return Party.BLUE
        elif self.red_played >= RED_TILES_TO_WIN:
            return Party.RED
        else:
            return None

    def check_tyrant_zone(self) -> bool:
        return self.red_played >= TYRANT_ZONE_COUNT 
