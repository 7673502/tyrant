import unittest
from dataclasses import replace

from tyrant.agents.biased_random_agent import BiasedRandomAgent
from tyrant.models.action import (
    ChancellorEnactAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.enums import Party, PolicyTile, Role, Vote
from tyrant.models.game_state import create_game
from tyrant.models.player import Player


class TestBiasedRandomAgent(unittest.IsolatedAsyncioTestCase):
    async def test_biased_agent_vote_bias(self):
        """Verify that BiasedRandomAgent prioritizes voting JA."""
        for i in range(20):
            with self.subTest(iteration=i):
                agent = BiasedRandomAgent(uid=0)
                players = (
                    Player(uid=0, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=3, party=Party.FASCIST, role=Role.FASCIST),
                    Player(uid=4, party=Party.FASCIST, role=Role.HITLER),
                )
                state = create_game(uids=(0, 1, 2, 3, 4))
                state = replace(
                    state,
                    players=players,
                    drawn_policies=(
                        PolicyTile.LIBERAL,
                        PolicyTile.FASCIST,
                        PolicyTile.LIBERAL,
                    ),
                )
                actions = (
                    VoteAction(description="Vote NEIN", vote=Vote.NEIN),
                    VoteAction(description="Vote JA", vote=Vote.JA),
                )
                choice = await agent.choose_action(state, actions)
                self.assertTrue(
                    isinstance(choice, VoteAction) and choice.vote == Vote.JA
                )

    async def test_biased_agent_discard_bias(self):
        """Verify that BiasedRandomAgent prioritizes discarding opposite policies."""
        for i in range(20):
            with self.subTest(iteration=i):
                agent = BiasedRandomAgent(uid=0)
                players = (
                    Player(uid=0, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=3, party=Party.FASCIST, role=Role.FASCIST),
                    Player(uid=4, party=Party.FASCIST, role=Role.HITLER),
                )
                state = create_game(uids=(0, 1, 2, 3, 4))
                state = replace(
                    state,
                    players=players,
                    drawn_policies=(
                        PolicyTile.LIBERAL,
                        PolicyTile.FASCIST,
                        PolicyTile.LIBERAL,
                    ),
                )
                actions = (
                    PresidentDiscardAction(
                        description="Discard Liberal", target_index=0
                    ),
                    PresidentDiscardAction(
                        description="Discard Fascist", target_index=1
                    ),
                    PresidentDiscardAction(
                        description="Discard Liberal", target_index=2
                    ),
                )
                choice = await agent.choose_action(state, actions)
                self.assertEqual(choice.description, "Discard Fascist")

    async def test_biased_agent_enact_bias(self):
        """Verify that BiasedRandomAgent prioritizes enacting aligned policies."""
        for i in range(20):
            with self.subTest(iteration=i):
                agent = BiasedRandomAgent(uid=0)
                players = (
                    Player(uid=0, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
                    Player(uid=3, party=Party.FASCIST, role=Role.FASCIST),
                    Player(uid=4, party=Party.FASCIST, role=Role.HITLER),
                )
                state = create_game(uids=(0, 1, 2, 3, 4))
                state = replace(
                    state,
                    players=players,
                    drawn_policies=(PolicyTile.LIBERAL, PolicyTile.FASCIST),
                )
                actions = (
                    ChancellorEnactAction(description="Enact Liberal", target_index=0),
                    ChancellorEnactAction(description="Enact Fascist", target_index=1),
                )
                choice = await agent.choose_action(state, actions)
                self.assertEqual(choice.description, "Enact Liberal")


if __name__ == "__main__":
    unittest.main()
