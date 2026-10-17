import asyncio
import unittest
from dataclasses import FrozenInstanceError, fields

from tyrant.agents.human_agent import HumanAgent, PendingTurn
from tyrant.engine.game_runner import GameRunner
from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.action import PassAction, SpeakAction, VoteAction
from tyrant.models.enums import GamePhase, Vote
from tyrant.models.game_state import create_game, scrub_state

VOTES = (
    VoteAction(description="Vote ja", vote=Vote.JA),
    VoteAction(description="Vote nein", vote=Vote.NEIN),
)
SPEECH = (SpeakAction(description="Speak"), PassAction(description="Pass"))


class TestHumanAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = scrub_state(create_game(uids=(0, 1, 2, 3, 4), seed=1), 0)
        self.agent = HumanAgent(uid=0)

    async def start_turn(self, valid_actions):
        """Returns a task asking the agent for an action, once its turn is pending."""
        task = asyncio.create_task(self.agent.choose_action(self.state, valid_actions))
        await asyncio.sleep(0)
        return task

    def test_pending_turn_immutability(self):
        """Verify that PendingTurn is frozen and every field is immutable."""
        turn = PendingTurn(state=self.state, valid_actions=VOTES)
        for field in fields(turn):
            with self.subTest(field=field.name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(turn, field.name, None)
        self.assertIsInstance(turn.valid_actions, tuple)

    async def test_choose_action_publishes_pending_turn(self):
        """Verify that the turn is published on pending while the agent waits."""
        task = await self.start_turn(VOTES)
        self.assertEqual(
            self.agent.pending, PendingTurn(state=self.state, valid_actions=VOTES)
        )
        self.assertFalse(task.done())
        task.cancel()

    async def test_submit_returns_chosen_action(self):
        """Verify that the submitted index decides the action and clears the pending turn."""
        task = await self.start_turn(VOTES)
        self.agent.submit(1)
        self.assertEqual(await task, VOTES[1])
        self.assertIsNone(self.agent.pending)

    async def test_submit_fills_speech_message(self):
        """Verify that the submitted message is filled in on a chosen speech."""
        task = await self.start_turn(SPEECH)
        self.agent.submit(0, "I trust Player 2.")
        self.assertEqual(
            await task, SpeakAction(description="Speak", message="I trust Player 2.")
        )

    async def test_submit_immutability(self):
        """Verify that submitting a speech returns a new action and leaves the offered actions unchanged."""
        task = await self.start_turn(SPEECH)
        self.agent.submit(0, "Hello.")
        self.assertIsNot(await task, SPEECH[0])
        self.assertEqual(SPEECH[0].message, "")

    async def test_submit_without_pending_turn_raises(self):
        """Verify that submitting with no pending turn raises TyrantError."""
        with self.assertRaises(TyrantError):
            self.agent.submit(0)

    async def test_submit_twice_raises(self):
        """Verify that a second submission for the same turn raises TyrantError."""
        task = await self.start_turn(VOTES)
        self.agent.submit(0)
        with self.assertRaises(TyrantError):
            self.agent.submit(1)
        self.assertEqual(await task, VOTES[0])

    async def test_submit_out_of_range_raises(self):
        """Verify that an out-of-range index raises InvalidMoveError and keeps the turn pending."""
        task = await self.start_turn(VOTES)
        for index in (-1, 2):
            with self.subTest(index=index):
                with self.assertRaises(InvalidMoveError):
                    self.agent.submit(index)
        self.assertIsNotNone(self.agent.pending)
        self.agent.submit(0)
        self.assertEqual(await task, VOTES[0])

    async def test_on_turn_receives_pending_turn(self):
        """Verify that on_turn is called with the new turn."""
        turns = []
        self.agent.on_turn = turns.append
        task = await self.start_turn(VOTES)
        self.assertEqual(turns, [PendingTurn(state=self.state, valid_actions=VOTES)])
        task.cancel()

    async def test_timeout_clears_pending_turn(self):
        """Verify that a timed-out turn is withdrawn and can no longer be submitted."""
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.agent.choose_action(self.state, VOTES), 0.01)
        self.assertIsNone(self.agent.pending)
        with self.assertRaises(TyrantError):
            self.agent.submit(0)

    async def test_human_agent_plays_full_game(self):
        """Verify that a game with only human agents always submitting the first option ends."""
        agents = [HumanAgent(uid) for uid in range(5)]
        for agent in agents:
            agent.on_turn = lambda _, agent=agent: agent.submit(0)
        final_state = await GameRunner(agents, seed=3).run()
        self.assertIs(final_state.phase, GamePhase.GAME_OVER)


if __name__ == "__main__":
    unittest.main()
