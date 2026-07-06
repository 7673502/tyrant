import unittest
from dataclasses import FrozenInstanceError
from tyrant.models.board import Board, play_tile
from tyrant.models.enums import PolicyTile, Party


class TestBoard(unittest.TestCase):
    def test_liberal_win(self):
        """Tests that the liberal party wins when five liberal tiles are played."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(5):
                    self.assertIsNone(board.winner)
                    board, _ = play_tile(board, PolicyTile.LIBERAL)

                self.assertEqual(board.winner, Party.LIBERAL)

    def test_fascist_win(self):
        """Tests that the fascist party wins when six fascist tiles are played."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(6):
                    self.assertIsNone(board.winner)
                    board, _ = play_tile(board, PolicyTile.FASCIST)

                self.assertEqual(board.winner, Party.FASCIST)

    def test_hitler_zone_entered(self):
        """Tests that the board correctly identifies when the hitler zone is entered."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(3):
                    self.assertFalse(board.hitler_zone)
                    board, _ = play_tile(board, PolicyTile.FASCIST)

                self.assertTrue(board.hitler_zone)

    def test_veto_power_unlocked(self):
        """Tests that the board correctly identifies when veto power is unlocked."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)

                for _ in range(5):
                    self.assertFalse(board.veto_power_unlocked)
                    board, _ = play_tile(board, PolicyTile.FASCIST)

                self.assertTrue(board.veto_power_unlocked)

    def test_immutability(self):
        """Tests that the Board dataclass is frozen and cannot be mutated."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)
                with self.assertRaises(FrozenInstanceError):
                    board.player_count = 2
                with self.assertRaises(FrozenInstanceError):
                    board.liberal_played = 2
                with self.assertRaises(FrozenInstanceError):
                    board.fascist_played = 2

    def test_play_tile_immutability(self):
        """Tests that play_tile returns a new Board instance and does not mutate the original."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                board = Board(player_count=count)
                new_board, _ = play_tile(board, PolicyTile.LIBERAL)

                self.assertEqual(0, board.liberal_played)
                self.assertEqual(1, new_board.liberal_played)
