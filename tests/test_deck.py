import unittest
from tyrant.models import Deck, PolicyTile

class TestDeck(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()

    def test_initial_deck_size(self):
        """Tests that the initial deck contains seventeen tiles and an empty discard pile."""
        self.assertEqual(len(self.deck.draw_pile), 17)
        self.assertEqual(len(self.deck.discard_pile), 0)

    def test_draw_three(self):
        """Tests drawing three tiles from the deck correctly updates pile sizes."""
        tiles = self.deck.draw()
        self.assertEqual(len(tiles), 3)
        self.assertEqual(len(self.deck.draw_pile), 14)

    def test_discard_two(self):
        """Tests discarding two tiles moves them to the discard pile."""
        self.deck.discard(PolicyTile.RED, PolicyTile.RED)
        self.assertEqual(len(self.deck.discard_pile), 2)

    def test_draw_pile_empty_exception(self):
        """Tests that a runtime error is raised when drawing from a pile with fewer than three tiles."""
        self.deck.draw_pile = []
        with self.assertRaises(RuntimeError):
            self.deck.draw()

