import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from tyrant.models.agents import Action


class TestAction(unittest.TestCase):
    def test_action_immutability(self):
        """Test that the Action dataclass is frozen."""
        action = Action(id="vote_ja", description="Vote JA")
        self.assertTrue(is_dataclass(action))

        with self.assertRaises(FrozenInstanceError):
            action.id = "vote_nein"


if __name__ == "__main__":
    unittest.main()
