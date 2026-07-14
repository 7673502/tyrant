import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from tyrant.models.action import Action


class TestAction(unittest.TestCase):
    def test_action_immutability(self):
        """Test that the Action dataclass is frozen."""
        action = Action(description="Vote JA")
        self.assertTrue(is_dataclass(action))

        with self.assertRaises(FrozenInstanceError):
            action.description = "Vote NEIN"
            action.description = "Vote NEIN"


if __name__ == "__main__":
    unittest.main()
