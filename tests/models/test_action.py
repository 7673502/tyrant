import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

from tyrant.models.action import Action, ClaimPresidentEnactAction
from tyrant.models.enums import PolicyTile


class TestAction(unittest.TestCase):
    def test_action_immutability(self):
        """Test that the Action dataclass is frozen."""
        action = Action(description="Vote JA")
        self.assertTrue(is_dataclass(action))

        with self.assertRaises(FrozenInstanceError):
            action.description = "Vote NEIN"
            action.description = "Vote NEIN"

    def test_claim_president_enact_action_immutability(self):
        """Verifies that ClaimPresidentEnactAction is a frozen dataclass with immutable fields."""
        action = ClaimPresidentEnactAction(
            description="Claim",
            claim_policies=(PolicyTile.LIBERAL, PolicyTile.FASCIST, PolicyTile.FASCIST),
            claim_discarded=PolicyTile.LIBERAL,
        )
        self.assertTrue(type(action).__dataclass_params__.frozen)
        for field in fields(action):
            with self.assertRaises(FrozenInstanceError):
                setattr(action, field.name, None)


if __name__ == "__main__":
    unittest.main()
