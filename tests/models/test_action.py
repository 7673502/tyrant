import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

from tyrant.models.action import Action, ClaimPresidentEnactAction, CorrectClaimAction
from tyrant.models.claim import PresidentEnactClaim
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

    def test_correct_claim_action_immutability(self):
        """Verifies that CorrectClaimAction is a frozen dataclass with immutable fields."""
        action = CorrectClaimAction(
            description="Correct your claim",
            claim=PresidentEnactClaim(
                uid=1,
                policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.LIBERAL),
                discarded=PolicyTile.FASCIST,
            ),
        )
        self.assertTrue(type(action).__dataclass_params__.frozen)
        for field in fields(action):
            with self.assertRaises(FrozenInstanceError):
                setattr(action, field.name, None)


if __name__ == "__main__":
    unittest.main()
