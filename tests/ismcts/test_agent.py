import unittest
from dataclasses import replace

from tyrant.engine.game_runner import GameRunner
from tyrant.engine.router import get_legal_actions
from tyrant.ismcts.agent import ISMCTSAgent
from tyrant.models.action import PassAction
from tyrant.models.discussion import Discussion
from tyrant.models.enums import DiscussionContext, GamePhase
from tyrant.models.game_state import create_game, scrub_state


class TestISMCTSAgent(unittest.IsolatedAsyncioTestCase):
    async def test_ismcts_agent_passes_in_discussion(self):
        """Verifies that ISMCTSAgent passes when it is its turn to speak."""
        state = create_game((0, 1, 2, 3, 4), seed=1, discussion_enabled=True)
        state = replace(
            state,
            phase=GamePhase.DISCUSSION,
            discussion=Discussion(
                context=DiscussionContext.AFTER_NOMINATION,
                resume_phase=GamePhase.VOTING,
                speaker_order=(0, 1, 2, 3, 4),
                rounds=2,
            ),
        )
        action = await ISMCTSAgent(0, iterations=10, seed=0).choose_action(
            scrub_state(state, 0), get_legal_actions(state, 0)
        )
        self.assertIsInstance(action, PassAction)

    async def test_ismcts_agent_full_game(self):
        """Verifies that five ISMCTS agents finish a game with discussions without any faults."""
        for seed in range(3):
            with self.subTest(seed=seed):
                agents = [ISMCTSAgent(uid, iterations=20, seed=uid) for uid in range(5)]
                runner = GameRunner(agents=agents, seed=seed, discussion_enabled=True)
                state = await runner.run()
                self.assertEqual(state.phase, GamePhase.GAME_OVER)
                self.assertEqual(runner.faults, ())


if __name__ == "__main__":
    unittest.main()
