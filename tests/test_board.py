import unittest
from dataclasses import FrozenInstanceError
from tyrant.models.board import Board, play_tile
from tyrant.models.enums import PolicyTile, Party


class TestBoard(unittest.TestCase):
    def test_blue_win(self):
        """Tests that the blue party wins when five blue tiles are played."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(5):
                    self.assertIsNone(board.winner)
                    board, _ = play_tile(board, PolicyTile.BLUE)

                self.assertEqual(board.winner, Party.BLUE)

    def test_red_win(self):
        """Tests that the red party wins when six red tiles are played."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(6):
                    self.assertIsNone(board.winner)
                    board, _ = play_tile(board, PolicyTile.RED)

                self.assertEqual(board.winner, Party.RED)

    def test_tyrant_zone_entered(self):
        """Tests that the board correctly identifies when the tyrant zone is entered."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(3):
                    self.assertFalse(board.tyrant_zone)
                    board, _ = play_tile(board, PolicyTile.RED)

                self.assertTrue(board.tyrant_zone)

    def test_immutability(self):
        """Tests that the Board dataclass is frozen and cannot be mutated."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)
                with self.assertRaises(FrozenInstanceError):
                    board.player_count = 2
                with self.assertRaises(FrozenInstanceError):
                    board.blue_played = 2
                with self.assertRaises(FrozenInstanceError):
                    board.red_played = 2

    def test_play_tile_immutability(self):
        """Tests that play_tile returns a new Board instance and does not mutate the original."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)
                new_board, _ = play_tile(board, PolicyTile.BLUE)

                self.assertEqual(0, board.blue_played)
                self.assertEqual(1, new_board.blue_played)
