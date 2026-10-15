import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

from tyrant.models.enums import Party, PolicyTile
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    InvestigationKnowledge,
    Knowledge,
    PeekKnowledge,
    PresidentDiscardKnowledge,
    PresidentDrawKnowledge,
)

THREE = (PolicyTile.LIBERAL, PolicyTile.FASCIST, PolicyTile.FASCIST)


class TestKnowledge(unittest.TestCase):
    def assert_frozen(self, knowledge: Knowledge):
        self.assertTrue(is_dataclass(knowledge))
        self.assertTrue(type(knowledge).__dataclass_params__.frozen)
        for field in fields(knowledge):
            with self.assertRaises(FrozenInstanceError):
                setattr(knowledge, field.name, None)

    def test_knowledge_immutability(self):
        """Verifies that Knowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(Knowledge(uid=1))

    def test_president_draw_knowledge_immutability(self):
        """Verifies that PresidentDrawKnowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            PresidentDrawKnowledge(uid=1, chancellor_uid=2, policies=THREE)
        )

    def test_president_discard_knowledge_immutability(self):
        """Verifies that PresidentDiscardKnowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            PresidentDiscardKnowledge(
                uid=1, chancellor_uid=2, discarded=THREE[0], passed=THREE[1:]
            )
        )

    def test_chancellor_receive_knowledge_immutability(self):
        """Verifies that ChancellorReceiveKnowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            ChancellorReceiveKnowledge(uid=2, president_uid=1, policies=THREE[:2])
        )

    def test_peek_knowledge_immutability(self):
        """Verifies that PeekKnowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(PeekKnowledge(uid=1, policies=THREE))

    def test_investigation_knowledge_immutability(self):
        """Verifies that InvestigationKnowledge is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            InvestigationKnowledge(uid=1, target_uid=2, party=Party.FASCIST)
        )


if __name__ == "__main__":
    unittest.main()
