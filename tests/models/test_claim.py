import unittest
from dataclasses import FrozenInstanceError, is_dataclass

from tyrant.models.claim import (
    ChancellorEnactClaim,
    Claim,
    InvestigationClaim,
    PeekClaim,
    PresidentEnactClaim,
)
from tyrant.models.enums import Party, PolicyTile


class TestClaim(unittest.TestCase):
    def test_claim_immutability(self):
        """Test that InvestigationClaim dataclass is frozen."""
        claim = Claim(uid=1)
        self.assertTrue(is_dataclass(claim))
        with self.assertRaises(FrozenInstanceError):
            claim.uid = 2

    def test_investigation_claim_immutability(self):
        """Test that InvestigationClaim dataclass is frozen."""
        claim = InvestigationClaim(uid=1, party=Party.LIBERAL)
        self.assertTrue(is_dataclass(claim))
        with self.assertRaises(FrozenInstanceError):
            claim.uid = 2
            claim.party = Party.FASCIST

    def test_peek_claim_immutability(self):
        """Test that PeekClaim dataclass is frozen."""
        claim = PeekClaim(
            uid=1, policies=(PolicyTile.LIBERAL, PolicyTile.LIBERAL, PolicyTile.LIBERAL)
        )
        self.assertTrue(is_dataclass(claim))
        with self.assertRaises(FrozenInstanceError):
            claim.uid = 2
            claim.policies = (
                PolicyTile.FASCIST,
                PolicyTile.FASCIST,
                PolicyTile.FASCIST,
            )

    def test_president_enact_claim_immutability(self):
        """Test that PresidentEnactClaim dataclass is frozen."""
        claim = PresidentEnactClaim(
            uid=1, policies=(PolicyTile.LIBERAL, PolicyTile.LIBERAL, PolicyTile.LIBERAL)
        )
        self.assertTrue(is_dataclass(claim))
        with self.assertRaises(FrozenInstanceError):
            claim.uid = 2
            claim.policies = (
                PolicyTile.FASCIST,
                PolicyTile.FASCIST,
                PolicyTile.FASCIST,
            )

    def test_chancellor_enact_claim_immutability(self):
        """Test that ChancellorEnactClaim dataclass is frozen."""
        claim = ChancellorEnactClaim(
            uid=1, policies=(PolicyTile.LIBERAL, PolicyTile.LIBERAL)
        )
        self.assertTrue(is_dataclass(claim))
        with self.assertRaises(FrozenInstanceError):
            claim.uid = 2
            claim.policies = (
                PolicyTile.FASCIST,
                PolicyTile.FASCIST,
            )
