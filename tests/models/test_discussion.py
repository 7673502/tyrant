import unittest
from dataclasses import FrozenInstanceError, is_dataclass, replace

from tyrant.models.discussion import Discussion, Message
from tyrant.models.enums import DiscussionContext, GamePhase


class TestDiscussion(unittest.TestCase):
    def test_message_immutability(self):
        """Test that Message dataclass is frozen."""
        message = Message(uid=1, text="Hi", context=DiscussionContext.AFTER_NOMINATION)
        self.assertTrue(is_dataclass(message))
        with self.assertRaises(FrozenInstanceError):
            message.uid = 2
        with self.assertRaises(FrozenInstanceError):
            message.text = "Bye"
        with self.assertRaises(FrozenInstanceError):
            message.context = DiscussionContext.AFTER_EXECUTION

    def test_discussion_immutability(self):
        """Test that Discussion dataclass is frozen."""
        discussion = Discussion(
            context=DiscussionContext.AFTER_NOMINATION,
            resume_phase=GamePhase.VOTING,
            speaker_order=(1, 2, 3),
        )
        self.assertTrue(is_dataclass(discussion))
        self.assertIsInstance(discussion.speaker_order, tuple)
        with self.assertRaises(FrozenInstanceError):
            discussion.context = DiscussionContext.AFTER_EXECUTION
        with self.assertRaises(FrozenInstanceError):
            discussion.resume_phase = GamePhase.NOMINATION
        with self.assertRaises(FrozenInstanceError):
            discussion.speaker_order = (3, 2, 1)
        with self.assertRaises(FrozenInstanceError):
            discussion.rounds = 2
        with self.assertRaises(FrozenInstanceError):
            discussion.turn = 1

    def test_discussion_current_speaker(self):
        """Test that current_speaker follows the turn index through the speaker order."""
        discussion = Discussion(
            context=DiscussionContext.AFTER_NOMINATION,
            resume_phase=GamePhase.VOTING,
            speaker_order=(3, 1, 2),
        )
        self.assertEqual(discussion.current_speaker, 3)
        self.assertEqual(replace(discussion, turn=2).current_speaker, 2)

    def test_discussion_current_speaker_wraps_across_rounds(self):
        """Test that current_speaker restarts the speaker order in each new round."""
        discussion = Discussion(
            context=DiscussionContext.AFTER_NOMINATION,
            resume_phase=GamePhase.VOTING,
            speaker_order=(3, 1, 2),
            rounds=2,
        )
        self.assertEqual(replace(discussion, turn=3).current_speaker, 3)
        self.assertEqual(replace(discussion, turn=5).current_speaker, 2)

    def test_discussion_is_complete(self):
        """Test that is_complete is true only once every round has finished."""
        discussion = Discussion(
            context=DiscussionContext.AFTER_NOMINATION,
            resume_phase=GamePhase.VOTING,
            speaker_order=(3, 1, 2),
            rounds=2,
        )
        self.assertFalse(discussion.is_complete)
        self.assertFalse(replace(discussion, turn=5).is_complete)
        self.assertTrue(replace(discussion, turn=6).is_complete)


if __name__ == "__main__":
    unittest.main()
