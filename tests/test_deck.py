import unittest
from secret_tyrant.game import Deck, PolicyTile

class TestDeck(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()

    def test_initial_deck_size(self):
        self.assertEqual(len(self.deck.draw_pile), 17)
        self.assertEqual(len(self.deck.discard_pile), 0)

    def test_draw_three(self):
        tiles = self.deck.draw()
        self.assertEqual(len(tiles), 3)
        self.assertEqual(len(self.deck.draw_pile), 14)

    def test_discard_two(self):
        self.deck.discard(PolicyTile.RED, PolicyTile.RED)
        self.assertEqual(len(self.deck.discard_pile), 2)

    def test_draw_pile_empty_exception(self):
        self.deck.draw_pile = []
        with self.assertRaises(RuntimeError):
            self.deck.draw()

