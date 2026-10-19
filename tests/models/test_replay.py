import unittest
from dataclasses import fields, is_dataclass

from frozendict import frozendict

from tyrant.models.action import NominateAction, VoteAction
from tyrant.models.agent_fault import AgentFault
from tyrant.models.enums import GamePhase, Vote
from tyrant.models.game_state import create_game
from tyrant.models.replay import Replay, ReplayStep, record_fault, record_step

NOMINATE = NominateAction(description="Nominate Player 2", target_uid=2)
VOTE = VoteAction(description="Vote ja", vote=Vote.JA)
FAULT = AgentFault(
    uid=1,
    phase=GamePhase.NOMINATION,
    reason="InvalidMoveError('Bad reply')",
    fell_back=False,
    step=0,
    reply="Not JSON.",
)


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
        self.assertIsInstance(replay.faults, tuple)
        self.assertIsInstance(replay.agents, frozendict)
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

    def test_record_step_fallback(self):
        """Verifies that record_step marks a step as a fallback only when asked."""
        replay = record_step(Replay(initial_state=self.state), 1, NOMINATE)
        replay = record_step(replay, 3, VOTE, fallback=True)

        self.assertEqual(tuple(step.fallback for step in replay.steps), (False, True))

    def test_record_step_keeps_agents(self):
        """Verifies that record_step keeps the replay's agents."""
        agents = frozendict({1: frozendict(type="RandomAgent")})
        replay = Replay(initial_state=self.state, agents=agents)
        self.assertIs(record_step(replay, 1, NOMINATE).agents, agents)

    def test_record_fault_immutability(self):
        """Verifies that record_fault returns a new Replay and leaves the input unchanged."""
        replay = record_step(Replay(initial_state=self.state), 1, NOMINATE)
        new_replay = record_fault(replay, FAULT)

        self.assertIsNot(new_replay, replay)
        self.assertEqual(replay.faults, ())
        self.assertIs(new_replay.steps, replay.steps)
        self.assertIs(new_replay.initial_state, self.state)

    def test_record_fault_appends_fault(self):
        """Verifies that record_fault appends faults in the order they are recorded."""
        second = AgentFault(
            uid=2,
            phase=GamePhase.VOTING,
            reason="TimeoutError()",
            fell_back=True,
            step=1,
        )
        replay = record_fault(Replay(initial_state=self.state), FAULT)
        replay = record_fault(replay, second)

        self.assertEqual(replay.faults, (FAULT, second))


if __name__ == "__main__":
    unittest.main()
