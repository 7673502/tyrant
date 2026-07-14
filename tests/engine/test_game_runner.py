import unittest
from dataclasses import replace

from tyrant.engine.game_runner import GameRunner
from tyrant.exceptions import TyrantError
from tyrant.models.action import Action, NominateAction, ChancellorEnactAction
from tyrant.models.enums import HIDDEN, GamePhase
from tyrant.models.game_state import GameState, create_game


class StubAgent:
    def __init__(self, uid: int, actions_to_play: list[Action]):
        self._uid = uid
        self._actions_to_play = actions_to_play

    @property
    def uid(self) -> int:
        return self._uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        return self._actions_to_play.pop(0)


class CapturingAgent:
    def __init__(self, uid: int):
        self._uid = uid
        self.captured_state: GameState | None = None

    @property
    def uid(self) -> int:
        return self._uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.captured_state = state
        return Action(description="Test")


class TestGameRunnerInitialization(unittest.TestCase):
    def test_init_with_initial_state(self):
        """Verifies that GameRunner initializes correctly when provided an explicit GameState."""
        state = create_game((1, 2, 3, 4, 5), 42)
        runner = GameRunner(agents=[], initial_state=state)
        self.assertEqual(runner.state, state)

    def test_init_without_initial_state(self):
        """Verifies that GameRunner generates a new GameState when none is provided."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertIsInstance(runner.state, GameState)
        self.assertEqual(len(runner.state.players), 5)

    def test_init_custom_configuration(self):
        """Verifies that GameRunner passes fixed_roles and shuffle_players to create_game."""
        from tyrant.models.enums import Role

        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        fixed_roles = {
            1: Role.HITLER,
            2: Role.FASCIST,
            3: Role.LIBERAL,
            4: Role.LIBERAL,
            5: Role.LIBERAL,
        }
        runner = GameRunner(
            agents=agents, seed=42, roles=fixed_roles, shuffle_players=False
        )
        self.assertEqual(tuple(p.uid for p in runner.state.players), (1, 2, 3, 4, 5))
        for p in runner.state.players:
            self.assertEqual(p.role, fixed_roles[p.uid])


class TestGameRunnerQueryAgent(unittest.IsolatedAsyncioTestCase):
    async def test_query_agent_scrubs_state(self):
        """Verifies that the GameState passed to the agent is properly scrubbed for hidden information."""
        state = create_game((1, 2, 3, 4, 5), 42)
        agent = CapturingAgent(uid=1)
        runner = GameRunner(agents=[agent], initial_state=state)

        await runner._query_agent(agent, tuple())

        self.assertIsNotNone(agent.captured_state)
        self.assertEqual(agent.captured_state.rng_state, HIDDEN)


class TestGameRunnerIteration(unittest.IsolatedAsyncioTestCase):
    async def test_run_iteration_applies_action(self):
        """Verifies that a single iteration queries agents and updates the internal state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        target_uid = state.players[(state.president_index + 1) % 5].uid

        action = NominateAction(description="Nominate", target_uid=target_uid)
        agents = [
            StubAgent(
                uid=p.uid, actions_to_play=[action] if p.uid == president_uid else []
            )
            for p in state.players
        ]
        runner = GameRunner(agents=agents, initial_state=state)

        new_state = await runner._run_iteration()

        self.assertEqual(new_state.phase, GamePhase.VOTING)
        self.assertEqual(new_state.chancellor, target_uid)

    async def test_run_iteration_stalemate(self):
        """Verifies that a TyrantError is raised if no players have legal actions."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.SETUP)
        agents = [StubAgent(uid=p.uid, actions_to_play=[]) for p in state.players]
        runner = GameRunner(agents=agents, initial_state=state)

        with self.assertRaises(TyrantError):
            await runner._run_iteration()


class TestGameRunnerRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_completes_game(self):
        """Verifies that run loops iterations until the game phase is GAME_OVER."""
        state = create_game((1, 2, 3, 4, 5), 42)

        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(state.deck.draw_pile[0], state.deck.draw_pile[1]),
            board=replace(state.board, fascist_played=5),
            chancellor=state.players[1].uid,
        )

        chancellor_uid = state.players[1].uid
        action = ChancellorEnactAction(description="Enact", target_index=0)
        agents = [
            StubAgent(
                uid=p.uid, actions_to_play=[action] if p.uid == chancellor_uid else []
            )
            for p in state.players
        ]

        runner = GameRunner(agents=agents, initial_state=state)
        final_state = await runner.run()

        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)


if __name__ == "__main__":
    unittest.main()
