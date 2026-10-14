import asyncio
import unittest
from dataclasses import replace

from tyrant.agents.random_agent import RandomAgent
from tyrant.engine.game_runner import GameRunner, _is_offered
from tyrant.engine.router import get_legal_actions
from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.action import (
    Action,
    ChancellorEnactAction,
    NominateAction,
    PassAction,
    SpeakAction,
    VoteAction,
)
from tyrant.models.enums import HIDDEN, GamePhase, Vote
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
        return valid_actions[0]


class RaisingAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.calls = 0

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.calls += 1
        raise RuntimeError("Agent failure")


class SlowAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.calls = 0

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.calls += 1
        await asyncio.sleep(1)
        return valid_actions[0]


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


class TestGameRunnerDiscussion(unittest.IsolatedAsyncioTestCase):
    def test_init_discussion_disabled_by_default(self):
        """Verifies that GameRunner leaves discussion disabled unless asked."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertFalse(runner.state.discussion_enabled)

    def test_init_forwards_discussion_enabled(self):
        """Verifies that GameRunner passes discussion_enabled to create_game."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, discussion_enabled=True)
        self.assertTrue(runner.state.discussion_enabled)

    async def test_run_completes_game_with_discussion(self):
        """Verifies that random agents finish a game with discussion enabled and leave a transcript."""
        agents = [RandomAgent(uid=i) for i in range(1, 8)]
        runner = GameRunner(agents=agents, seed=42, discussion_enabled=True)
        final_state = await runner.run()
        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)
        self.assertGreater(len(final_state.messages), 0)


class TestGameRunnerQueryAgent(unittest.IsolatedAsyncioTestCase):
    async def test_query_agent_scrubs_state(self):
        """Verifies that the GameState passed to the agent is properly scrubbed for hidden information."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        agent = CapturingAgent(uid=president_uid)
        runner = GameRunner(agents=[agent], initial_state=state)

        await runner._query_agent(agent, get_legal_actions(state, president_uid))

        self.assertIsNotNone(agent.captured_state)
        self.assertEqual(agent.captured_state.rng_state, HIDDEN)

    async def test_attempt_rejects_unoffered_action(self):
        """Verifies that an action outside valid_actions raises an InvalidMoveError."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        bad_action = NominateAction(description="Nominate", target_uid=president_uid)
        agent = StubAgent(uid=president_uid, actions_to_play=[bad_action])
        runner = GameRunner(agents=[agent], initial_state=state)

        with self.assertRaises(InvalidMoveError):
            await runner._attempt(agent, state, get_legal_actions(state, president_uid))


class TestGameRunnerResilience(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = create_game((1, 2, 3, 4, 5), 42)
        self.president_uid = self.state.players[self.state.president_index].uid
        self.valid_actions = get_legal_actions(self.state, self.president_uid)
        self.bad_action = NominateAction(
            description="Nominate", target_uid=self.president_uid
        )

    def test_init_resilience_defaults(self):
        """Verifies that GameRunner defaults to two retries and no timeout."""
        runner = GameRunner(agents=[], initial_state=self.state)
        self.assertEqual(runner.max_retries, 2)
        self.assertIsNone(runner.timeout)

    async def test_query_agent_well_behaved_called_once(self):
        """Verifies that a well-behaved agent is queried once and its action is used."""
        good_action = self.valid_actions[1]
        agent = StubAgent(uid=self.president_uid, actions_to_play=[good_action])
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(agent, self.valid_actions)

        self.assertEqual(action, good_action)
        self.assertEqual(agent._actions_to_play, [])

    async def test_query_agent_keeps_speak_message(self):
        """Verifies that the agent's SpeakAction message survives validation."""
        speak_action = SpeakAction(description="Speak", message="Trust me.")
        agent = StubAgent(uid=self.president_uid, actions_to_play=[speak_action])
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(
            agent, (SpeakAction(description="Speak"), PassAction(description="Pass"))
        )

        self.assertEqual(action, speak_action)

    async def test_query_agent_retries_after_illegal_action(self):
        """Verifies that an illegal action is retried and a later legal action is used."""
        good_action = self.valid_actions[0]
        agent = StubAgent(
            uid=self.president_uid, actions_to_play=[self.bad_action, good_action]
        )
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(agent, self.valid_actions)

        self.assertEqual(action, good_action)

    async def test_query_agent_falls_back_after_illegal_actions(self):
        """Verifies that repeated illegal actions fall back to a legal action after all retries."""
        agent = StubAgent(uid=self.president_uid, actions_to_play=[self.bad_action] * 3)
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(agent, self.valid_actions)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent._actions_to_play, [])

    async def test_query_agent_falls_back_after_exceptions(self):
        """Verifies that an agent that always raises is retried and then falls back."""
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=4)

        _, action = await runner._query_agent(agent, self.valid_actions)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent.calls, 5)

    async def test_query_agent_falls_back_after_timeouts(self):
        """Verifies that an agent that exceeds the timeout is retried and then falls back."""
        agent = SlowAgent(uid=self.president_uid)
        runner = GameRunner(
            agents=[agent], initial_state=self.state, max_retries=1, timeout=0.01
        )

        _, action = await runner._query_agent(agent, self.valid_actions)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent.calls, 2)

    async def test_query_agent_zero_retries(self):
        """Verifies that max_retries of zero falls back after a single failed attempt."""
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=0)

        await runner._query_agent(agent, self.valid_actions)

        self.assertEqual(agent.calls, 1)

    async def test_query_agent_seeded_fallback_is_deterministic(self):
        """Verifies that fallback choices are reproducible for the same seed."""
        chosen = []
        for _ in range(2):
            agent = RaisingAgent(uid=self.president_uid)
            runner = GameRunner(agents=[agent], initial_state=self.state, seed=7)
            picks = [
                (await runner._query_agent(agent, self.valid_actions))[1]
                for _ in range(5)
            ]
            chosen.append(picks)

        self.assertEqual(chosen[0], chosen[1])

    async def test_run_completes_game_with_failing_agents(self):
        """Verifies that a game finishes when every agent always raises."""
        agents = [RaisingAgent(uid=i) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, max_retries=0)

        final_state = await runner.run()

        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)


class TestIsOffered(unittest.TestCase):
    def test_is_offered_matching_action(self):
        """Verifies that an action equal to an offered action is accepted."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertTrue(
            _is_offered(VoteAction(description="Vote JA", vote=Vote.JA), offered)
        )

    def test_is_offered_ignores_description(self):
        """Verifies that a different description does not prevent a match."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertTrue(
            _is_offered(VoteAction(description="Other", vote=Vote.JA), offered)
        )

    def test_is_offered_field_mismatch(self):
        """Verifies that an action with different identifying fields is rejected."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertFalse(
            _is_offered(VoteAction(description="Vote JA", vote=Vote.NEIN), offered)
        )

    def test_is_offered_type_mismatch(self):
        """Verifies that an action of a type that was not offered is rejected."""
        offered = (SpeakAction(description="Speak"),)
        self.assertFalse(_is_offered(PassAction(description="Speak"), offered))

    def test_is_offered_base_action_rejected(self):
        """Verifies that a bare Action is not accepted in place of a subclass."""
        offered = (PassAction(description="Pass"),)
        self.assertFalse(_is_offered(Action(description="Pass"), offered))

    def test_is_offered_speak_with_message(self):
        """Verifies that a SpeakAction with an agent-filled message is accepted."""
        offered = (SpeakAction(description="Speak"),)
        self.assertTrue(
            _is_offered(SpeakAction(description="Speak", message="Hello."), offered)
        )


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
