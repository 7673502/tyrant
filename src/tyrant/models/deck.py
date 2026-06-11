from random import shuffle
from typing import Final
from tyrant.models.enums import PolicyTile

NUM_BLUE_POLICIES: Final = 6
NUM_RED_POLICIES: Final = 11
POLICY_DRAW_COUNT: Final = 3

class Deck:
    def __init__(self):
        self.draw_pile = []
        self.discard_pile = NUM_BLUE_POLICIES * [PolicyTile.BLUE] + NUM_RED_POLICIES * [PolicyTile.RED]
        self.shuffle()

    def shuffle(self) -> bool:
        '''shuffles only if less than 3 tiles in draw pile and returns whether shuffle occurred'''
        if len(self.draw_pile) < POLICY_DRAW_COUNT:
            self.draw_pile.extend(self.discard_pile)
            shuffle(self.draw_pile)
            self.discard_pile = []

            return True
        
        return False

    def _check_draw_size(self):
        if len(self.draw_pile) < POLICY_DRAW_COUNT:
            raise RuntimeError(f"Draw pile should always contain at least 3 tiles but contains {len(self.draw_pile)}.")

    def draw(self):
        self._check_draw_size()
        top_three = (self.draw_pile.pop(), self.draw_pile.pop(), self.draw_pile.pop())
        return top_three

    def top_deck(self):
        self._check_draw_size()
        tile = self.draw_pile.pop()
        return tile

    def peek(self):
        self._check_draw_size()
        return self.draw_pile[-3:]
    
    def discard(self, tile1: PolicyTile, tile2: PolicyTile):
        self.discard_pile.extend([tile1, tile2])
