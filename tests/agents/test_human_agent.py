import unittest

from tyrant.agents.human_agent import HumanAgent
from tyrant.engine.game_runner import GameRunner
from tyrant.models.action import PassAction, SpeakAction, VoteAction
from tyrant.models.enums import GamePhase, Vote
from tyrant.models.game_state import create_game, scrub_state


class TestHumanAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = scrub_state(create_game(uids=(0, 1, 2, 3, 4), seed=1), 0)
        self.output: list[str] = []

    def make_agent(self, replies: list[str]) -> HumanAgent:
        """Returns an agent that reads the given replies in order and records its output."""
        lines = iter(replies)
        return HumanAgent(
            uid=0, input_fn=lambda _: next(lines), output_fn=self.output.append
        )

    async def test_choose_action_returns_numbered_option(self):
        """Verify that the action whose number the player enters is returned."""
        actions = (
            VoteAction(description="Vote ja", vote=Vote.JA),
            VoteAction(description="Vote nein", vote=Vote.NEIN),
        )
        choice = await self.make_agent(["2"]).choose_action(self.state, actions)
        self.assertEqual(choice, actions[1])

    async def test_choose_action_shows_view_and_options(self):
        """Verify that the player's view and numbered options are shown."""
        actions = (
            VoteAction(description="Vote ja", vote=Vote.JA),
            VoteAction(description="Vote nein", vote=Vote.NEIN),
        )
        await self.make_agent(["1"]).choose_action(self.state, actions)
        self.assertIn("# Secret Hitler: Player 0's view", self.output[0])
        self.assertEqual(self.output[2:4], ["1. Vote ja", "2. Vote nein"])

    async def test_choose_action_reprompts_on_invalid_input(self):
        """Verify that non-numeric and out-of-range replies are rejected until a valid number is entered."""
        actions = (
            VoteAction(description="Vote ja", vote=Vote.JA),
            VoteAction(description="Vote nein", vote=Vote.NEIN),
        )
        choice = await self.make_agent(["ja", "0", "3", " 1 "]).choose_action(
            self.state, actions
        )
        self.assertEqual(choice, actions[0])
        self.assertEqual(self.output.count("Enter a number from 1 to 2."), 3)

    async def test_choose_action_fills_speech_message(self):
        """Verify that choosing to speak reads the message the player types."""
        actions = (SpeakAction(description="Speak"), PassAction(description="Pass"))
        choice = await self.make_agent(["1", "  I trust Player 2.  "]).choose_action(
            self.state, actions
        )
        self.assertEqual(
            choice, SpeakAction(description="Speak", message="I trust Player 2.")
        )

    async def test_choose_action_immutability(self):
        """Verify that choosing an action returns a new speech and leaves the offered actions unchanged."""
        actions = (SpeakAction(description="Speak"), PassAction(description="Pass"))
        state = self.state
        choice = await self.make_agent(["1", "Hello."]).choose_action(state, actions)
        self.assertIsNot(choice, actions[0])
        self.assertEqual(actions[0].message, "")
        self.assertEqual(state, self.state)

    async def test_human_agent_plays_full_game(self):
        """Verify that a game with only human agents always picking the first option ends."""
        agents = [
            HumanAgent(uid, input_fn=lambda _: "1", output_fn=lambda _: None)
            for uid in range(5)
        ]
        final_state = await GameRunner(agents, seed=3, timeout=None).run()
        self.assertIs(final_state.phase, GamePhase.GAME_OVER)


if __name__ == "__main__":
    unittest.main()
