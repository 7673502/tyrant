import unittest
from secret_tyrant.game import Board, PolicyTile, Party

class TestBoard(unittest.TestCase):
    def test_blue_win(self):
        board = Board(player_count=5)

        for _ in range(5):
            self.assertIsNone(board.check_win())
            board.play_tile(PolicyTile.BLUE)

        self.assertEqual(board.check_win(), Party.BLUE)

    def test_red_win(self):
        board = Board(player_count=5)

        for _ in range(6):
            self.assertIsNone(board.check_win())
            board.play_tile(PolicyTile.RED)

        self.assertEqual(board.check_win(), Party.RED)

    def test_tyrant_zone_entered(self):
        board = Board(player_count=5)

        for _ in range(3):
            self.assertFalse(board.check_tyrant_zone())
            board.play_tile(PolicyTile.RED)

        self.assertTrue(board.check_tyrant_zone())

