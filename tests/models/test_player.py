import unittest
from dataclasses import FrozenInstanceError
from tyrant.models.player import Player
from tyrant.models.enums import Party, Role


class TestPlayer(unittest.TestCase):
    def test_immutability(self):
        """Tests that the Player dataclass is frozen and cannot be mutated."""
        player = Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL)
        with self.assertRaises(FrozenInstanceError):
            player.uid = 2
        with self.assertRaises(FrozenInstanceError):
            player.party = Party.FASCIST
        with self.assertRaises(FrozenInstanceError):
            player.role = Role.HITLER
