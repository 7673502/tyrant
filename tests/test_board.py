import unittest
from tyrant.models import Board, PolicyTile, Party

class TestBoard(unittest.TestCase):
    def test_blue_win(self):
        """Tests that the blue party wins when five blue tiles are played."""
        board = Board(player_count=5)

        for _ in range(5):
            self.assertIsNone(board.check_win())
            board.play_tile(PolicyTile.BLUE)

        self.assertEqual(board.check_win(), Party.BLUE)

    def test_red_win(self):
        """Tests that the red party wins when six red tiles are played."""
        board = Board(player_count=5)

        for _ in range(6):
            self.assertIsNone(board.check_win())
            board.play_tile(PolicyTile.RED)

        self.assertEqual(board.check_win(), Party.RED)

    def test_tyrant_zone_entered(self):
        """Tests that the board correctly identifies when the tyrant zone is entered."""
        board = Board(player_count=5)

        for _ in range(3):
            self.assertFalse(board.check_tyrant_zone())
            board.play_tile(PolicyTile.RED)

        self.assertTrue(board.check_tyrant_zone())

