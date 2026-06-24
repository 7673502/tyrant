from random import Random
from dataclasses import dataclass
from typing import Final
from tyrant.models.enums import PolicyTile

NUM_LIBERAL_POLICIES: Final = 6
NUM_FASCIST_POLICIES: Final = 11
POLICY_DRAW_COUNT: Final = 3


@dataclass(frozen=True)
class Deck:
    draw_pile: tuple[PolicyTile, ...]
    discard_pile: tuple[PolicyTile, ...] = ()

    @property
    def peek(self) -> tuple[PolicyTile, ...]:
        check_draw_size(self)
        return self.draw_pile[-3:]


def check_draw_size(deck: Deck):
    """Raises RuntimeError if the deck has fewer than 3 tiles in the draw pile."""
    if len(deck.draw_pile) < POLICY_DRAW_COUNT:
        raise RuntimeError(
            f"Draw pile should always contain at least 3 tiles but contains {len(deck.draw_pile)}."
        )


def create_deck(rng: Random) -> Deck:
    """Creates and returns a new initialized, shuffled deck."""
    initial_pile = [PolicyTile.LIBERAL] * NUM_LIBERAL_POLICIES + [
        PolicyTile.FASCIST
    ] * NUM_FASCIST_POLICIES
    rng.shuffle(initial_pile)
    return Deck(draw_pile=tuple(initial_pile), discard_pile=())


def shuffle_deck(deck: Deck, rng: Random) -> tuple[Deck, bool]:
    """Shuffles only if less than 3 tiles in draw pile and returns whether shuffle occurred."""
    if len(deck.draw_pile) < POLICY_DRAW_COUNT:
        new_draw = list(deck.draw_pile) + list(deck.discard_pile)
        rng.shuffle(new_draw)
        return Deck(draw_pile=tuple(new_draw), discard_pile=()), True
    return deck, False


def draw_policies(deck: Deck) -> tuple[Deck, tuple[PolicyTile, PolicyTile, PolicyTile]]:
    """Draws 3 policies from the deck."""
    check_draw_size(deck)
    top_three = (deck.draw_pile[-1], deck.draw_pile[-2], deck.draw_pile[-3])
    new_draw_pile = deck.draw_pile[:-3]
    return Deck(draw_pile=new_draw_pile, discard_pile=deck.discard_pile), top_three


def top_deck(deck: Deck) -> tuple[Deck, PolicyTile]:
    """Draws 1 policy from the top of the deck."""
    check_draw_size(deck)
    tile = deck.draw_pile[-1]
    new_draw_pile = deck.draw_pile[:-1]
    return Deck(draw_pile=new_draw_pile, discard_pile=deck.discard_pile), tile


def discard_policies(deck: Deck, *tiles: PolicyTile) -> Deck:
    """Discards policies into the discard pile."""
    new_discard = deck.discard_pile + tiles
    return Deck(draw_pile=deck.draw_pile, discard_pile=new_discard)
