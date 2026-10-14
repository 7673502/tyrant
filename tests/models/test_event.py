import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

from frozendict import frozendict

from tyrant.models.claim import InvestigationClaim
from tyrant.models.enums import (
    DiscussionContext,
    Party,
    PolicyTile,
    Vote,
    WinCondition,
)
from tyrant.models.event import (
    ClaimEvent,
    ElectionEvent,
    Event,
    ExecutionEvent,
    GameOverEvent,
    InvestigationEvent,
    NominationEvent,
    PolicyEnactedEvent,
    SpecialElectionEvent,
    SpeechEvent,
    VetoEvent,
)


class TestEvent(unittest.TestCase):
    def assert_frozen(self, event: Event):
        self.assertTrue(is_dataclass(event))
        self.assertTrue(type(event).__dataclass_params__.frozen)
        for field in fields(event):
            with self.assertRaises(FrozenInstanceError):
                setattr(event, field.name, None)

    def test_event_immutability(self):
        """Verifies that Event is a frozen dataclass."""
        self.assert_frozen(Event())

    def test_nomination_event_immutability(self):
        """Verifies that NominationEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(NominationEvent(president_uid=1, chancellor_uid=2))

    def test_election_event_immutability(self):
        """Verifies that ElectionEvent is a frozen dataclass with immutable fields."""
        event = ElectionEvent(
            president_uid=1,
            chancellor_uid=2,
            votes=frozendict({1: Vote.JA, 2: Vote.NEIN}),
            result=Vote.NEIN,
        )
        self.assert_frozen(event)
        self.assertIsInstance(event.votes, frozendict)

    def test_policy_enacted_event_immutability(self):
        """Verifies that PolicyEnactedEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            PolicyEnactedEvent(
                policy=PolicyTile.LIBERAL, president_uid=1, chancellor_uid=2
            )
        )

    def test_policy_enacted_event_top_deck(self):
        """Verifies that a PolicyEnactedEvent without a government is a top-deck."""
        enacted = PolicyEnactedEvent(
            policy=PolicyTile.LIBERAL, president_uid=1, chancellor_uid=2
        )
        top_decked = PolicyEnactedEvent(
            policy=PolicyTile.FASCIST, president_uid=None, chancellor_uid=None
        )
        self.assertFalse(enacted.top_deck)
        self.assertTrue(top_decked.top_deck)

    def test_veto_event_immutability(self):
        """Verifies that VetoEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(VetoEvent(president_uid=1, chancellor_uid=2, approved=True))

    def test_claim_event_immutability(self):
        """Verifies that ClaimEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            ClaimEvent(
                claim=InvestigationClaim(uid=1, party=Party.LIBERAL),
                president_uid=1,
                chancellor_uid=None,
                target_uid=3,
            )
        )

    def test_investigation_event_immutability(self):
        """Verifies that InvestigationEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(InvestigationEvent(president_uid=1, target_uid=2))

    def test_special_election_event_immutability(self):
        """Verifies that SpecialElectionEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(SpecialElectionEvent(president_uid=1, target_uid=2))

    def test_execution_event_immutability(self):
        """Verifies that ExecutionEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(ExecutionEvent(president_uid=1, target_uid=2))

    def test_speech_event_immutability(self):
        """Verifies that SpeechEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            SpeechEvent(
                uid=1, text="Hello.", context=DiscussionContext.AFTER_NOMINATION
            )
        )

    def test_game_over_event_immutability(self):
        """Verifies that GameOverEvent is a frozen dataclass with immutable fields."""
        self.assert_frozen(
            GameOverEvent(winner=Party.LIBERAL, condition=WinCondition.LIBERAL_POLICIES)
        )


if __name__ == "__main__":
    unittest.main()
