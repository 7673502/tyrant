import unittest
from dataclasses import fields, is_dataclass

from tyrant.models.action import NominateAction, VoteAction
from tyrant.models.enums import Vote
from tyrant.models.game_state import create_game
from tyrant.models.replay import Replay, ReplayStep, record_step

NOMINATE = NominateAction(description="Nominate Player 2", target_uid=2)
VOTE = VoteAction(description="Vote ja", vote=Vote.JA)


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.state = create_game((1, 2, 3, 4, 5), 42)

    def test_replay_step_immutability(self):
        """Verifies that ReplayStep is a frozen dataclass and its fields are immutable."""
        self.assertTrue(is_dataclass(ReplayStep))
        self.assertTrue(ReplayStep.__dataclass_params__.frozen)

        step = ReplayStep(uid=1, action=NOMINATE)
        for field in fields(step):
            with self.assertRaises(Exception):
                setattr(step, field.name, None)

    def test_replay_immutability(self):
        """Verifies that Replay is a frozen dataclass and its fields are immutable."""
        self.assertTrue(is_dataclass(Replay))
        self.assertTrue(Replay.__dataclass_params__.frozen)

        replay = Replay(initial_state=self.state)
        self.assertIsInstance(replay.steps, tuple)
        for field in fields(replay):
            with self.assertRaises(Exception):
                setattr(replay, field.name, None)

    def test_record_step_immutability(self):
        """Verifies that record_step returns a new Replay and leaves the input unchanged."""
        replay = Replay(initial_state=self.state)
        new_replay = record_step(replay, 1, NOMINATE)

        self.assertIsNot(new_replay, replay)
        self.assertEqual(replay.steps, ())
        self.assertIs(new_replay.initial_state, self.state)

    def test_record_step_appends_step(self):
        """Verifies that record_step appends steps in the order they are recorded."""
        replay = record_step(Replay(initial_state=self.state), 1, NOMINATE)
        replay = record_step(replay, 3, VOTE)

        self.assertEqual(
            replay.steps,
            (ReplayStep(uid=1, action=NOMINATE), ReplayStep(uid=3, action=VOTE)),
        )


if __name__ == "__main__":
    unittest.main()
