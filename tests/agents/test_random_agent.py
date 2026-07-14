import unittest

from tyrant.agents.random_agent import RandomAgent
from tyrant.models.action import Action
from tyrant.models.game_state import create_game


class TestRandomAgent(unittest.IsolatedAsyncioTestCase):
    async def test_random_agent_selection(self):
        """Verify that RandomAgent chooses a valid action from the tuple."""
        agent = RandomAgent(uid=0)
        state = create_game(uids=(0, 1, 2, 3, 4))
        actions = (
            Action(id="action_a", description="Action A"),
            Action(id="action_b", description="Action B"),
        )
        choice = await agent.choose_action(state, actions)
        self.assertIn(choice, actions)


if __name__ == "__main__":
    unittest.main()
