import unittest
from dataclasses import FrozenInstanceError
from random import Random
from tyrant.models.deck import Deck, create_deck, draw_policies, discard_policies, top_deck, shuffle_deck
from tyrant.models.enums import PolicyTile


class TestDeck(unittest.TestCase):
    def setUp(self):
        self.rng = Random(42)
        self.deck = create_deck(self.rng)

    def test_initial_deck_size(self):
        """Tests that the initial deck contains seventeen tiles and an empty discard pile."""
        self.assertEqual(len(self.deck.draw_pile), 17)
        self.assertEqual(len(self.deck.discard_pile), 0)

    def test_draw_three(self):
        """Tests drawing three tiles from the deck correctly updates pile sizes."""
        new_deck, tiles = draw_policies(self.deck)
        self.assertEqual(len(tiles), 3)
        self.assertEqual(len(new_deck.draw_pile), 14)

    def test_discard_two(self):
        """Tests discarding two tiles moves them to the discard pile."""
        new_deck = discard_policies(self.deck, PolicyTile.RED, PolicyTile.RED)
        self.assertEqual(len(new_deck.discard_pile), 2)

    def test_draw_pile_empty_exception(self):
        """Tests that a runtime error is raised when drawing from a pile with fewer than three tiles."""
        bad_deck = Deck(draw_pile=())
        with self.assertRaises(RuntimeError):
            draw_policies(bad_deck)

    def test_immutability(self):
        """Tests that the Deck dataclass is frozen and cannot be mutated."""
        with self.assertRaises(FrozenInstanceError):
            self.deck.draw_pile = ()

    def test_draw_policies_immutability(self):
        """Tests that drawing policies returns a new instance and does not mutate the original."""
        new_deck, _ = draw_policies(self.deck)
        self.assertEqual(len(self.deck.draw_pile), 17)
        self.assertEqual(len(new_deck.draw_pile), 14)

    def test_discard_policies_immutability(self):
        """Tests that discarding policies returns a new instance and does not mutate the original."""
        new_deck = discard_policies(self.deck, PolicyTile.RED, PolicyTile.BLUE)
        self.assertEqual(len(self.deck.discard_pile), 0)
        self.assertEqual(len(new_deck.discard_pile), 2)

    def test_rng_reproducibility(self):
        """Tests that using the same RNG seed produces the same deck and shuffles exactly the same way."""
        rng1 = Random(42)
        rng2 = Random(42)
        
        deck1 = create_deck(rng1)
        deck2 = create_deck(rng2)

        self.assertEqual(deck1.draw_pile, deck2.draw_pile)

        # Empty the draw pile for both to force a shuffle (< 3)
        deck1_empty, _ = draw_policies(deck1)
        deck1_empty, _ = draw_policies(deck1_empty)
        deck1_empty, _ = draw_policies(deck1_empty)
        deck1_empty, _ = draw_policies(deck1_empty)
        deck1_empty, _ = draw_policies(deck1_empty)

        deck2_empty, _ = draw_policies(deck2)
        deck2_empty, _ = draw_policies(deck2_empty)
        deck2_empty, _ = draw_policies(deck2_empty)
        deck2_empty, _ = draw_policies(deck2_empty)
        deck2_empty, _ = draw_policies(deck2_empty)

        deck1_empty = discard_policies(deck1_empty, PolicyTile.RED, PolicyTile.BLUE)
        deck2_empty = discard_policies(deck2_empty, PolicyTile.RED, PolicyTile.BLUE)

        deck1_shuffled, _ = shuffle_deck(deck1_empty, rng1)
        deck2_shuffled, _ = shuffle_deck(deck2_empty, rng2)

        self.assertEqual(deck1_shuffled.draw_pile, deck2_shuffled.draw_pile)
